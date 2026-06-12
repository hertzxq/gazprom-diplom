"""
Сопоставление позиций: гибридный подход RapidFuzz + LLM.

Дополнительно учитываются специальные правила для актов:
- скидка 15% от прайс-листа;
- коэффициент 1.5 для сильного загрязнения;
- разбиение одной строки акта на несколько услуг;
- грубая фильтрация по категориям авто.
"""
import re
from typing import Any

import httpx
from rapidfuzz import fuzz

from app.config import settings
from app.schemas import MatchResult
from app.services.file_parser import ParsedDocument

# Ключи — в нормализованном виде (_normalize_text: lowercase, ё→е, спецсимволы
# заменяются пробелом), поэтому «x-trail» здесь записан как «x trail».
CATEGORY_KEYWORDS = {
    "седан": ("седан", "solaris", "rio", "logan", "polo", "camry", "corolla", "focus", "octavia"),
    "джип": ("джип", "suv", "кроссовер", "внедорож", "rav4", "prado", "x5", "x trail",
             "sportage", "outlander", "santa fe"),
    "микроавтобус": ("микроавтобус", "минивэн", "minibus", "автобус", "sprinter", "transit",
                     "starex", "crafter", "boxer"),
}

SERVICE_KEYWORDS = (
    "мойк",
    "чист",
    "полиров",
    "уборк",
    "пылесос",
    "воск",
    "химчист",
    "картридж",
    "замен",
    "обслужив",
    "шиномонтаж",
    "балансировк",
    "антикор",
)


async def match_positions(
    positions_document: ParsedDocument,
    source_document: ParsedDocument,
    source_file_type: str | None = None,
    scenario: str | None = None,
    use_llm: bool | None = None,
) -> list[MatchResult]:
    """
    Сопоставляет строки из УПД/Акта с позициями прайс-листа.

    Аргумент `scenario` (опциональный) задаёт явный сценарий обработки:
    - "d_lux"               — логика Д-люкс (скидка 15%, коэффициент 1.5,
                               категории авто, разбиение строк).
    - "leader_smi"|"veneta" — стандартная логика УПД (цена = total/quantity).
    - None / ""             — автоопределение по `source_file_type`.

    Если scenario явно противоречит source_file_type (например,
    `d_lux` + `upd` или `leader_smi` + `act`) — обработка идёт по сценарию,
    но все строки результата помечаются `needs_review=True` с пометкой
    «Сценарий не соответствует типу файла» в highlight_reason.

    `use_llm` управляет LLM-верификацией спорных позиций (зона неуверенности
    fuzzy-скоринга): None — по settings.LLM_MATCHER_ENABLED. На CPU каждый
    вызов LLM может ждать полный таймаут, поэтому фронт передаёт флаг явно.
    """
    positions_lookup = _prepare_positions(positions_document.rows)
    if not positions_lookup:
        return []

    if use_llm is None:
        use_llm = settings.LLM_MATCHER_ENABLED

    use_act_logic, mismatch = _resolve_scenario(scenario, source_file_type)

    if use_act_logic:
        results = await _match_act_rows(positions_lookup, source_document.rows, use_llm=use_llm)
    else:
        results = await _match_standard_rows(positions_lookup, source_document.rows, use_llm=use_llm)

    if mismatch:
        results = _mark_scenario_mismatch(results)

    return results


_SCENARIO_MISMATCH_REASON = "Сценарий не соответствует типу файла"


def _resolve_scenario(
    scenario: str | None, source_file_type: str | None
) -> tuple[bool, bool]:
    """
    Возвращает (использовать_логику_акта, есть_несоответствие).

    «Использовать логику акта» = True для сценария d_lux ИЛИ для file_type=act
    при пустом сценарии. Несоответствие = True если выбранный сценарий
    несовместим с типом файла.
    """
    normalized = (scenario or "").strip().lower()
    is_act_file = source_file_type == "act"

    if normalized == "d_lux":
        return True, not is_act_file
    if normalized in {"leader_smi", "veneta"}:
        return False, is_act_file
    # «Автоопределение» / неизвестный сценарий — по типу файла
    return is_act_file, False


