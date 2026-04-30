"""
Парсеры реестров платежей и договоров (Задача 2).

В отличие от общего parse_document() из file_parser.py, здесь не используется
автоопределение заголовка — структура реестров фиксированная: третья строка
содержит шапку, данные начинаются с четвёртой. Колонки идентифицируются
по буквенному индексу (A, B, C, …, AA, AB, …), как в Excel.

Почему не через parse_document():
    * В реестре платежей 37 колонок, в реестре договоров 65 — автодетект
      заголовка иногда ловит не ту строку.
    * В поле «Сумма платежа» встречаются записи `51 200; 184 000` (несколько
      платежей в одной строке через `;`, тысячи разделены NBSP). Это нужно
      расщеплять и корректно суммировать.
    * Даты хранятся как float (Excel serial); приводим к datetime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

import openpyxl
import xlrd

from app.utils.numbers import to_float as _to_float


HEADER_ROW_INDEX_1BASED = 3  # третья строка — шапка, данные с четвёртой

# Буквенные индексы колонок реестра платежей (1-based position → letter).
# Ссылки на наименования из шапки (см. examples/Task2/Реестр_платежей.xls, стр. 3).
PAYMENT_COL = {
    "vid":               "D",   # Вид (обычно «Платеж»)
    "date":              "F",   # Дата платежа / приёма
    "contragent":        "G",   # Контрагент
    "contract_number":   "H",   # Номер договора
    "contract_date":     "I",   # Дата договора
    "contract_sum":      "J",   # Сумма по договору
    "payment_sum":       "K",   # Сумма платежа (строкой, может быть `51 200; 184 000`)
    "smsp_type":         "M",   # Вид СМСП
    "smsp_purchase":     "N",   # Закупка для СМСП
    "currency":          "O",   # Валюта по договору
    "payment_amount_rub": "AJ",  # Сумма в рублях для валютных платежей
}

# Буквенные индексы колонок реестра договоров.
CONTRACT_COL = {
    "vid":               "A",  # Вид (Договор / Доп. соглашение)
    "number":            "B",  # Номер договора
    "conclusion_date":   "C",  # Дата заключения
    "contract_sum":      "E",  # Сумма с НДС
    "purchase_method":   "F",  # Вид закупки (ЕП / КИМ / МИ …)
    "smsp_type":         "G",  # Вид СМСП (Малое / Микро / Самозанятый / Нет)
    "smsp_purchase":     "H",  # Закупка для СМСП (Да / Нет)
    "exclusion_from_smsp": "N",  # Исключение из СМСП (длинная формулировка пункта)
    "action_from":       "AL",  # Исполнение с
    "action_to":         "AM",  # Исполнение по
    "contragent":        "BM",  # Контрагенты
}


@dataclass(slots=True)
class PaymentRow:
    row_index: int
    payment_date: Optional[date]
    contragent: str
    contract_number: str
    contract_date: Optional[date]
    contract_sum: Optional[float]
    payment_sum: Optional[float]       # сумма в рублях (с учётом AK для валютных)
    currency: str
    smsp_type: str
    smsp_purchase: str
    has_multi_payments: bool = False   # в поле K через `;` было несколько значений


@dataclass(slots=True)
class ContractRow:
    row_index: int
    vid: str                           # «Договор» или «Дополнительное соглашение»
    number: str
    conclusion_date: Optional[date]
    contract_sum: Optional[float]
    purchase_method: str               # ЕП / КИМ / МИ / …
    smsp_type: str
    smsp_purchase: str
    exclusion_from_smsp: str           # исходный текст (для классификатора)
    action_from: Optional[date]
    action_to: Optional[date]
    contragent: str


# ─── Public API ────────────────────────────────────────────────────────


def parse_payment_registry(file_path: str) -> list[PaymentRow]:
    """Парсит реестр платежей. Возвращает список строк (только `Вид == 'Платеж'`)."""
    grid = _read_grid(file_path)
    rows: list[PaymentRow] = []
    for i, raw in enumerate(grid[HEADER_ROW_INDEX_1BASED:], start=HEADER_ROW_INDEX_1BASED + 1):
        if _is_empty(raw):
            continue
        vid = _as_str(_cell(raw, PAYMENT_COL["vid"]))
        # По ТЗ нас интересуют именно платежи; если строка — не платёж, пропускаем.
        # Поле пустое в шаблонных строках — тоже пропускаем.
        if not vid or vid.lower() != "платеж":
            continue

        currency = _as_str(_cell(raw, PAYMENT_COL["currency"])) or "RUB"
        payment_sum_raw = _cell(raw, PAYMENT_COL["payment_sum"])
        payment_sum_rub_raw = _cell(raw, PAYMENT_COL["payment_amount_rub"])

        # Для валютных платежей берём колонку AK (уже в рублях).
        # Для RUB — колонку K. В обеих — возможны множественные платежи через `;`.
        if currency.upper() != "RUB":
            total, multi = _parse_payment_amount(payment_sum_rub_raw)
            if total is None:
                # fallback: если AK пуст — попробуем K, это всё равно будет в валюте,
                # но хотя бы не потеряем сумму
                total, multi = _parse_payment_amount(payment_sum_raw)
        else:
            total, multi = _parse_payment_amount(payment_sum_raw)

        rows.append(PaymentRow(
            row_index=i,
            payment_date=_to_date(_cell(raw, PAYMENT_COL["date"])),
            contragent=_as_str(_cell(raw, PAYMENT_COL["contragent"])),
            contract_number=_as_str(_cell(raw, PAYMENT_COL["contract_number"])),
            contract_date=_to_date(_cell(raw, PAYMENT_COL["contract_date"])),
            contract_sum=_to_float(_cell(raw, PAYMENT_COL["contract_sum"])),
            payment_sum=total,
            currency=currency,
            smsp_type=_as_str(_cell(raw, PAYMENT_COL["smsp_type"])),
            smsp_purchase=_as_str(_cell(raw, PAYMENT_COL["smsp_purchase"])),
            has_multi_payments=multi,
        ))
    return rows


def parse_contract_registry(file_path: str) -> list[ContractRow]:
    """Парсит реестр договоров. Возвращает только строки `Вид == 'Договор'`."""
    grid = _read_grid(file_path)
    rows: list[ContractRow] = []
    for i, raw in enumerate(grid[HEADER_ROW_INDEX_1BASED:], start=HEADER_ROW_INDEX_1BASED + 1):
        if _is_empty(raw):
            continue
        vid = _as_str(_cell(raw, CONTRACT_COL["vid"]))
        if vid.lower() != "договор":
            # «Дополнительное соглашение» и прочие в первичный свод не попадают:
            # они меняют условия основного договора, не создают отдельной сущности.
            continue

        rows.append(ContractRow(
            row_index=i,
            vid=vid,
            number=_as_str(_cell(raw, CONTRACT_COL["number"])),
            conclusion_date=_to_date(_cell(raw, CONTRACT_COL["conclusion_date"])),
            contract_sum=_to_float(_cell(raw, CONTRACT_COL["contract_sum"])),
            purchase_method=_as_str(_cell(raw, CONTRACT_COL["purchase_method"])),
            smsp_type=_as_str(_cell(raw, CONTRACT_COL["smsp_type"])),
            smsp_purchase=_as_str(_cell(raw, CONTRACT_COL["smsp_purchase"])),
            exclusion_from_smsp=_as_str(_cell(raw, CONTRACT_COL["exclusion_from_smsp"])),
            action_from=_to_date(_cell(raw, CONTRACT_COL["action_from"])),
            action_to=_to_date(_cell(raw, CONTRACT_COL["action_to"])),
            contragent=_as_str(_cell(raw, CONTRACT_COL["contragent"])),
        ))
    return rows


# ─── Helpers ───────────────────────────────────────────────────────────


def _read_grid(file_path: str) -> list[list[Any]]:
    """Читает файл в плоскую матрицу. Даты сохраняются как datetime/date, не как float."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return _read_xlsx(path)
    if ext == ".xls":
        return _read_xls(path)
    raise ValueError(f"Неподдерживаемый формат реестра: {ext}")


