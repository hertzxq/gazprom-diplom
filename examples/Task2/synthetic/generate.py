"""
Генерирует синтетические реестры для ручного прогона Задачи 2.

Создаёт два xlsx-файла в том же каталоге:
    payment_registry_synthetic.xlsx    — ~120 платежей
    contract_registry_synthetic.xlsx   — 60 договоров с разнообразием категорий

Состав реестра договоров (всего 60):
    *  5 — аренда (J=аренда, публикация=нет)
    *  4 — авиаперевозки (J=авиа)
    *  4 — финансовые/страховые (J=страх)
    *  4 — образовательные (J=образов)
    *  4 — связь / почта (J=почта)
    *  5 — Только для СМСП — Среднее (H=Да, G=Среднее)
    *  6 — Только для СМСП — Малое (H=Да, G=Малое)
    *  5 — Только для СМСП — Микро (H=Да, G=Микро)
    *  5 — С СМСП для всех — Малое (H=Нет, G=Малое)
    *  5 — С СМСП для всех — Микро (H=Нет, G=Микро)
    *  8 — Обычные не-СМСП ЕП крупные
    *  4 — Мелкие не-СМСП (< 100к, не публ.)
    *  3 — Длящиеся (даты из разных лет)
    *  3 — Валютные (USD/EUR)

Особенности платежей:
    * 1–3 платежа на каждый договор (~100 платежей)
    * 4 платежа с множественной суммой через `;` (NBSP в качестве разделителя тысяч)
    * 5 валютных платежей с заполненной AJ
    * 5 платежей по контрагентам, которых нет в реестре
    * 3 платежа с датой раньше начала года (для проверки фильтра date_from)
"""
from datetime import date
from pathlib import Path

import openpyxl


HERE = Path(__file__).parent

PAYMENT_HEADERS = {
    "A": "Вложения", "B": "Важный", "C": "Сейчас у", "D": "Вид",
    "E": "Номер", "F": "Дата", "G": "Контрагент", "H": "Номер договора",
    "I": "Дата договора", "J": "Сумма по договору", "K": "Сумма платежа",
    "L": "Комментарий", "M": "Вид СМСП", "N": "Закупка для СМСП",
    "O": "Валюта по договору", "P": "Тек. процесс", "Q": "Состояние",
    "R": "Сумма", "S": "Исполнен", "T": "Ответственное лицо", "U": "Исполнитель",
    "AJ": "Сумма в рублях для валютных платежей", "AK": "Валюта платежа",
}

CONTRACT_HEADERS = {
    "A": "Вид", "B": "Номер", "C": "Дата заключения",
    "D": "Предмет для ПУР", "E": "Сумма с НДС", "F": "Вид закупки",
    "G": "Вид СМСП", "H": "Закупка для СМСП", "I": "Номер ПП",
    "J": "Количество участников", "K": "Внутренний реестровый номер",
    "L": "Сумма из АСЭЗ", "M": "Сумма по факту", "N": "Исключение из СМСП",
    "O": "Валюта", "AL": "Исполнение с", "AM": "Исполнение по",
    "BM": "Контрагенты",
}


# ─── Тексты исключений (полные формулировки из ПП РФ 1352) ─────────────

EXCL_AVIA = "р) закупки услуг в области воздушных перевозок и авиационных работ"
EXCL_INS = "д) закупки финансовых услуг, включая страховые услуги"
EXCL_EDU = "ц) закупки услуг образовательных организаций"
EXCL_RENT = "л) закупки, предметом которых является аренда и (или) приобретение в собственность объектов недвижимого имущества"
EXCL_POST = "х) закупки услуг подвижной радиотелефонной связи и услуг почтовой связи"
EXCL_NONE = "Не является исключением"


# ─── Сборка договоров через шаблоны ────────────────────────────────────


CONTRACTS: list[tuple] = []  # (номер, дата, сумма, способ, СМСП, закупка_для_СМСП, исключ., с, по, контрагент)


def _add(prefix: str, idx: int, dt: date, sum_: float, method: str, smsp_type: str,
         smsp_purchase: str, excl: str, action_from: date, action_to: date, contragent: str) -> None:
    CONTRACTS.append((
        f"DOG-{prefix}-{idx:02d}", dt, sum_, method, smsp_type, smsp_purchase, excl,
        action_from, action_to, contragent,
    ))