def _mark_scenario_mismatch(results: list[MatchResult]) -> list[MatchResult]:
    """Помечает все строки как требующие проверки из-за несоответствия сценария."""
    marked: list[MatchResult] = []
    for r in results:
        reason = r.highlight_reason
        combined = (
            f"{reason}; {_SCENARIO_MISMATCH_REASON}" if reason else _SCENARIO_MISMATCH_REASON
        )
        marked.append(
            r.model_copy(update={"needs_review": True, "highlight_reason": combined})
        )
    return marked


async def _match_standard_rows(
    positions_lookup: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    use_llm: bool = True,
) -> list[MatchResult]:
    results: list[MatchResult] = []

    for source_row in source_rows:
        item_name = _extract_item_name(source_row)
        if not item_name:
            continue

        category = _detect_category(_row_to_text(source_row))
        best_match, needs_review = await _resolve_match(
            item_name, positions_lookup, category, use_llm=use_llm
        )

        quantity = _extract_numeric(source_row, ["количество", "кол-во", "кол.", "объем"])
        total = _extract_numeric(source_row, ["сумма", "стоимость", "всего", "итого"])
        unit = _extract_value(source_row, ["единица", "ед. изм", "ед.изм"])
        price = total / quantity if quantity and total and quantity > 0 else best_match.get("price") if best_match else None

        results.append(
            MatchResult(
                upd_row_index=source_row.get("_row_index", 0),
                upd_item_name=item_name,
                matched_position_number=best_match.get("number") if best_match else None,
                matched_position_name=best_match.get("name") if best_match else None,
                confidence=best_match.get("score", 0.0) if best_match else 0.0,
                needs_review=needs_review or best_match is None,
                quantity=quantity,
                unit=unit or (best_match.get("unit") if best_match else None),
                price=price,
                total=total,
            )
        )

    return results


async def _match_act_rows(
    positions_lookup: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    use_llm: bool = True,
) -> list[MatchResult]:
    """
    Сопоставление строк акта (Д-люкс).

    Категория авто:
    - Секционный заголовок (только категория, нет ключевых слов услуги) обновляет
      `current_category` и не порождает MatchResult.
    - Inline-категория в строке услуги имеет приоритет над унаследованной.
    - Если использована унаследованная категория — результат помечается
      `needs_review=True` с пояснением.
    """
    results: list[MatchResult] = []
    current_category: str | None = None

    for source_row in source_rows:
        row_text = _row_to_text(source_row)
        inline_category = _detect_category(row_text)

        raw_item_name = _extract_item_name(source_row) or row_text
        is_section_header = _is_section_header(raw_item_name, row_text)

        if is_section_header:
            # Только секционный заголовок обновляет «текущую» категорию.
            if inline_category:
                current_category = inline_category
            continue

        service_names = _split_act_services(raw_item_name)
        if not service_names:
            continue

        if inline_category:
            category = inline_category
            inherited_used = False
        elif current_category:
            category = current_category
            inherited_used = True
        else:
            category = None
            inherited_used = False

        for service_name in service_names:
            best_match, needs_review = await _resolve_match(
                service_name, positions_lookup, category, use_llm=use_llm
            )
            highlight_price = False
            highlight_reason: str | None = None
            quantity = 1.0
            unit = "условная единица"
            price: float | None = None
            total: float | None = None

            if best_match and best_match.get("price") is not None:
                price = _apply_discount(best_match["price"])
                if _has_strong_dirty_marker(service_name):
                    price *= 1.5
                    highlight_price = True
                    highlight_reason = "Применён коэффициент 1.5 для сильного загрязнения"

                if not _is_round_number(price):
                    highlight_price = True
                    highlight_reason = highlight_reason or "Цена содержит копейки и требует проверки"

                total = quantity * price

            if inherited_used and best_match is not None:
                inherit_reason = "Категория унаследована из предыдущей строки"
                highlight_reason = (
                    f"{highlight_reason}; {inherit_reason}" if highlight_reason else inherit_reason
                )

            # Марка авто не распознана, а выбранная позиция категорийная:
            # выбор категории фактически случаен — деградация должна быть видимой.
            unknown_category = (
                category is None and best_match is not None and bool(best_match.get("category"))
            )
            if unknown_category:
                no_cat_reason = "Категория автомобиля не распознана — проверьте выбор категории"
                highlight_reason = (
                    f"{highlight_reason}; {no_cat_reason}" if highlight_reason else no_cat_reason
                )

            results.append(
                MatchResult(
                    upd_row_index=source_row.get("_row_index", 0),
                    upd_item_name=service_name,
                    matched_position_number=best_match.get("number") if best_match else None,
                    matched_position_name=best_match.get("name") if best_match else None,
                    confidence=best_match.get("score", 0.0) if best_match else 0.0,
                    needs_review=needs_review or best_match is None or highlight_price
                    or inherited_used or unknown_category,
                    quantity=quantity,
                    unit=unit,
                    price=price,
                    total=total,
                    highlight_price=highlight_price,
                    highlight_reason=highlight_reason,
                )
            )

    return results