def _read_xlsx(path: Path) -> list[list[Any]]:
    wb = openpyxl.load_workbook(str(path), data_only=True)
    try:
        ws = wb.active
        grid = [list(row) for row in ws.iter_rows(values_only=True)]
        return grid
    finally:
        wb.close()


def _read_xls(path: Path) -> list[list[Any]]:
    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)
    grid: list[list[Any]] = []
    for r in range(ws.nrows):
        row: list[Any] = []
        for c in range(ws.ncols):
            cell = ws.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_DATE:
                try:
                    row.append(xlrd.xldate_as_datetime(cell.value, wb.datemode))
                except Exception:
                    row.append(cell.value)
            elif cell.ctype == xlrd.XL_CELL_EMPTY:
                row.append(None)
            else:
                row.append(cell.value)
        grid.append(row)
    return grid


def _col_letter_to_index(letter: str) -> int:
    """'A' → 0, 'Z' → 25, 'AA' → 26, 'BM' → 64, …"""
    idx = 0
    for ch in letter.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _cell(row: list[Any], letter: str) -> Any:
    idx = _col_letter_to_index(letter)
    if idx >= len(row):
        return None
    return row[idx]


def _is_empty(row: list[Any]) -> bool:
    return all(cell is None or (isinstance(cell, str) and not cell.strip()) for cell in row)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _to_date(value: Any) -> Optional[date]:
    """Нормализует значение к date. Принимает: datetime, date, float (Excel serial), str."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return xlrd.xldate_as_datetime(float(value), 0).date()
        except Exception:
            return None
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


def _parse_payment_amount(value: Any) -> tuple[Optional[float], bool]:
    """
    Разбирает строку «Сумма платежа». Форматы:
        '8 100'             →  8100.0
        '51 200; 184 000'   →  235200.0   (несколько платежей в одной строке)
        '322 069,36'        →  322069.36
        1619312.79          →  1619312.79
    Возвращает (итог, был_ли_сплит).
    """
    if value is None or value == "":
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False
    s = str(value)
    parts = [p for p in s.split(";") if p.strip()]
    multi = len(parts) > 1
    total = 0.0
    for part in parts:
        amount = _to_float(part)
        if amount is not None:
            total += amount
    if total == 0.0 and not any(_to_float(p) is not None for p in parts):
        return None, multi
    return total, multi
