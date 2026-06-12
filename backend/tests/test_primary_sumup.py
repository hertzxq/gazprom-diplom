"""Unit-тесты сборки первичного свода (Задача 2)."""
from datetime import date

import pytest

from app.services.primary_sumup import build_primary_sumup, SumupRow
from app.services.registry_parser import PaymentRow, ContractRow
from app.services.smsp_classifier import ClassifierRule


@pytest.fixture
def rules():
    return [
        ClassifierRule("авиа",    ["воздушн", "авиац", "авиа"],              "р",  10),
        ClassifierRule("страх",   ["страхов", "финансов", "банковск", "лизинг"], "д",  20),
        ClassifierRule("образов", ["образоват", "обучен"],                   "ц",  30),
        ClassifierRule("аренда",  ["аренд", "недвижим"],                     "л",  40),
        ClassifierRule("почта",   ["почтов", "связ"],                        None, 50),
    ]


def _payment(**kw) -> PaymentRow:
    defaults = dict(
        row_index=0,
        payment_date=date(2026, 1, 15),
        contragent="ООО Ромашка",
        contract_number="DOG-001",
        contract_date=date(2026, 1, 10),
        contract_sum=100_000.0,
        payment_sum=10_000.0,
        currency="RUB",
        smsp_type="",
        smsp_purchase="",
        has_multi_payments=False,
    )
    defaults.update(kw)
    return PaymentRow(**defaults)


def _contract(**kw) -> ContractRow:
    defaults = dict(
        row_index=0,
        vid="Договор",
        number="DOG-001",
        conclusion_date=date(2026, 1, 10),
        contract_sum=100_000.0,
        purchase_method="ЕП",
        smsp_type="",
        smsp_purchase="Нет",
        exclusion_from_smsp="Не является исключением",
        action_from=date(2026, 1, 15),
        action_to=date(2026, 12, 31),
        contragent="ООО Ромашка",
    )
    defaults.update(kw)
    return ContractRow(**defaults)


class TestGrouping:
    def test_single_payment(self, rules):
        rows = build_primary_sumup([_payment()], [], rules)
        assert len(rows) == 1
        assert rows[0].payment_sum == pytest.approx(10_000.0)
        assert rows[0].payments_count == 1
        assert rows[0].has_contract_match is False

    def test_multiple_payments_grouped(self, rules):
        """3 платежа по одному договору (одинаковый номер/дата/контрагент) → 1 строка."""
        payments = [
            _payment(payment_date=date(2026, 1, 15), payment_sum=5000),
            _payment(payment_date=date(2026, 2, 15), payment_sum=7000),
            _payment(payment_date=date(2026, 3, 15), payment_sum=3000),
        ]
        rows = build_primary_sumup(payments, [], rules)
        assert len(rows) == 1
        assert rows[0].payment_sum == pytest.approx(15_000.0)
        assert rows[0].payments_count == 3
        assert rows[0].date == date(2026, 1, 15)  # минимальная

    def test_different_contracts_not_grouped(self, rules):
        payments = [
            _payment(contract_number="A-1"),
            _payment(contract_number="A-2"),
        ]
        rows = build_primary_sumup(payments, [], rules)
        assert len(rows) == 2


class TestContractLookup:
    def test_match_by_exact_key(self, rules):
        """Платёж и договор с одинаковым (номер, дата, контрагент) → сопоставление."""
        p = _payment(contract_number="DOG-001", contract_date=date(2026, 1, 10), contragent="ООО А")
        c = _contract(number="DOG-001", conclusion_date=date(2026, 1, 10), contragent="ООО А",
                      purchase_method="МИ", smsp_type="Малое", smsp_purchase="Да")
        rows = build_primary_sumup([p], [c], rules)
        assert len(rows) == 1
        assert rows[0].has_contract_match is True
        assert rows[0].purchase_method == "МИ"
        assert rows[0].smsp_type == "Малое"
        assert rows[0].smsp_purchase == "Да"

    def test_match_soft_fallback_by_number_and_contragent(self, rules):
        """Если даты не совпадают, но номер+контрагент — fallback-сопоставление."""
        p = _payment(contract_number="DOG-001", contract_date=date(2026, 1, 15), contragent="ООО А")
        c = _contract(number="DOG-001", conclusion_date=date(2026, 1, 10), contragent="ООО А")
        rows = build_primary_sumup([p], [c], rules)
        assert rows[0].has_contract_match is True

    def test_no_match_empty_columns(self, rules):
        """Если договора нет в реестре — I/J/K/L остаются пустыми."""
        p = _payment(contract_number="UNKNOWN-001")
        rows = build_primary_sumup([p], [], rules)
        assert rows[0].has_contract_match is False
        assert rows[0].purchase_method == ""
        assert rows[0].exclusion_category == "нет"
        assert rows[0].action_from is None


