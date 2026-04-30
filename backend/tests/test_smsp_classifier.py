"""Unit-тесты классификатора исключений СМСП и правил столбцов M/O."""
from datetime import date

import pytest

from app.services.smsp_classifier import (
    ClassifierRule,
    classify_exclusion,
    determine_publication,
    is_continuing,
    _extract_point_letter,
)


@pytest.fixture
def default_rules():
    """Дефолтный набор правил — копия `SMSP_DEFAULT_RULES` из config.py."""
    return [
        ClassifierRule("авиа",    ["воздушн", "авиац", "авиа"],              "р",  10),
        ClassifierRule("страх",   ["страхов", "финансов", "банковск", "лизинг"], "д",  20),
        ClassifierRule("образов", ["образоват", "обучен"],                   "ц",  30),
        ClassifierRule("аренда",  ["аренд", "недвижим"],                     "л",  40),
        ClassifierRule("почта",   ["почтов", "связ"],                        None, 50),
    ]


class TestClassifyExclusion:
    def test_empty_text(self, default_rules):
        assert classify_exclusion("", default_rules) == "нет"
        assert classify_exclusion(None, default_rules) == "нет"

    def test_explicit_no_exclusion(self, default_rules):
        assert classify_exclusion("Не является исключением", default_rules) == "нет"

    def test_by_point_letter(self, default_rules):
        """Формат «л) закупки, предметом которых является аренда…» → метка аренды."""
        txt = "л) закупки, предметом которых является аренда и (или) приобретение"
        assert classify_exclusion(txt, default_rules) == "аренда"

    def test_by_keyword(self, default_rules):
        """Если текст без буквы, но со словом «страхов» → страх."""
        assert classify_exclusion("услуги страхования имущества", default_rules) == "страх"

    def test_point_letter_wins_over_keyword(self, default_rules):
        """
        Если в тексте есть и буква пункта, и ключевое слово другой категории —
        приоритет за буквой пункта.
        """
        txt = "р) закупки услуг в области воздушных перевозок и авиационных работ"
        assert classify_exclusion(txt, default_rules) == "авиа"

    def test_disabled_rule_ignored(self, default_rules):
        """Отключённые правила не срабатывают."""
        for r in default_rules:
            if r.category == "аренда":
                r.enabled = False
        assert classify_exclusion("л) аренда недвижимого имущества", default_rules) == "нет"

    def test_order_idx_priority(self):
        """При равных кандидатах побеждает правило с меньшим `order_idx`."""
        rules = [
            ClassifierRule("cat_a", ["тест"], None, order_idx=20),
            ClassifierRule("cat_b", ["тест"], None, order_idx=10),
        ]
        assert classify_exclusion("это тестовая строка", rules) == "cat_b"

    def test_point_letter_ya1(self, default_rules):
        """Пункт я(1)) — если такое правило есть, оно должно подхватиться."""
        extra = ClassifierRule("опо", ["опасн"], "я(1)", 15)
        rules = [extra] + list(default_rules)
        txt = "я(1)) закупки работ, услуг по проектированию опасных объектов"
        assert classify_exclusion(txt, rules) == "опо"

    def test_unknown_category(self, default_rules):
        assert classify_exclusion("некая закупка без ключевых слов", default_rules) == "нет"


class TestExtractPointLetter:
    def test_simple_letter(self):
        assert _extract_point_letter("л) закупки ...") == "л"
        assert _extract_point_letter("р) воздушные") == "р"

    def test_with_leading_spaces(self):
        assert _extract_point_letter("  а) оборона") == "а"

    def test_no_letter(self):
        assert _extract_point_letter("Не является исключением") is None
        assert _extract_point_letter("") is None
        assert _extract_point_letter(None) is None

    def test_ya_subpoint(self):
        assert _extract_point_letter("я(1)) закупки опасных") == "я(1)"

    def test_not_a_point(self):
        assert _extract_point_letter("что-то без пункта") is None


class TestDeterminePublication:
    def test_rental_always_not_published(self):
        """Категория «аренда» → «нет» независимо от сумм."""
        assert determine_publication(
            exclusion_category="аренда",
            contract_sum=10_000_000.0,
            smsp_purchase="да",
            purchase_method="КИМ",
        ) == "нет"

    def test_ep_small_not_smsp_not_published(self):
        """ЕП + сумма < 100т.р. + не для СМСП → не публикуется."""
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=50_000.0,
            smsp_purchase="нет",
            purchase_method="ЕП",
        ) == "нет"

    def test_ep_threshold_boundary(self):
        """Ровно 100 т.р. — публикуется (строго меньше означает «не публ»)."""
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=100_000.0,
            smsp_purchase="нет",
            purchase_method="ЕП",
        ) == "да"

    def test_ep_above_threshold(self):
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=150_000.0,
            smsp_purchase="нет",
            purchase_method="ЕП",
        ) == "да"

    def test_small_but_smsp(self):
        """Малая сумма, но закупка для СМСП → публикуется."""
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=50_000.0,
            smsp_purchase="да",
            purchase_method="ЕП",
        ) == "да"

    def test_small_but_not_ep(self):
        """Малая сумма, но не ЕП (например КИМ) → публикуется."""
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=50_000.0,
            smsp_purchase="нет",
            purchase_method="КИМ",
        ) == "да"

    def test_no_contract_sum(self):
        """Если сумма договора не указана — публикуется (правило «< 100т.р.» не применимо)."""
        assert determine_publication(
            exclusion_category="нет",
            contract_sum=None,
            smsp_purchase="нет",
            purchase_method="ЕП",
        ) == "да"


class TestIsContinuing:
    def test_same_year(self):
        assert is_continuing(date(2025, 1, 1), date(2025, 12, 31)) == "нет"

    def test_different_years(self):
        assert is_continuing(date(2025, 6, 1), date(2026, 6, 1)) == "да"

    def test_multi_year(self):
        assert is_continuing(date(2024, 1, 1), date(2027, 12, 31)) == "да"

    def test_none_values(self):
        assert is_continuing(None, date(2026, 1, 1)) == "нет"
        assert is_continuing(date(2026, 1, 1), None) == "нет"
        assert is_continuing(None, None) == "нет"
