"""Unit-тесты итогового свода СМСП (3 вкладки, 27 показателей)."""
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from app.services.primary_sumup import SumupRow
from app.services.smsp_summary import (
    generate_final_summary_xlsx,
    compute_final_summary,
    SHEETS,
)


def _row(**kw) -> SumupRow:
    defaults = dict(
        date=date(2026, 1, 1),
        contragent="Test",
        contract_number="001",
        contract_date=date(2026, 1, 1),
        contract_sum=100_000.0,
        payment_sum=10_000.0,
        smsp_type="",
        smsp_purchase="",
        purchase_method="",
        exclusion_category="нет",
        action_from=None,
        action_to=None,
        is_continuing="нет",
        counter=1,
        publication="да",
        payments_count=1,
        has_contract_match=True,
    )
    defaults.update(kw)
    return SumupRow(**defaults)


@pytest.fixture
def sample_rows():
    """
    Набор строк, покрывающий все категории:
        1 x аренда (900k)
        1 x страх, G=Малое (180k)
        1 x образов, G=Микро (250k)
        1 x Только для СМСП среднее (4M)
        1 x Только для СМСП малое (5M)
        1 x С СМСП малое (300k)
        1 x обычная не-СМСП (100k)
        1 x не публ (45k)
    """
    return [
        _row(contragent="Аренда", payment_sum=900_000, exclusion_category="аренда",
             smsp_purchase="нет", publication="нет"),
        _row(contragent="Страх", payment_sum=180_000, exclusion_category="страх",
             smsp_type="Малое", smsp_purchase="нет"),
        _row(contragent="Образ", payment_sum=250_000, exclusion_category="образов",
             smsp_type="Микро", smsp_purchase="нет"),
        _row(contragent="СМСП среднее", payment_sum=4_000_000,
             smsp_type="Среднее", smsp_purchase="да"),
        _row(contragent="СМСП малое", payment_sum=5_000_000,
             smsp_type="Малое", smsp_purchase="да"),
        _row(contragent="С СМСП малое", payment_sum=300_000,
             smsp_type="Микро", smsp_purchase="нет"),
        _row(contragent="Обычный", payment_sum=100_000,
             smsp_type="нет", smsp_purchase="нет"),
        _row(contragent="Мелкий не-публ", payment_sum=45_000,
             smsp_type="нет", smsp_purchase="нет", publication="нет"),
    ]


