"""
Классификатор исключений СМСП и правила для столбцов M, O первичного свода.

Входы:
    * текст из столбца «Исключение из СМСП» реестра договоров (N) — длинная
      формулировка пункта (например, «л) закупки, предметом которых является аренда…»)
      или «Не является исключением».
    * список SmspExclusionRule из БД (category, keywords, point_letter).

Выход:
    * короткая метка категории (`"авиа"`, `"аренда"`, `"почта"`, …) или `"нет"`
      если ни одно правило не сработало.

Другие чистые функции:
    * determine_publication — признак «Публикация на ЕИС».
    * is_continuing — признак «Длящийся».
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.utils.numbers import normalize_text


# Порог суммы договора, ниже которого ЕП-закупка «для не-СМСП» не публикуется
# в ЕИС (см. шапку колонки O в «Первичный свод.xls»).
EIS_THRESHOLD_RUB = 100_000.0


@dataclass(slots=True)
class ClassifierRule:
    """Лёгкая DTO, чтобы классификатор не зависел от SQLAlchemy-модели."""
    category: str
    keywords: list[str]
    point_letter: Optional[str] = None
    order_idx: int = 100
    enabled: bool = True


NOT_AN_EXCLUSION_MARKERS = (
    "не явл",            # «Не является исключением»
)


def classify_exclusion(text: str, rules: list[ClassifierRule]) -> str:
    """
    Маппит формулировку из столбца N реестра договоров на короткую метку.

    Алгоритм:
      1. Если текст явно содержит «не является исключением» или пуст → `"нет"`.
      2. Если текст начинается с буквы пункта (`«л) ...»`, `«р) ...»`, …) —
         пытаемся сопоставить букву с rule.point_letter (приоритетный путь).
      3. Иначе — идём по отсортированным правилам (order_idx ↑) и ищем
         substring-совпадение с любым keyword.
      4. Ни одно не сработало → `"нет"`.
    """
    if not text:
        return "нет"

    normalized = normalize_text(text)
    if any(marker in normalized for marker in NOT_AN_EXCLUSION_MARKERS):
        return "нет"

    active_rules = sorted(
        (r for r in rules if r.enabled),
        key=lambda r: r.order_idx,
    )

    # (2) Проверка по букве пункта — формат «л) ...», «я(1)) ...» и т.п.
    point = _extract_point_letter(text)
    if point is not None:
        for rule in active_rules:
            if rule.point_letter and rule.point_letter.lower() == point.lower():
                return rule.category

    # (3) Substring-совпадение по ключевым словам.
    for rule in active_rules:
        for kw in rule.keywords or []:
            if not kw:
                continue
            if normalize_text(kw) in normalized:
                return rule.category

    return "нет"


def determine_publication(
    *,
    exclusion_category: str,
    contract_sum: Optional[float],
    smsp_purchase: str,
    purchase_method: str,
) -> str:
    """
    Признак «Публикация на ЕИС» для столбца O первичного свода.

    Правило из шапки примера (`examples/Task2/Первичный свод.xls`, ячейка O4):
        Ставим "нет" если:
            * категория = «аренда» (пункт л), независимо от всего остального;
            * ИЛИ (цена договора < 100 т.р.) И (столбец H = «нет») И
              (столбец I/способ закупки = «ЕП»).
        В остальных случаях — «да».
    """
    if _norm(exclusion_category) == "аренда":
        return "нет"

    if (
        contract_sum is not None
        and contract_sum < EIS_THRESHOLD_RUB
        and _norm(smsp_purchase) == "нет"
        and _norm(purchase_method) == "еп"
    ):
        return "нет"

    return "да"


def is_continuing(start: Optional[date], end: Optional[date]) -> str:
    """Столбец M: «да», если даты действия из разных лет. Иначе — «нет»."""
    if start is None or end is None:
        return "нет"
    return "да" if start.year != end.year else "нет"


# ─── Helpers ───────────────────────────────────────────────────────────


def _norm(value: Optional[str]) -> str:
    return normalize_text(value or "")


def _extract_point_letter(text: str) -> Optional[str]:
    """
    Достаёт букву пункта из начала текста: «л)», «я(1))», «р)» и т.п.
    Возвращает `"л"`, `"я(1)"`, `"р"` — регистр-инвариантно.
    """
    s = (text or "").lstrip()
    if not s:
        return None

    # Формат «я(1))» — буква + (цифра)
    if len(s) >= 5 and s[1] == "(" and s[0].isalpha():
        idx = s.find(")", 2)
        if idx != -1:
            # ожидаем после скобки ещё одну закрывающую: «я(1))»
            after = s[idx + 1:idx + 2]
            if after == ")":
                return s[:idx + 1]

    # Формат «л)», «р)», «ю)», «я)»
    if len(s) >= 2 and s[0].isalpha() and s[1] == ")":
        return s[0]

    return None