def _is_section_header(item_name: str, row_text: str) -> bool:
    """
    True если строка похожа на секционный заголовок (например «СЕДАН» / «Джипы»):
    содержит маркер категории и не содержит ни одного ключевого слова услуги.
    """
    haystack = _normalize_text(f"{item_name} {row_text}")
    if not haystack:
        return False
    if not _detect_category(haystack):
        return False
    return not any(keyword in haystack for keyword in SERVICE_KEYWORDS)


def _prepare_positions(positions_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Подготавливает список позиций для поиска."""
    lookup = []
    for row in positions_data:
        name = _extract_item_name(row)
        number = _extract_position_number(row)
        price = _extract_numeric(row, ["цена", "стоимость", "расценка", "цена за единицу", "тариф"])
        unit = _extract_value(row, ["единица", "ед. изм", "ед.изм"])
        row_text = _row_to_text(row)

        if name:
            lookup.append(
                {
                    "number": number,
                    "name": name,
                    "normalized_name": _normalize_text(name),
                    "price": price,
                    "unit": unit,
                    "category": _detect_category(row_text),
                    "raw": row,
                }
            )
    return lookup


async def _resolve_match(
    query: str,
    positions: list[dict[str, Any]],
    category_hint: str | None = None,
    use_llm: bool = True,
) -> tuple[dict[str, Any] | None, bool]:
    ranked = _rank_positions(query, positions, category_hint)
    best_match = ranked[0] if ranked else None

    if best_match and best_match["score"] >= settings.FUZZY_MATCH_THRESHOLD:
        return best_match, False

    # LLM выключена — мгновенная деградация: берём лучший fuzzy-кандидат
    # с пометкой needs_review (поведение идентично недоступному Ollama).
    if not use_llm:
        return best_match, True

    llm_candidates = ranked[:20]
    if best_match and best_match["score"] >= settings.FUZZY_UNCERTAIN_THRESHOLD:
        llm_match = await _llm_match(query, llm_candidates)
        return (llm_match or best_match), llm_match is None

    llm_match = await _llm_match(query, llm_candidates)
    if llm_match:
        return llm_match, True

    return best_match, True


def _rank_positions(
    query: str,
    positions: list[dict[str, Any]],
    category_hint: str | None = None,
) -> list[dict[str, Any]]:
    if not positions:
        return []

    filtered_positions = _filter_positions_by_category(positions, category_hint)
    normalized_query = _normalize_text(query)
    ranked: list[dict[str, Any]] = []

    for position in filtered_positions:
        token_score = fuzz.token_set_ratio(normalized_query, position["normalized_name"])
        sort_score = fuzz.token_sort_ratio(normalized_query, position["normalized_name"])
        partial_score = fuzz.partial_ratio(normalized_query, position["normalized_name"])
        score = token_score * 0.45 + sort_score * 0.35 + partial_score * 0.20

        if category_hint and position.get("category") == category_hint:
            score += 5

        ranked.append(
            {
                **position,
                "score": min(score, 100.0),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def _filter_positions_by_category(
    positions: list[dict[str, Any]],
    category_hint: str | None,
) -> list[dict[str, Any]]:
    if not category_hint:
        return positions

    matching = [position for position in positions if position.get("category") == category_hint]
    return matching or positions


async def _llm_match(query: str, positions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Сопоставление через LLM (Ollama API)."""
    if not positions:
        return None

    candidates_text = "\n".join(
        f"{p['number']}. {p['name']}" for p in positions if p["name"]
    )

    prompt = f"""Ты помощник по анализу закупочной документации.
Сопоставь наименование из УПД или акта с позицией из прайс-листа.

Наименование: "{query}"

Кандидаты:
{candidates_text}

Ответь только номером позиции. Если подходящей позиции нет, ответь 0.
"""

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 10},
                },
            )
        if response.status_code != 200:
            return None

        result_text = response.json().get("response", "").strip()
        numbers = re.findall(r"\d+", result_text)
        if not numbers:
            return None

        matched_num = int(numbers[0])
        if matched_num == 0:
            return None

        for position in positions:
            if position["number"] == matched_num:
                return {
                    **position,
                    "score": max(position.get("score", 0.0), 75.0),
                }
    except Exception:
        return None

    return None


