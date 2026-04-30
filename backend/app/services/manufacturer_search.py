"""
Поиск производителей товаров через LLM (Ollama).

Два режима:
1. Поиск по характеристикам товара — возвращает список производителей
2. Поиск по наименованию — возвращает производителя и документацию
"""
import json
import logging
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def search_manufacturers_by_specs(
    product_name: str,
    characteristics: list[dict[str, str]],
    sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Поиск производителей по характеристикам товара.
    Возвращает список производителей с контактами, сертификатами и т.д.
    """
    chars_text = "\n".join(
        f"- {c['key']}: {c['value']}" for c in characteristics if c.get("key")
    )
    if not chars_text:
        chars_text = "(характеристики не указаны)"

    sources_text = (
        "Возможные источники: " + ", ".join(sources)
        if sources
        else "Возможные источники: открытые реестры РФ/ЕАЭС, сайты производителей, отраслевые каталоги"
    )

    prompt = f"""Ты — эксперт по российскому промышленному производству и закупочной деятельности.
Твоя задача — назвать РЕАЛЬНЫХ производителей товара ниже.

ТОВАР: "{product_name}"
ХАРАКТЕРИСТИКИ:
{chars_text}

{sources_text}

ЖЁСТКИЕ ПРАВИЛА:
1. Указывай ТОЛЬКО реально существующие компании, в которых ты уверен.
2. НЕ выдумывай названия. НЕ выдумывай сайты, телефоны, сертификаты.
3. Если не знаешь ни одного подходящего производителя — верни пустой массив [].
4. Если поле тебе неизвестно — оставь пустую строку "". Лучше пусто, чем выдумка.
5. Поля «name» и «country» — обязательны. Остальные могут быть пустыми.
6. Возвращай от 0 до 8 элементов. Лучше 2 точных, чем 8 выдуманных.

ПРИМЕР качественного ответа на ЗАПРОС "Подшипник шариковый радиальный, материал сталь":
[
  {{
    "name": "АО «Вологодский подшипниковый завод»",
    "country": "Россия",
    "website": "vbf.ru",
    "contacts": "",
    "certificates": "ГОСТ 8338, ГОСТ 7242, ISO 9001",
    "products": "Шариковые и роликовые подшипники общего назначения",
    "source": "Открытые данные о промышленных предприятиях РФ"
  }},
  {{
    "name": "ОАО «Степногорский подшипниковый завод»",
    "country": "Казахстан",
    "website": "",
    "contacts": "",
    "certificates": "ГОСТ 520",
    "products": "Подшипники качения для машиностроения",
    "source": "Реестры ЕАЭС"
  }}
]

Теперь ответь по запросу выше. Верни только JSON-массив, без пояснений и markdown.
"""
    return await _query_llm_json_array(prompt)


async def search_manufacturer_info(
    product_name: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """
    Поиск производителя и документации по наименованию товара.
    Возвращает информацию о производителе и ссылки на документы.
    """
    sources_text = (
        "Возможные источники: " + ", ".join(sources)
        if sources
        else "Возможные источники: открытые реестры РФ/ЕАЭС, сайты производителей, каталоги"
    )

    prompt = f"""Ты — эксперт по российскому промышленному производству.
Тебе дано конкретное наименование товара (часто это маркировка или модель). Назови
РЕАЛЬНОГО производителя и связанные с этим товаром документы (ГОСТ, ТУ и т.п.),
если ты в них уверен.

ТОВАР: "{product_name}"
{sources_text}

ЖЁСТКИЕ ПРАВИЛА:
1. Указывай только реально существующие компании и реально существующие документы.
2. НЕ выдумывай URL, телефоны, номера ТУ.
3. Если не знаешь — оставь поле пустой строкой "" или верни пустой массив [].
4. is_primary=true — только если ты уверен, что это именно производитель данной модели,
   а не просто компания, выпускающая похожее.
5. summary — короткая фактическая сводка (1–3 предложения), без воды и без выдумок.
   Если не знаешь товар — напиши прямо: «Информация о товаре не найдена».

ПРИМЕР качественного ответа для запроса "Кран шаровой LD КШЦФ 150":
{{
  "manufacturers": [
    {{
      "name": "ООО «ЛД»",
      "country": "Россия",
      "website": "ld-pride.ru",
      "contacts": "",
      "is_primary": true
    }}
  ],
  "documentation": [
    {{
      "title": "ГОСТ 21345-2005",
      "doc_type": "ГОСТ",
      "source_url": "",
      "description": "Краны шаровые, конусные и цилиндрические. Общие технические условия."
    }}
  ],
  "summary": "КШЦФ 150 — кран шаровой цельносварной фланцевый Ду 150 производства ООО «ЛД» (Челябинск). Применяется для перекрытия потоков воды, газа и нефтепродуктов."
}}

Теперь ответь по запросу выше. Верни только JSON-объект, без пояснений и markdown.
"""
    return await _query_llm_json_object(prompt)


async def _query_llm_json_array(prompt: str) -> list[dict[str, Any]]:
    """Запрос к Ollama и парсинг ответа как JSON-массива."""
    raw = await _call_ollama(prompt)
    if not raw:
        logger.warning("Ollama returned empty response for JSON array query")
        return []

    logger.info("Ollama raw response (first 500 chars): %s", raw[:500])

    try:
        parsed = _extract_json(raw)
        items: list[dict[str, Any]] = []
        if isinstance(parsed, list):
            items = [x for x in parsed if isinstance(x, dict)]
        elif isinstance(parsed, dict):
            # Иногда LLM возвращает {"key": [...]} вместо массива.
            # Также бывает один объект с пустыми полями — это «нет результата».
            for key in ("manufacturers", "results", "data", "items", "list"):
                if key in parsed and isinstance(parsed[key], list):
                    items = [x for x in parsed[key] if isinstance(x, dict)]
                    logger.info("Extracted %d items from key '%s'", len(items), key)
                    break
            else:
                # Один dict-объект — оборачиваем в массив только если name заполнен.
                if parsed.get("name"):
                    items = [parsed]
                else:
                    logger.info("Single dict with empty 'name' — treating as empty result")
        else:
            logger.warning("LLM response parsed as %s, expected list/dict", type(parsed).__name__)

        cleaned = _filter_placeholder_items(items)
        logger.info("After placeholder filter: %d items (was %d)", len(cleaned), len(items))
        return cleaned
    except Exception as e:
        logger.error("Failed to parse LLM JSON array response: %s\nRaw: %s", e, raw[:1000])
        return []


# Маркеры мусорных/плейсхолдерных значений, которые бросаются в глаза
# (фрагменты дословно скопированных подсказок из промпта).
_PLACEHOLDER_MARKERS = (
    "название компании",
    "название документа",
    "url сайта",
    "телефон, email",
    "сертификаты (гост",
    "краткое описание",
    "откуда получена",
    "company name",
    "manufacturer name",
)


def _is_placeholder_value(value: Any) -> bool:
    """Является ли значение плейсхолдером из примера промпта (а не реальным ответом)."""
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _filter_placeholder_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Отбрасывает элементы:
    - без name (пустой или только пробелы),
    - с name, очевидно скопированным из плейсхолдера примера.
    """
    result = []
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        if _is_placeholder_value(name):
            logger.warning("Dropping placeholder-like item: %r", name)
            continue
        result.append(item)
    return result


async def _query_llm_json_object(prompt: str) -> dict[str, Any]:
    """Запрос к Ollama и парсинг ответа как JSON-объекта."""
    empty = {"manufacturers": [], "documentation": [], "summary": "Не удалось получить информацию."}
    raw = await _call_ollama(prompt)
    if not raw:
        logger.warning("Ollama returned empty response for JSON object query")
        return empty

    logger.info("Ollama raw response (first 500 chars): %s", raw[:500])

    try:
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            logger.warning("LLM response parsed as %s, expected dict", type(parsed).__name__)
            return empty

        manufacturers_raw = parsed.get("manufacturers") or []
        manufacturers_raw = [x for x in manufacturers_raw if isinstance(x, dict)]
        manufacturers = _filter_placeholder_items(manufacturers_raw)

        docs_raw = parsed.get("documentation") or []
        docs = [
            d for d in docs_raw
            if isinstance(d, dict)
            and (d.get("title") or "").strip()
            and not _is_placeholder_value(d.get("title"))
        ]

        summary = (parsed.get("summary") or "").strip()
        if _is_placeholder_value(summary):
            summary = ""

        logger.info("Parsed %d manufacturers, %d docs (after filter)", len(manufacturers), len(docs))
        return {
            "manufacturers": manufacturers,
            "documentation": docs,
            "summary": summary,
        }
    except Exception as e:
        logger.error("Failed to parse LLM JSON object response: %s\nRaw: %s", e, raw[:1000])
        return empty


async def _call_ollama(prompt: str, expected_format: str = "json") -> str | None:
    """
    Выполняет запрос к Ollama API.

    `format="json"` — нативный JSON-mode Ollama: модель гарантированно вернёт
    валидный JSON, что заметно снижает шанс «пурги» и копирования плейсхолдеров.
    Передавай `expected_format=""` если JSON не нужен.
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    model = settings.OLLAMA_SEARCH_MODEL
    logger.info("Calling Ollama at %s with model %s (format=%r)", url, model, expected_format)

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Низкая температура для structured output — меньше галлюцинаций и копирования.
        "options": {"temperature": 0.1, "num_predict": 1500},
    }
    if expected_format:
        payload["format"] = expected_format

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)

        logger.info("Ollama response status: %d", response.status_code)

        if response.status_code != 200:
            logger.error("Ollama error: status=%d body=%s", response.status_code, response.text[:500])
            return None

        response_json = response.json()
        result = response_json.get("response", "").strip()
        if not result:
            logger.warning("Ollama returned empty 'response' field. Full json keys: %s", list(response_json.keys()))
        return result

    except httpx.ConnectError as e:
        logger.error("Cannot connect to Ollama at %s: %s", url, e)
        raise RuntimeError(f"Не удалось подключиться к Ollama ({settings.OLLAMA_BASE_URL}). Убедитесь, что Ollama запущен.") from e
    except httpx.TimeoutException as e:
        logger.error("Ollama request timed out: %s", e)
        raise RuntimeError("Запрос к Ollama превысил время ожидания (120 сек). Попробуйте позже.") from e
    except Exception as e:
        logger.error("Unexpected error calling Ollama: %s", e, exc_info=True)
        raise RuntimeError(f"Ошибка при обращении к Ollama: {str(e)}") from e


def _extract_json(text: str) -> Any:
    """Извлекает JSON из текста, убирая markdown-обёртки."""
    # Убрать markdown code block
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")

    # Попробовать найти JSON-массив или объект
    for pattern in [r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"]:
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    return json.loads(cleaned)