# Аренда (5)
_rent_contragents = [
    "ООО «Недвижимость Плюс»",
    "АО «Бизнес-Парк Северный»",
    "ООО «Городские Площади»",
    "ЗАО «Офис Инвест»",
    "ООО «АльфаРент»",
]
for i, contragent in enumerate(_rent_contragents, start=1):
    _add("ARND", i,
         date(2026, 1, 5 + i), 800_000 + i * 250_000, "ЕП", "нет", "Нет",
         EXCL_RENT,
         date(2026, 1, 15 + i), date(2026, 12, 31),
         contragent)

# Авиа (4)
_avia_contragents = [
    "АО «Авиакомпания Лидер»",
    "ПАО «Аэрофлот»",
    "ООО «Сибирские Авиалинии»",
    "АО «Уральские Перевозки»",
]
for i, contragent in enumerate(_avia_contragents, start=1):
    _add("AVIA", i,
         date(2026, 2, i * 2), 1_500_000 + i * 600_000, "ЕП", "нет", "Нет",
         EXCL_AVIA,
         date(2026, 2, i * 2 + 5), date(2026, 12, 31),
         contragent)

# Страх (4)
_ins_contragents = [
    "АО СК «Надёжный Полис»",
    "ООО СК «РосГарантия»",
    "АО «АльфаСтрахование»",
    "ООО «Финансовый Партнёр»",
]
for i, contragent in enumerate(_ins_contragents, start=1):
    _add("INS", i,
         date(2026, 3, i * 2), 600_000 + i * 200_000, "ЕП", "нет", "Нет",
         EXCL_INS,
         date(2026, 3, i * 2 + 5), date(2026, 12, 31),
         contragent)

# Образование (4)
_edu_contragents = [
    "АНО ДПО «Учебный Центр»",
    "ООО «Корпоративный Университет»",
    "ФГБОУ ВО «Технический Институт»",
    "ООО «Бизнес-Школа Лидер»",
]
for i, contragent in enumerate(_edu_contragents, start=1):
    _add("EDU", i,
         date(2026, 2, 10 + i * 2), 200_000 + i * 80_000, "ЕП", "нет", "Нет",
         EXCL_EDU,
         date(2026, 3, 1 + i), date(2026, 6, 30),
         contragent)

# Почта/связь (4)
_post_contragents = [
    "ПАО «Связной Оператор»",
    "АО «МегаСвязь»",
    "ФГУП «Почта России»",
    "ООО «Логистик Экспресс»",
]
for i, contragent in enumerate(_post_contragents, start=1):
    _add("POST", i,
         date(2026, 1, 8 + i * 2), 120_000 + i * 50_000, "ЕП", "нет", "Нет",
         EXCL_POST,
         date(2026, 1, 15 + i), date(2026, 12, 31),
         contragent)

# Только для СМСП — Среднее (5)
_smsp_med_contragents = [
    "ООО «Средний Партнёр»",
    "АО «Среднеотраслевые Решения»",
    "ООО «БетаПром»",
    "АО «ГаммаЛогистик»",
    "ООО «Дельта-Консалтинг»",
]
for i, contragent in enumerate(_smsp_med_contragents, start=1):
    _add("SMSP-MED", i,
         date(2026, 2, i * 3), 5_000_000 + i * 1_500_000, "КИМ", "Среднее", "Да",
         EXCL_NONE,
         date(2026, 2, i * 3 + 5), date(2026, 12, 31),
         contragent)

# Только для СМСП — Малое (6)
_smsp_small_contragents = [
    "ООО «Малый Поставщик»",
    "ООО «Эпсилон-Сервис»",
    "ООО «Зета-Сетевик»",
    "ООО «Эта-Решения»",
    "ООО «Тета-Партнёр»",
    "ООО «Йота-Логистика»",
]
for i, contragent in enumerate(_smsp_small_contragents, start=1):
    _add("SMSP-SMALL", i,
         date(2026, 3, i * 2), 2_000_000 + i * 600_000, "КИМ", "Малое", "Да",
         EXCL_NONE,
         date(2026, 3, i * 2 + 5), date(2026, 9, 30),
         contragent)