def _split_act_services(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip(" ,;")
    if not normalized:
        return []

    chunks = [part.strip(" ,;") for part in re.split(r"(?:\r?\n|;|\s+\+\s+)", normalized) if part.strip(" ,;")]
    result: list[str] = []

    for chunk in chunks:
        lower_chunk = chunk.lower()
        # Считаем вхождения, а не уникальные маркеры: «полировка кузова и
        # полировка фар» содержит один маркер «полиров» дважды и тоже составная.
        if " и " in lower_chunk and sum(lower_chunk.count(marker) for marker in SERVICE_KEYWORDS) >= 2:
            result.extend(
                part.strip(" ,;")
                for part in re.split(r"\s+и\s+", chunk)
                if part.strip(" ,;")
            )
        else:
            result.append(chunk)

    return result or [normalized]


def _detect_category(text: str | None) -> str | None:
    normalized = _normalize_text(text or "")
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return None


def _has_strong_dirty_marker(text: str) -> bool:
    normalized = _normalize_text(text)
    return "сильн" in normalized and "загряз" in normalized


def _apply_discount(price: float) -> float:
    return round(price * 0.85, 2)


def _is_round_number(value: float) -> bool:
    return abs(value - round(value)) < 0.001


def _normalize_text(value: str) -> str:
    normalized = (value or "").lower()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _row_to_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(value).strip()
        for key, value in row.items()
        if not str(key).startswith("_") and value not in (None, "")
    )


def _extract_item_name(row: dict[str, Any]) -> str | None:
    """Извлекает наименование товара/услуги из строки."""
    name_keys = [
        "наименование",
        "наименование товара",
        "наименование работы",
        "наименование услуги",
        "товар",
        "услуга",
        "описание",
        "наименование работы (услуги)",
        "наименование товаров",
    ]
    for key in name_keys:
        for row_key in row:
            if key in str(row_key).lower():
                val = row.get(row_key)
                if val and str(val).strip():
                    return str(val).strip()

    for key, val in row.items():
        if key.startswith("_"):
            continue
        if val and isinstance(val, str) and len(val) > 3 and not val.replace(".", "").isdigit():
            return val.strip()
    return None


def _extract_position_number(row: dict[str, Any]) -> int | None:
    """Извлекает номер позиции."""
    num_keys = ["№", "номер", "п/п", "№ п/п", "n", "поз", "№ позиции", "порядковый номер"]
    for key in num_keys:
        for row_key in row:
            if key in str(row_key).lower():
                val = row.get(row_key)
                if val is not None:
                    try:
                        return int(float(str(val).replace(",", ".")))
                    except (ValueError, TypeError):
                        pass
    return None


def _extract_numeric(row: dict[str, Any], keys: list[str]) -> float | None:
    """Извлекает числовое значение по вариантам ключей."""
    for key in keys:
        for row_key in row:
            if key in str(row_key).lower():
                value = _to_float(row.get(row_key))
                if value is not None:
                    return value
    return None


def _extract_value(row: dict[str, Any], keys: list[str]) -> str | None:
    """Извлекает строковое значение по вариантам ключей."""
    for key in keys:
        for row_key in row:
            if key in str(row_key).lower():
                val = row.get(row_key)
                if val is not None and str(val).strip():
                    return str(val).strip()
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
    if not cleaned:
        return None

    if cleaned.count(",") == 1 and cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None
