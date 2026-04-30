"""Утилиты нормализации чисел, не зависящие от SQLAlchemy/Pydantic."""
from __future__ import annotations

import re
from typing import Any


def to_float(value: Any) -> float | None:
    """
    Нормализует значение к float.

    Корректно обрабатывает:
        * неразрывные пробелы (`\\xa0`) как разделитель тысяч;
        * обычные пробелы;
        * запятую как десятичный разделитель (русский формат: `1 619 312,79`);
        * смешанные точки и запятые.
    Возвращает None, если значение пустое или не распарсилось.
    """
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


def normalize_text(value: str | None) -> str:
    """
    Нормализует текст для сопоставления:
        * lower-case;
        * `ё` → `е`;
        * удаление спецсимволов (остаются буквы/цифры/пробелы);
        * схлопывание повторных пробелов.
    """
    normalized = (value or "").lower()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