# Только для СМСП — Микро (5)
_smsp_micro_contragents = [
    "ИП Иванов А.А.",
    "ИП Смирнов В.К.",
    "ООО «Каппа-Сервис»",
    "ИП Кузнецов Д.С.",
    "ООО «Лямбда-Микро»",
]
for i, contragent in enumerate(_smsp_micro_contragents, start=1):
    _add("SMSP-MICRO", i,
         date(2026, 4, i * 2), 350_000 + i * 100_000, "ЕП", "Микро", "Да",
         EXCL_NONE,
         date(2026, 4, i * 2 + 5), date(2026, 10, 31),
         contragent)

# С СМСП для всех — Малое (5)
_with_smsp_small_contragents = [
    "ООО «Сигма-Технология»",
    "ООО «Тау-Сервис»",
    "ООО «Ипсилон-Поставка»",
    "ООО «Фи-Логистик»",
    "ООО «Хи-Решения»",
]
for i, contragent in enumerate(_with_smsp_small_contragents, start=1):
    _add("WITH-SMALL", i,
         date(2026, 4, i * 3), 800_000 + i * 200_000, "ЕП", "Малое", "Нет",
         EXCL_NONE,
         date(2026, 4, i * 3 + 3), date(2026, 12, 31),
         contragent)

# С СМСП для всех — Микро (5)
_with_smsp_micro_contragents = [
    "ИП Петров И.С.",
    "ИП Орлов М.В.",
    "ООО «Пси-Микропоставка»",
    "ИП Соколов А.Н.",
    "ИП Васильев Е.П.",
]
for i, contragent in enumerate(_with_smsp_micro_contragents, start=1):
    _add("WITH-MICRO", i,
         date(2026, 5, i * 2), 250_000 + i * 80_000, "ЕП", "Микро", "Нет",
         EXCL_NONE,
         date(2026, 5, i * 2 + 3), date(2026, 11, 30),
         contragent)

# Обычные не-СМСП ЕП крупные (8)
_reg_contragents = [
    "ООО «Общий Поставщик»",
    "АО «Стандарт-Сервис»",
    "ООО «РосТехОборудование»",
    "АО «ИндустриалПром»",
    "ООО «МегаСнаб»",
    "АО «Универсал-Логистик»",
    "ООО «Промторг»",
    "АО «БизнесЛидер»",
]
for i, contragent in enumerate(_reg_contragents, start=1):
    _add("REG", i,
         date(2026, 1, 10 + i * 2), 500_000 + i * 250_000, "ЕП", "нет", "Нет",
         EXCL_NONE,
         date(2026, 2, i + 1), date(2026, 12, 31),
         contragent)

# Мелкие не-СМСП (< 100к, не публикуются — O=нет на платежах) (4)
_small_contragents = [
    "ООО «Копеечный Сервис»",
    "ИП Михайлов В.С.",
    "ООО «Малая Поставка»",
    "ИП Захаров А.Ю.",
]
for i, contragent in enumerate(_small_contragents, start=1):
    _add("SMALL", i,
         date(2026, 2, 5 + i * 3), 30_000 + i * 15_000, "ЕП", "нет", "Нет",
         EXCL_NONE,
         date(2026, 2, 10 + i * 3), date(2026, 4, 30),
         contragent)

# Длящиеся (3) — даты из разных лет
_cont_contragents = [
    "ООО «Длящийся Сервис»",
    "АО «Многолетние Поставки»",
    "ООО «Долгосрочный Партнёр»",
]
for i, contragent in enumerate(_cont_contragents, start=1):
    _add("CONT", i,
         date(2025, 11, i * 5), 400_000 + i * 150_000, "ЕП", "Микро", "Нет",
         EXCL_NONE,
         date(2025, 12, i + 1), date(2027, i + 1, 28),
         contragent)

# Валютные (3)
_for_contragents = [
    ("ForeignCorp Ltd",  "USD"),
    ("EuroSupply GmbH",  "EUR"),
    ("Asia Trading Co.", "USD"),
]
for i, (contragent, currency) in enumerate(_for_contragents, start=1):
    _add("FRGN", i,
         date(2026, 1, i * 5), 300_000 + i * 200_000, "ЕП", "нет", "Нет",
         EXCL_NONE,
         date(2026, 1, i * 5 + 5), date(2026, 12, 31),
         contragent)


