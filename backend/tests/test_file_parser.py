"""
Unit-тесты для file_parser: генерируем временные xlsx-файлы и проверяем парсинг.
"""
from pathlib import Path

import openpyxl
import pytest

from app.services.file_parser import (
    _build_headers,
    _detect_header_row,
    _extract_document_metadata,
    _is_empty_row,
    parse_document,
    parse_excel,
)


def _make_xlsx(path: Path, rows: list[list]) -> Path:
    """Создаёт xlsx-файл с указанными строками."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(str(path))
    wb.close()
    return path


class TestDetectHeaderRow:
    def test_header_on_first_row(self):
        rows = [
            ("№", "Наименование", "Количество", "Цена"),
            (1, "Мойка", 5, 1000),
        ]
        assert _detect_header_row(rows) == 0

    def test_header_after_title(self):
        rows = [
            ("Прайс-лист ООО Ромашка",),
            (None,),
            ("№", "Наименование услуги", "Цена"),
            (1, "Мойка", 500),
        ]
        assert _detect_header_row(rows) == 2

    def test_no_clear_header_returns_first_nonempty(self):
        """
        Без заголовочных ключевых слов — возвращает индекс первой непустой строки,
        а не 0 «по умолчанию».
        """
        rows = [
            (None, None, None),
            (None, None, None),
            ("a", "b", "c"),
            ("d", "e", "f"),
        ]
        assert _detect_header_row(rows) == 2

    def test_header_after_long_preamble(self):
        """
        Реальный кейс: акт с длинной шапкой реквизитов (>20 строк),
        затем настоящая шапка таблицы. Раньше окно [:20] не доходило до
        заголовка и возвращало 0.
        """
        rows = []
        # 30 строк реквизитов (нет ключевых слов из HEADER_KEYWORDS)
        for i in range(30):
            rows.append((f"Реквизит {i}", f"Значение {i}", None))
        rows.append(("№ п/п", "Наименование услуги", "Стоимость"))
        rows.append((1, "Мойка кузова", 1000))

        assert _detect_header_row(rows) == 30

    def test_header_inside_extended_window(self):
        """Шапка ровно на границе нового окна (~50 строк) — должна находиться."""
        rows = [(None,) * 3] * 50
        rows.append(("№", "Наименование", "Цена"))
        rows.append((1, "Услуга", 100))
        assert _detect_header_row(rows) == 50


class TestBuildHeaders:
    def test_unique_headers(self):
        assert _build_headers(("№", "Наименование", "Цена")) == ["№", "Наименование", "Цена"]

    def test_duplicates_numbered(self):
        # Два "Цена" → второй становится "Цена_2"
        headers = _build_headers(("№", "Цена", "Цена"))
        assert headers == ["№", "Цена", "Цена_2"]

    def test_empty_cells_replaced(self):
        headers = _build_headers(("№", None, ""))
        assert headers[0] == "№"
        assert headers[1].startswith("col_")
        assert headers[2].startswith("col_")


class TestIsEmptyRow:
    def test_all_none(self):
        assert _is_empty_row((None, None, None)) is True

    def test_all_empty_strings(self):
        assert _is_empty_row(("", "  ", "\t")) is True

    def test_non_empty(self):
        assert _is_empty_row((None, "значение", None)) is False

    def test_zero_is_not_empty(self):
        # 0 — реальное значение
        assert _is_empty_row((0, None)) is False


class TestParseExcel:
    def test_basic_table(self, tmp_path):
        file = _make_xlsx(tmp_path / "test.xlsx", [
            ["№", "Наименование", "Количество", "Цена"],
            [1, "Мойка кузова", 5, 1000],
            [2, "Чистка салона", 3, 500],
        ])
        doc = parse_excel(file)
        assert len(doc.rows) == 2
        assert doc.rows[0]["Наименование"] == "Мойка кузова"
        assert doc.rows[0]["Количество"] == 5
        assert doc.rows[1]["№"] == 2

    def test_ignores_empty_rows(self, tmp_path):
        file = _make_xlsx(tmp_path / "test.xlsx", [
            ["№", "Наименование", "Цена"],
            [1, "Мойка", 1000],
            [None, None, None],
            [2, "Чистка", 500],
        ])
        doc = parse_excel(file)
        assert len(doc.rows) == 2

    def test_row_index_assigned(self, tmp_path):
        file = _make_xlsx(tmp_path / "test.xlsx", [
            ["№", "Наименование"],
            [1, "A"],
            [2, "B"],
        ])
        doc = parse_excel(file)
        assert doc.rows[0]["_row_index"] == 0
        assert doc.rows[1]["_row_index"] == 1

    def test_metadata_records_header_detection(self, tmp_path):
        """metadata содержит запись про найденный заголовок (для отладки)."""
        file = _make_xlsx(tmp_path / "test.xlsx", [
            ["Просто текст"],
            [None],
            ["№", "Наименование", "Цена"],
            [1, "Мойка", 1000],
        ])
        doc = parse_excel(file)
        assert "header_detection" in doc.metadata
        assert isinstance(doc.metadata["header_detection"], list)
        assert len(doc.metadata["header_detection"]) == 1
        info = doc.metadata["header_detection"][0]
        assert info["row"] == 2
        assert info["confident"] is True
        assert info["keyword_hits"] >= 1

    def test_metadata_marks_unconfident_when_no_keywords(self, tmp_path):
        """Без ключевых слов в шапке — confident=False."""
        file = _make_xlsx(tmp_path / "test.xlsx", [
            ["a", "b", "c"],
            ["d", "e", "f"],
        ])
        doc = parse_excel(file)
        info = doc.metadata["header_detection"][0]
        assert info["confident"] is False
        assert info["keyword_hits"] == 0


class TestParseDocumentDispatch:
    def test_xlsx_dispatched(self, tmp_path):
        file = _make_xlsx(tmp_path / "test.xlsx", [["№", "Наименование"], [1, "A"]])
        doc = parse_document(str(file))
        assert len(doc.rows) == 1

    def test_unsupported_extension(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("hello")
        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            parse_document(str(file))

    def test_doc_extension_rejected(self, tmp_path):
        file = tmp_path / "test.doc"
        file.write_text("x")
        with pytest.raises(ValueError):
            parse_document(str(file))


class TestParseXLS:
    """
    Парсинг старого .xls формата через xlrd.
    Файл генерируется на лету через xlwt — если xlwt не установлен, тесты скипаются.
    """

    @pytest.fixture
    def xls_file(self, tmp_path):
        xlwt = pytest.importorskip("xlwt")
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        for col_idx, val in enumerate(["№", "Наименование", "Цена"]):
            ws.write(0, col_idx, val)
        ws.write(1, 0, 1)
        ws.write(1, 1, "Мойка кузова")
        ws.write(1, 2, 1000)
        ws.write(2, 0, 2)
        ws.write(2, 1, "Чистка салона")
        ws.write(2, 2, 500)
        path = tmp_path / "test.xls"
        wb.save(str(path))
        return path

    def test_parses_basic_xls(self, xls_file):
        doc = parse_document(str(xls_file))
        assert len(doc.rows) == 2
        assert doc.rows[0]["Наименование"] == "Мойка кузова"
        assert doc.rows[0]["Цена"] == 1000
        assert doc.rows[1]["№"] == 2

    def test_xls_metadata_has_header_detection(self, xls_file):
        doc = parse_document(str(xls_file))
        assert "header_detection" in doc.metadata
        assert doc.metadata["header_detection"][0]["row"] == 0
        assert doc.metadata["header_detection"][0]["confident"] is True


class TestParsePDF:
    """
    Парсинг PDF через pdfplumber. Файл генерируется reportlab.
    """

    @pytest.fixture
    def pdf_file(self, tmp_path):
        reportlab = pytest.importorskip("reportlab")
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

        path = tmp_path / "test.pdf"
        # Только латиница и цифры — встроенные шрифты reportlab не поддерживают кириллицу.
        data = [
            ["No", "Name", "Price"],
            ["1", "Service A", "1000"],
            ["2", "Service B", "500"],
        ]
        # GRID нужен, чтобы pdfplumber смог распознать структуру таблицы (он
        # детектит таблицы по линиям).
        table = Table(data)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        doc = SimpleDocTemplate(str(path), pagesize=A4)
        doc.build([table])
        return path

    def test_parses_pdf_table(self, pdf_file):
        doc = parse_document(str(pdf_file))
        # Хотя бы одна строка таблицы должна быть извлечена
        assert len(doc.rows) >= 1
        # Метаданные содержат header_detection
        assert "header_detection" in doc.metadata
        assert len(doc.metadata["header_detection"]) >= 1


class TestExtractDocumentMetadata:
    def test_finds_schet_factura_number(self):
        text = "Счет-фактура № 12345/АБ от 15.03.2024"
        meta = _extract_document_metadata(text, [])
        assert meta["document_number"] == "12345/АБ"

    def test_finds_act_number(self):
        text = "Расшифровка к акту выполненных работ № 42"
        meta = _extract_document_metadata(text, [])
        assert meta["document_number"] == "42"

    def test_finds_max_date(self):
        text = "Дата 10.01.2024. Подписан 15.03.2024. Отправлен 05.02.2024."
        meta = _extract_document_metadata(text, [])
        assert meta["document_date"] == "15.03.2024"
        assert len(meta["all_dates"]) == 3

    def test_no_match_returns_none(self):
        meta = _extract_document_metadata("Нет ни номера ни даты", [])
        assert meta["document_number"] is None
        assert meta["document_date"] is None
        assert meta["all_dates"] == []

    def test_fallback_searches_in_rows(self):
        """Если нет text, ищем в rows."""
        rows = [{"col": "Счет-фактура № 555"}, {"col": "дата 01.01.2024"}]
        meta = _extract_document_metadata("", rows)
        assert meta["document_number"] == "555"