class TestClassification:
    def test_rental_category_sets_publication_no(self, rules):
        c = _contract(
            exclusion_from_smsp="л) закупки, предметом которых является аренда",
            contract_sum=10_000_000.0,
        )
        rows = build_primary_sumup([_payment()], [c], rules)
        assert rows[0].exclusion_category == "аренда"
        assert rows[0].publication == "нет"

    def test_small_ep_not_smsp_not_published(self, rules):
        p = _payment(contract_number="A", contract_date=None)
        c = _contract(number="A", conclusion_date=None,
                      contract_sum=50_000.0, purchase_method="ЕП",
                      smsp_purchase="Нет", exclusion_from_smsp="Не является исключением")
        rows = build_primary_sumup([p], [c], rules)
        # сумма из договора < 100т.р., ЕП, не СМСП → нет публикации
        assert rows[0].publication == "нет"

    def test_is_continuing_when_years_differ(self, rules):
        c = _contract(
            action_from=date(2025, 6, 1),
            action_to=date(2026, 6, 1),
        )
        rows = build_primary_sumup([_payment()], [c], rules)
        assert rows[0].is_continuing == "да"


class TestPeriodFilter:
    """E2: фильтр по периоду расчёта."""

    def test_date_from_drops_earlier_payments(self, rules):
        payments = [
            _payment(contract_number="A", payment_date=date(2025, 12, 1), payment_sum=1000),
            _payment(contract_number="A", payment_date=date(2026, 1, 15), payment_sum=2000),
            _payment(contract_number="A", payment_date=date(2026, 6, 1), payment_sum=3000),
        ]
        rows = build_primary_sumup(payments, [], rules, date_from=date(2026, 1, 1))
        assert len(rows) == 1
        assert rows[0].payment_sum == 5000.0

    def test_date_to_drops_later_payments(self, rules):
        payments = [
            _payment(contract_number="A", payment_date=date(2026, 1, 1), payment_sum=1000),
            _payment(contract_number="A", payment_date=date(2026, 6, 1), payment_sum=2000),
            _payment(contract_number="A", payment_date=date(2027, 1, 1), payment_sum=3000),
        ]
        rows = build_primary_sumup(payments, [], rules, date_to=date(2026, 12, 31))
        assert rows[0].payment_sum == 3000.0

    def test_date_range_filters_both_ends(self, rules):
        payments = [
            _payment(contract_number="A", payment_date=date(2025, 6, 1), payment_sum=1000),
            _payment(contract_number="A", payment_date=date(2026, 3, 15), payment_sum=2000),
            _payment(contract_number="A", payment_date=date(2027, 6, 1), payment_sum=3000),
        ]
        rows = build_primary_sumup(
            payments, [], rules,
            date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
        )
        assert rows[0].payment_sum == 2000.0

    def test_payments_without_date_dropped_when_filter_active(self, rules):
        payments = [
            _payment(contract_number="A", payment_date=None, payment_sum=999),
            _payment(contract_number="A", payment_date=date(2026, 6, 1), payment_sum=1000),
        ]
        rows = build_primary_sumup(payments, [], rules, date_from=date(2026, 1, 1))
        assert rows[0].payment_sum == 1000.0


class TestMinAmountFilter:
    """E3: пороговое значение по сумме платежей."""

    def test_groups_below_threshold_dropped(self, rules):
        payments = [
            _payment(contract_number="A", payment_sum=500),
            _payment(contract_number="B", payment_sum=5000),
        ]
        rows = build_primary_sumup(payments, [], rules, min_amount=1000)
        assert len(rows) == 1
        assert rows[0].contract_number == "B"

    def test_threshold_zero_disabled(self, rules):
        payments = [_payment(contract_number="A", payment_sum=10)]
        rows = build_primary_sumup(payments, [], rules, min_amount=0)
        assert len(rows) == 1


class TestSumupRowSerialization:
    def test_to_dict_dates_iso(self):
        row = SumupRow(
            date=date(2026, 1, 15),
            contragent="ООО А",
            contract_number="001",
            contract_date=date(2026, 1, 10),
            contract_sum=100_000.0,
            payment_sum=50_000.0,
            smsp_type="Малое",
            smsp_purchase="Да",
            purchase_method="МИ",
            exclusion_category="нет",
            action_from=date(2026, 1, 1),
            action_to=date(2026, 12, 31),
            is_continuing="нет",
            counter=1,
            publication="да",
            payments_count=1,
            has_contract_match=True,
        )
        d = row.to_dict()
        assert d["date"] == "2026-01-15"
        assert d["contract_date"] == "2026-01-10"
        assert d["action_from"] == "2026-01-01"
        assert d["action_to"] == "2026-12-31"
        assert d["payment_sum"] == 50_000.0