# ─── Платежи ──────────────────────────────────────────────────────────


PAYMENTS: list[dict] = []


def add(contract_num: str, contract_dt: date, contragent: str, currency: str,
        payments: list[tuple[date, str]], sum_rub_override: str | None = None) -> None:
    """Добавляет платежи по договору (1+ платежей)."""
    for pay_date, pay_amount in payments:
        PAYMENTS.append({
            "D": "Платеж",
            "F": pay_date,
            "G": contragent,
            "H": contract_num,
            "I": contract_dt,
            "K": pay_amount,
            "M": "", "N": "",
            "O": currency,
            "AJ": sum_rub_override,
            "AK": currency,
        })


# Хелпер: формат суммы с NBSP (как Excel экспортирует тысячи).
def _amt(value: int | float, decimals: bool = False) -> str:
    if decimals:
        whole = int(value)
        frac = int(round((value - whole) * 100))
        s = f"{whole:,}".replace(",", "\xa0")
        return f"{s},{frac:02d}"
    return f"{int(value):,}".replace(",", "\xa0")


# По всем 60 договорам — генерируем по 1–3 платежа автоматически.
import random
random.seed(42)

for c in CONTRACTS:
    (num, dt, sum_, method, smsp_type, smsp_purchase, excl, a_from, a_to, contragent) = c
    # 1–3 платежа на договор; общая сумма ≈ contract_sum
    n_payments = random.choice([1, 2, 2, 3])
    base_amount = sum_ / n_payments

    # Валюта по договору — для FRGN-* платежи в валюте, для остальных в RUB
    currency = "RUB"
    if num.startswith("DOG-FRGN-"):
        currency = "USD" if num.endswith(("-01", "-03")) else "EUR"

    # Дата платежа — после даты заключения, в пределах action_from..action_to
    start_month = max(a_from.month, dt.month)
    payments = []
    for i in range(n_payments):
        # Распределяем по месяцам внутри периода действия
        m = (start_month + i + 1) % 12 or 12
        y = a_from.year if m >= a_from.month else a_from.year + 1
        if y > a_to.year:
            y = a_to.year
        # День — 1, 5, 10, 15, 20, 25 — псевдослучайно
        d = [1, 5, 10, 15, 20, 25][i % 6]
        pay_date = date(y, m, d)
        # Округляем до сотен — реалистично для платёжек
        amount = round(base_amount + random.randint(-50_000, 50_000), -2)
        if amount < 1000:
            amount = 1000
        payments.append((pay_date, _amt(amount)))

    sum_rub_override = None
    if currency != "RUB":
        # Для валютных платежей — суммируем эквивалент в рублях (×80 для USD, ×90 для EUR)
        rate = 80 if currency == "USD" else 90
        rub_total = round(sum_ * rate / n_payments, -2)
        sum_rub_override = _amt(rub_total)

    add(num, dt, contragent, currency, payments, sum_rub_override=sum_rub_override)


# ─── Дополнительные «специальные» платежи (особые случаи) ──────────────

# 1. Платежи с множественной суммой через `;` (4 шт.)
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 3, 15),
    "G": "ПАО «Связной Оператор»",
    "H": "DOG-POST-01", "I": date(2026, 1, 10),
    "K": "45\xa0000; 35\xa0000",
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 4, 20),
    "G": "ООО «Общий Поставщик»",
    "H": "DOG-REG-01", "I": date(2026, 1, 12),
    "K": "125\xa0000; 75\xa0000; 50\xa0000",
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 5, 10),
    "G": "ООО «Малый Поставщик»",
    "H": "DOG-SMSP-SMALL-01", "I": date(2026, 3, 2),
    "K": "200\xa0000; 200\xa0000",
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 6, 5),
    "G": "ИП Иванов А.А.",
    "H": "DOG-SMSP-MICRO-01", "I": date(2026, 4, 2),
    "K": "120\xa0000; 80\xa0000",
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})

