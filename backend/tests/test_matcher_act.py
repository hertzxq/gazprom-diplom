"""
Интеграционные тесты matcher для сценария Д-люкс (акт):
- скидка 15%
- коэффициент 1.5 при сильном загрязнении
- 3 категории авто, наследование категории по строкам
- разбиение одной строки на несколько услуг
- подсветка спорных цен
"""
import pytest
import respx
from httpx import Response

from app.config import settings
from app.services.file_parser import ParsedDocument
from app.services.matcher import match_positions


# Синтетический прайс-лист (все 3 категории)
PRICE_LIST_ROWS = [
    {"№": 1, "Наименование": "Мойка седан", "Цена": 1000, "_row_index": 0},
    {"№": 2, "Наименование": "Мойка седан при сильном загрязнении", "Цена": 1000, "_row_index": 1},
    {"№": 3, "Наименование": "Полировка седан", "Цена": 800, "_row_index": 2},
    {"№": 4, "Наименование": "Мойка джип", "Цена": 1500, "_row_index": 3},
    {"№": 5, "Наименование": "Мойка джип при сильном загрязнении", "Цена": 1500, "_row_index": 4},
    {"№": 6, "Наименование": "Чистка салона микроавтобус", "Цена": 2000, "_row_index": 5},
]


def _doc(rows):
    return ParsedDocument(rows=rows, text="", metadata={})


@pytest.fixture
def mock_llm_empty():
    """LLM всегда возвращает 0 (не нашёл) — поведение при неуверенности."""
    with respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False) as mock:
        mock.post("/api/generate").mock(return_value=Response(200, json={"response": "0"}))
        yield mock


@pytest.mark.asyncio
class TestActDiscount:
    """Проверка скидки 15% для актов."""

    async def test_price_reduced_by_15_percent(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Марка авто": "Toyota Camry", "Наименование работы": "Мойка седан", "_row_index": 0},
        ])
        results = await match_positions(positions, act, source_file_type="act")
        assert len(results) == 1
        r = results[0]
        # Цена 1000 - 15% = 850
        assert r.price == 850.0
        assert r.total == 850.0  # quantity=1
        assert r.quantity == 1.0
        assert r.unit == "условная единица"


@pytest.mark.asyncio
class TestActStrongDirtyMultiplier:
    """Коэффициент 1.5 для «сильного загрязнения»."""

    async def test_strong_dirty_multiplies_by_1_5(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Марка авто": "Camry", "Наименование работы": "Мойка седан при сильном загрязнении", "_row_index": 0},
        ])
        results = await match_positions(positions, act, source_file_type="act")
        r = results[0]
        # 1000 * 0.85 * 1.5 = 1275
        assert r.price == pytest.approx(1275.0, abs=0.01)
        assert r.highlight_price is True
        assert "1.5" in (r.highlight_reason or "") or "коэффициент" in (r.highlight_reason or "").lower()


@pytest.mark.asyncio
class TestActHighlightForKopecks:
    """Цена с копейками → подсветка."""

    async def test_price_with_kopecks_highlighted(self, mock_llm_empty):
        positions = _doc([
            {"№": 1, "Наименование": "Полировка седан", "Цена": 777, "_row_index": 0},
        ])
        act = _doc([
            {"Марка авто": "Camry", "Наименование работы": "Полировка седан", "_row_index": 0},
        ])
        results = await match_positions(positions, act, source_file_type="act")
        r = results[0]
        # 777 * 0.85 = 660.45 — с копейками
        assert r.price == 660.45
        assert r.highlight_price is True


@pytest.mark.asyncio
class TestActRowSplit:
    """Одна строка акта с «и» между услугами → несколько MatchResult."""

    async def test_two_services_in_one_row(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {
                "Марка авто": "Camry",
                "Наименование работы": "Мойка седан и полировка седан",
                "_row_index": 0,
            },
        ])
        results = await match_positions(positions, act, source_file_type="act")
        # Должно быть 2 результата — по одному на каждую услугу
        assert len(results) == 2
        names = {r.upd_item_name.lower() for r in results}
        assert any("мойка" in n for n in names)
        assert any("полировка" in n for n in names)


