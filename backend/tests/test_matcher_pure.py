"""
Unit-тесты для чистых (синхронных) функций matcher.py.
Не требуют сети, БД, Ollama. Запускаются быстро.
"""
import pytest

from app.services.matcher import (
    _apply_discount,
    _detect_category,
    _extract_item_name,
    _extract_numeric,
    _extract_position_number,
    _extract_value,
    _has_strong_dirty_marker,
    _is_round_number,
    _normalize_text,
    _prepare_positions,
    _rank_positions,
    _split_act_services,
    _to_float,
)


class TestNormalizeText:
    def test_yo_replaced_with_e(self):
        assert _normalize_text("Ёлка") == "елка"

    def test_special_chars_removed(self):
        assert _normalize_text("мойка, кузова!") == "мойка кузова"

    def test_multiple_whitespace_collapsed(self):
        assert _normalize_text("мойка    кузова\t\nавто") == "мойка кузова авто"

    def test_empty_string(self):
        assert _normalize_text("") == ""

    def test_none_safe(self):
        assert _normalize_text(None) == ""

    def test_keeps_latin_and_digits(self):
        assert _normalize_text("Toyota Camry 2020!") == "toyota camry 2020"


class TestDetectCategory:
    @pytest.mark.parametrize("text,expected", [
        ("Hyundai Solaris", "седан"),
        ("RIO", "седан"),
        ("Camry", "седан"),
        ("Джип большой", "джип"),
        ("Toyota RAV4", "джип"),
        ("X5 кроссовер", "джип"),
        ("Ford Transit", "микроавтобус"),
        ("микроавтобус Mercedes", "микроавтобус"),
    ])
    def test_known_categories(self, text, expected):
        assert _detect_category(text) == expected

    def test_unknown_returns_none(self):
        assert _detect_category("Трактор Беларусь") is None

    def test_empty_returns_none(self):
        assert _detect_category("") is None
        assert _detect_category(None) is None

    def test_cyrillic_model_not_in_dict_is_not_matched(self):
        """
        ВАЖНО: словарь CATEGORY_KEYWORDS содержит латинские модели (solaris, rio, ...).
        Кириллическая транслитерация «Солярис» не детектируется — это известное ограничение.
        """
        assert _detect_category("Солярис") is None


class TestHasStrongDirtyMarker:
    def test_positive_case(self):
        assert _has_strong_dirty_marker("Мойка при сильном загрязнении") is True

    def test_positive_case_different_word_order(self):
        assert _has_strong_dirty_marker("Сильное загрязнение кузова") is True

    def test_only_silno_is_not_enough(self):
        assert _has_strong_dirty_marker("Сильный запах в салоне") is False

    def test_only_zagryaz_is_not_enough(self):
        assert _has_strong_dirty_marker("Лёгкое загрязнение") is False

    def test_empty(self):
        assert _has_strong_dirty_marker("") is False


class TestApplyDiscount:
    def test_round_price(self):
        assert _apply_discount(1000) == 850.0

    def test_rounds_to_two_decimals(self):
        # 100.99 * 0.85 = 85.8415 -> 85.84
        assert _apply_discount(100.99) == 85.84

    def test_zero(self):
        assert _apply_discount(0) == 0.0

    def test_small_price(self):
        assert _apply_discount(100) == 85.0


class TestIsRoundNumber:
    @pytest.mark.parametrize("value,expected", [
        (680.0, True),
        (680, True),
        (0.0, True),
        (680.01, False),
        (680.5, False),
        (680.0005, True),   # в пределах допуска 0.001
        (680.01, False),
    ])
    def test_values(self, value, expected):
        assert _is_round_number(value) is expected


class TestSplitActServices:
    def test_single_service(self):
        result = _split_act_services("Мойка кузова")
        assert result == ["Мойка кузова"]

    def test_two_services_with_and(self):
        # Должен разделить — содержит ≥ 2 ключевых слов услуг
        result = _split_act_services("Мойка кузова и чистка салона")
        assert len(result) == 2
        assert "Мойка кузова" in result
        assert "чистка салона" in result

    def test_and_between_non_services(self):
        # «песок» и «гравий» — не ключевые слова услуг → не делит
        result = _split_act_services("песок и гравий")
        assert result == ["песок и гравий"]

    def test_split_by_semicolon(self):
        result = _split_act_services("Мойка; чистка")
        assert len(result) == 2

    def test_split_by_plus(self):
        result = _split_act_services("Мойка + воск")
        assert len(result) == 2

    def test_multiline_after_normalization_becomes_single(self):
        """
        ОГРАНИЧЕНИЕ: перед разбиением применяется `re.sub(r"\\s+", " ", text)`,
        который превращает \\n в пробел. Поэтому многострочный ввод НЕ делится по строкам.
        Разбиение по \\n работает только если такая строка попадает из Excel-ячейки как отдельный row.
        """
        result = _split_act_services("Мойка кузова\nполировка")
        assert result == ["Мойка кузова полировка"]

    def test_empty_string(self):
        assert _split_act_services("") == []

    def test_trims_punctuation(self):
        result = _split_act_services(";; Мойка ;; ")
        assert result == ["Мойка"]