# 2. Платежи в валюте с заполненной AJ (5 шт.)
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 3, 18),
    "G": "ForeignCorp Ltd",
    "H": "DOG-FRGN-01", "I": date(2026, 1, 5),
    "K": "5\xa0000",
    "M": "", "N": "", "O": "USD", "AJ": "400\xa0000,00", "AK": "USD",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 5, 12),
    "G": "EuroSupply GmbH",
    "H": "DOG-FRGN-02", "I": date(2026, 1, 10),
    "K": "8\xa0500",
    "M": "", "N": "", "O": "EUR", "AJ": "765\xa0000,00", "AK": "EUR",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 7, 1),
    "G": "Asia Trading Co.",
    "H": "DOG-FRGN-03", "I": date(2026, 1, 15),
    "K": "3\xa0200",
    "M": "", "N": "", "O": "USD", "AJ": "256\xa0000,00", "AK": "USD",
})

# 3. Платежи без договора в реестре (5 шт.)
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 4, 5),
    "G": "ООО «Неопознанный Поставщик»",
    "H": "UNKNOWN-001", "I": date(2026, 3, 15),
    "K": _amt(123_456, decimals=False),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 5, 20),
    "G": "ИП Незаключённый",
    "H": "ORPHAN-002", "I": date(2026, 4, 10),
    "K": _amt(85_000),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 6, 18),
    "G": "ООО «Неизвестный Контрагент»",
    "H": "MISSING-003", "I": date(2026, 5, 25),
    "K": _amt(450_000),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 7, 12),
    "G": "ИП Иванов Бесконтрактный",
    "H": "NOREG-004", "I": date(2026, 6, 1),
    "K": _amt(67_300),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2026, 8, 5),
    "G": "ООО «Внешний Поставщик»",
    "H": "EXTERNAL-005", "I": date(2026, 7, 10),
    "K": _amt(312_500, decimals=True),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})

# 4. Платежи с датой раньше 2026-01-01 (3 шт., для проверки фильтра date_from)
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2025, 11, 20),
    "G": "ООО «Длящийся Сервис»",
    "H": "DOG-CONT-01", "I": date(2025, 11, 5),
    "K": _amt(150_000),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2025, 12, 15),
    "G": "АО «Многолетние Поставки»",
    "H": "DOG-CONT-02", "I": date(2025, 11, 10),
    "K": _amt(200_000),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})
PAYMENTS.append({
    "D": "Платеж",
    "F": date(2025, 12, 28),
    "G": "ООО «Долгосрочный Партнёр»",
    "H": "DOG-CONT-03", "I": date(2025, 11, 15),
    "K": _amt(300_000),
    "M": "", "N": "", "O": "RUB", "AJ": None, "AK": "RUB",
})


# ─── Запись xlsx ──────────────────────────────────────────────────────


def _col_idx(letter: str) -> int:
    idx = 0
    for ch in letter.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def write_xlsx(path: Path, headers: dict[str, str], rows: list[dict], title_row_a: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Export"
    ws.cell(row=1, column=1, value=title_row_a)
    # Шапка в 3-й строке
    for letter, name in headers.items():
        ws.cell(row=3, column=_col_idx(letter), value=name)
    for i, row in enumerate(rows, start=4):
        for letter, value in row.items():
            ws.cell(row=i, column=_col_idx(letter), value=value)
    wb.save(str(path))
    wb.close()


def contract_rows() -> list[dict]:
    rows = []
    for (num, dt, sum_, meth, smsp_type, smsp_purch, excl, a_from, a_to, con) in CONTRACTS:
        currency = "RUB"
        if num.startswith("DOG-FRGN-"):
            currency = "USD" if num.endswith(("-01", "-03")) else "EUR"
        rows.append({
            "A": "Договор",
            "B": num,
            "C": dt,
            "D": "Поставка/услуги (синтетические данные)",
            "E": sum_,
            "F": meth,
            "G": smsp_type,
            "H": smsp_purch,
            "N": excl,
            "O": currency,
            "AL": a_from,
            "AM": a_to,
            "BM": con,
        })
    return rows


if __name__ == "__main__":
    p_path = HERE / "payment_registry_synthetic.xlsx"
    c_path = HERE / "contract_registry_synthetic.xlsx"
    write_xlsx(p_path, PAYMENT_HEADERS, PAYMENTS, "Бух. документы")
    write_xlsx(c_path, CONTRACT_HEADERS, contract_rows(), "Договоры")
    print("Создано:")
    print(f"  {p_path}  ({len(PAYMENTS)} платежей)")
    print(f"  {c_path}  ({len(CONTRACTS)} договоров)")