class TestComputeFinalSummary:
    def test_structure_has_3_sheets(self, sample_rows):
        result = compute_final_summary(sample_rows)
        assert set(result.keys()) == {name for name, _ in SHEETS}

    def test_total_all(self, sample_rows):
        result = compute_final_summary(sample_rows)
        total = _find(result["Итого_платежи_договоры"], "Итого всего")
        assert total["total_sum"] == pytest.approx(10_775_000.0)
        assert total["count"] == 8

    def test_exclusions(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        assert _find(sheet, "Исключение (страх)")["total_sum"] == pytest.approx(180_000)
        assert _find(sheet, "Исключение (образов)")["total_sum"] == pytest.approx(250_000)
        assert _find(sheet, "Исключение (аренда)")["total_sum"] == pytest.approx(900_000)
        assert _find(sheet, "Исключения (авиа)")["total_sum"] == 0

    def test_itogo_minus_exclusions(self, sample_rows):
        """Итого за минусом исключений = всего − Σ 5 категорий."""
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        total = _find(sheet, "Итого всего")["total_sum"]
        excl = sum(_find(sheet, label)["total_sum"] for label in [
            "Исключения (авиа)", "Исключение (страх)", "Исключение (образов)",
            "Исключение (аренда)", "Исключение (почта)",
        ])
        minus = _find(sheet, "Итого за минусом исключений")["total_sum"]
        assert minus == pytest.approx(total - excl)

    def test_only_for_smsp(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        only = _find(sheet, "Только для СМСП")
        assert only["total_sum"] == pytest.approx(9_000_000)  # 4M + 5M
        assert only["count"] == 2
        assert _find(sheet, "Только для СМСП среднее")["total_sum"] == pytest.approx(4_000_000)
        assert _find(sheet, "Только для СМСП малое и микро")["total_sum"] == pytest.approx(5_000_000)

    def test_with_smsp_for_all(self, sample_rows):
        """
        С СМСП для всех = H=«нет» И G ∉ {«», «нет»}.
        В sample: Страх (Малое), Образ (Микро), С СМСП малое (Микро) = 180k + 250k + 300k.
        """
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        row = _find(sheet, "С СМСП для всех")
        assert row["total_sum"] == pytest.approx(730_000)
        assert row["count"] == 3

    def test_itogo_smsp_equals_14_plus_18(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        only = _find(sheet, "Только для СМСП")["total_sum"]
        with_ = _find(sheet, "С СМСП для всех")["total_sum"]
        itogo = _find(sheet, "Итого с СМСП")["total_sum"]
        assert itogo == pytest.approx(only + with_)

    def test_with_smsp_minus_exclusions(self, sample_rows):
        """
        С СМСП для всех (минус исключения) = «С СМСП для всех» И J=«нет».
        В sample: только «С СМСП малое» (300k), потому что Страх и Образ — с категориями.
        """
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        row = _find(sheet, "с СМСП для всех (минус исключения)")
        assert row["total_sum"] == pytest.approx(300_000)

    def test_itogo_27_equals_14_plus_24(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        only_14 = _find(sheet, "Только для СМСП")["total_sum"]
        only_24 = _find(sheet, "с СМСП для всех (минус исключения)")["total_sum"]
        itogo = _find(sheet, "Итого с СМСП (за минусом исключений)")["total_sum"]
        assert itogo == pytest.approx(only_14 + only_24)


class TestSheetFilters:
    def test_published_sheet_excludes_not_published(self, sample_rows):
        result = compute_final_summary(sample_rows)
        pub_total = _find(result["Итого_платежи_договоры_публ"], "Итого всего")
        # Исключаем 2 строки с publication="нет": Аренда (900k) и Мелкий (45k).
        assert pub_total["count"] == 6
        assert pub_total["total_sum"] == pytest.approx(10_775_000 - 900_000 - 45_000)

    def test_not_published_sheet_only_no(self, sample_rows):
        result = compute_final_summary(sample_rows)
        not_pub = _find(result["Итого_платежи_договоры_не_публ"], "Итого всего")
        assert not_pub["count"] == 2
        assert not_pub["total_sum"] == pytest.approx(945_000)


class TestSmspShare:
    """E1: расчёт долей СМСП по сумме и по количеству."""

    def test_share_by_sum_present(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        share_sum = _find(sheet, "Доля СМСП по сумме, %")
        # Числитель = «Итого с СМСП (за минусом исключений)» = только_СМСП + с_СМСП_за_исключениями
        # = 9_000_000 + 300_000 = 9_300_000
        # Знаменатель = «Итого за минусом исключений» = 10_775_000 - 1_330_000 = 9_445_000
        # Доля = 9_300_000 / 9_445_000 * 100 ≈ 98.46
        assert share_sum["total_sum"] == pytest.approx(98.46, abs=0.05)

    def test_share_by_count_present(self, sample_rows):
        sheet = result_sheet(sample_rows, "Итого_платежи_договоры")
        share_count = _find(sheet, "Доля СМСП по количеству, %")
        # СМСП-договоров после исключений: 4 (две покупки только для СМСП + Страх/Образ → нет, т.к.
        # они в категориях исключений; С СМСП малое — да, smsp_purchase=нет but smsp_type=Микро and excl=нет → да; Обычный и не публ — нет, smsp_type=нет)
        # smsp_eligible: СМСП среднее, СМСП малое, С СМСП малое = 3
        # Всего минус исключений: 8 - 3 (аренда/страх/образов) = 5
        # 3/5 * 100 = 60.0
        assert share_count["total_sum"] == pytest.approx(60.0, abs=0.05)

    def test_shares_zero_on_empty_input(self):
        result = compute_final_summary([])
        for sheet_name in result:
            share = _find(result[sheet_name], "Доля СМСП по сумме, %")
            assert share["total_sum"] == 0.0


class TestXlsxGeneration:
    def test_3_sheets_are_written(self, tmp_path, sample_rows, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "GENERATED_DIR", tmp_path)

        out = generate_final_summary_xlsx(sample_rows, "test_id")
        assert Path(out).exists()

        wb = openpyxl.load_workbook(out)
        assert set(wb.sheetnames) == {
            "Итого_платежи_договоры",
            "Итого_платежи_договоры_публ",
            "Итого_платежи_договоры_не_публ",
        }
        for name in wb.sheetnames:
            ws = wb[name]
            # 1 строка шапки + 26 метрик (некоторые пустые-разделители)
            assert ws.max_row >= 26
            # Столбец A — лейблы, B — суммы
            assert ws.cell(row=1, column=1).value == "Наименование показателя"
        wb.close()


# ─── Helpers ───────────────────────────────────────────────────────────


def _find(metrics: list[dict], label: str) -> dict:
    for m in metrics:
        if m["label"] == label:
            return m
    raise AssertionError(f"Показатель {label!r} не найден")


def result_sheet(rows: list[SumupRow], sheet_name: str) -> list[dict]:
    return compute_final_summary(rows)[sheet_name]