class TestToFloat:
    @pytest.mark.parametrize("value,expected", [
        (100, 100.0),
        (100.5, 100.5),
        ("100", 100.0),
        ("100,5", 100.5),
        ("1 234,56", 1234.56),
        ("1\xa0234,56", 1234.56),  # неразрывный пробел
        # Для формата "1.234,56" (точка-тысячи, запятая-дроби) функция требует > 1 точки.
        # Одна точка + одна запятая трактуется как "100,5" + лишняя точка — падает.
        ("1.234.567,89", 1234567.89),  # точки > 1 → корректно
        ("—", None),
        ("", None),
        (None, None),
        ("abc", None),
    ])
    def test_values(self, value, expected):
        assert _to_float(value) == expected


class TestExtractNumeric:
    def test_extracts_by_exact_key(self):
        row = {"Количество": "5,5"}
        assert _extract_numeric(row, ["количество"]) == 5.5

    def test_case_insensitive_partial(self):
        row = {"Сумма с НДС": 1000}
        assert _extract_numeric(row, ["сумма"]) == 1000.0

    def test_skips_system_keys(self):
        # система использует _row_index, но _extract_numeric не должен ломаться
        row = {"_row_index": 5, "цена": "100"}
        assert _extract_numeric(row, ["цена"]) == 100.0

    def test_returns_none_if_not_found(self):
        row = {"другое": 100}
        assert _extract_numeric(row, ["цена"]) is None


class TestExtractValue:
    def test_extracts_string(self):
        row = {"Единица измерения": "шт"}
        assert _extract_value(row, ["единица"]) == "шт"

    def test_returns_none_for_empty(self):
        row = {"Единица": ""}
        assert _extract_value(row, ["единица"]) is None

    def test_case_insensitive(self):
        row = {"Ед. изм.": "кг"}
        assert _extract_value(row, ["ед. изм"]) == "кг"


class TestExtractItemName:
    def test_prefers_known_keys(self):
        row = {"Наименование услуги": "Мойка", "Описание": "Полная мойка авто"}
        assert _extract_item_name(row) == "Мойка"

    def test_fallback_to_long_string(self):
        row = {"foo": "Мойка кузова автомобиля"}
        assert _extract_item_name(row) == "Мойка кузова автомобиля"

    def test_skips_numeric_strings(self):
        row = {"foo": "123.45", "описание": "услуга"}
        assert _extract_item_name(row) == "услуга"

    def test_returns_none_for_empty(self):
        assert _extract_item_name({}) is None


class TestExtractPositionNumber:
    def test_extracts_int(self):
        row = {"№": 5}
        assert _extract_position_number(row) == 5

    def test_extracts_from_string(self):
        row = {"№ п/п": "12"}
        assert _extract_position_number(row) == 12

    def test_handles_float_string(self):
        row = {"номер": "3.0"}
        assert _extract_position_number(row) == 3

    def test_returns_none_if_absent(self):
        assert _extract_position_number({"foo": "bar"}) is None


class TestPreparePositions:
    def test_filters_rows_without_name(self):
        rows = [
            {"Наименование": "Мойка", "Цена": 500, "№": 1},
            {"foo": 123},  # нет наименования
            {"Наименование": "Чистка", "Цена": 300, "№": 2},
        ]
        result = _prepare_positions(rows)
        assert len(result) == 2
        assert result[0]["name"] == "Мойка"
        assert result[0]["price"] == 500.0
        assert result[0]["number"] == 1

    def test_normalized_name_set(self):
        result = _prepare_positions([{"Наименование": "Мойка Ёлочка", "№": 1}])
        assert result[0]["normalized_name"] == "мойка елочка"


class TestRankPositions:
    def test_order_by_score(self):
        positions = [
            {"number": 1, "name": "Чистка салона", "normalized_name": "чистка салона",
             "price": None, "unit": None, "category": None, "raw": {}},
            {"number": 2, "name": "Мойка кузова", "normalized_name": "мойка кузова",
             "price": None, "unit": None, "category": None, "raw": {}},
        ]
        ranked = _rank_positions("мойка кузова", positions)
        assert ranked[0]["number"] == 2
        assert ranked[0]["score"] > ranked[1]["score"]

    def test_category_bonus(self):
        positions = [
            {"number": 1, "name": "Мойка", "normalized_name": "мойка",
             "price": None, "unit": None, "category": "джип", "raw": {}},
            {"number": 2, "name": "Мойка", "normalized_name": "мойка",
             "price": None, "unit": None, "category": "седан", "raw": {}},
        ]
        ranked = _rank_positions("мойка", positions, category_hint="седан")
        assert ranked[0]["number"] == 2
        # Фильтр по категории оставил только седан
        assert all(p["category"] == "седан" for p in ranked)

    def test_empty_returns_empty(self):
        assert _rank_positions("что угодно", []) == []

    def test_score_capped_at_100(self):
        positions = [
            {"number": 1, "name": "Мойка", "normalized_name": "мойка",
             "price": None, "unit": None, "category": "седан", "raw": {}},
        ]
        ranked = _rank_positions("мойка", positions, category_hint="седан")
        assert ranked[0]["score"] <= 100.0