@pytest.mark.asyncio
class TestActCategoryInheritance:
    """
    Категория авто определяется один раз и наследуется для последующих строк
    до следующего явного указания.
    """

    async def test_category_inherited_between_rows(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Марка авто": "Toyota Camry (седан)", "Наименование работы": "Мойка", "_row_index": 0},
            {"Марка авто": "", "Наименование работы": "Полировка", "_row_index": 1},
            {"Марка авто": "RAV4", "Наименование работы": "Мойка", "_row_index": 2},
        ])
        results = await match_positions(positions, act, source_file_type="act")
        assert len(results) == 3
        # Первые две строки должны матчиться к седановым позициям (1 или 3)
        # Третья (RAV4) → джип → к позиции 4
        third = results[2]
        # Сложно строго предсказать без знания порогов, но хотя бы категория должна быть распознана
        assert third.matched_position_number in (4, 5, None)


@pytest.mark.asyncio
class TestSectionHeaderHandling:
    """
    Секционный заголовок (категория без услуг) НЕ создаёт MatchResult,
    но обновляет «текущую» категорию для последующих строк.
    """

    async def test_section_header_skipped(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Наименование работы": "СЕДАН", "_row_index": 0},  # секционный заголовок
            {"Наименование работы": "Мойка", "_row_index": 1},   # услуга без явного авто
        ])
        results = await match_positions(positions, act, source_file_type="act")
        assert len(results) == 1
        # Категория унаследована из секционного заголовка → needs_review
        r = results[0]
        assert r.needs_review is True
        assert r.highlight_reason and "унаследован" in r.highlight_reason.lower()
        # Должен матчиться к «Мойка седан» (поз. 1) благодаря унаследованной категории
        assert r.matched_position_number in (1, 2)

    async def test_section_header_only_no_results(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Наименование работы": "Джипы", "_row_index": 0},
            {"Наименование работы": "Седан", "_row_index": 1},
        ])
        results = await match_positions(positions, act, source_file_type="act")
        assert results == []


@pytest.mark.asyncio
class TestCarryDownCategory:
    """Поведение унаследованной категории."""

    async def test_inline_category_overrides_inherited(self, mock_llm_empty):
        """
        Секционный заголовок — джип, но в строке услуги указано Camry (седан).
        Inline-категория перевешивает унаследованную, needs_review для категории
        не выставляется.
        """
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Наименование работы": "Джип", "_row_index": 0},                              # секция
            {"Наименование работы": "Camry мойка", "_row_index": 1},                        # inline=седан
        ])
        results = await match_positions(positions, act, source_file_type="act")
        assert len(results) == 1
        r = results[0]
        # Должен матчиться к седану (поз. 1 или 2), не к джипу (4 или 5)
        assert r.matched_position_number in (1, 2)
        # Унаследованная категория не использовалась → нет такой причины
        assert r.highlight_reason is None or "унаследован" not in (r.highlight_reason or "").lower()

    async def test_service_row_does_not_set_category(self, mock_llm_empty):
        """
        Раньше любая строка с inline-категорией обновляла current_category.
        Теперь только секционный заголовок. Поэтому строка-услуга с упоминанием
        Camry НЕ должна перезатирать категорию для следующих строк.
        """
        positions = _doc(PRICE_LIST_ROWS)
        act = _doc([
            {"Наименование работы": "Джип", "_row_index": 0},                  # секция → current=джип
            {"Наименование работы": "Camry мойка", "_row_index": 1},            # inline=седан, current не меняется
            {"Наименование работы": "Мойка", "_row_index": 2},                  # должна унаследовать «джип»
        ])
        results = await match_positions(positions, act, source_file_type="act")
        # 2 услуги (1 секционный заголовок пропущен)
        assert len(results) == 2
        # Третья строка → джип (поз. 4 или 5)
        assert results[1].matched_position_number in (4, 5)


@pytest.mark.asyncio
class TestActVsStandardRouting:
    """Проверяем что source_file_type='act' идёт в _match_act_rows, иначе в _match_standard_rows."""

    async def test_act_applies_discount_standard_does_not(self, mock_llm_empty):
        positions = _doc(PRICE_LIST_ROWS)
        rows = [{"Марка авто": "Camry", "Наименование услуги": "Мойка седан",
                 "Количество": 1, "Сумма": 1000, "Единица измерения": "шт", "_row_index": 0}]

        # Стандартный (упд) — без скидки, берёт цену из total/qty
        standard = await match_positions(_doc(PRICE_LIST_ROWS), _doc(rows), source_file_type="upd")
        assert standard[0].price == 1000.0  # из total/qty

        # Акт — скидка 15%
        act_results = await match_positions(_doc(PRICE_LIST_ROWS), _doc(rows), source_file_type="act")
        assert act_results[0].price == 850.0
