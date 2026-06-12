"""
Unit-тесты для D1: scenario-параметр matcher.match_positions.

- scenario="d_lux" + UPD-файл → логика акта (со скидкой), все строки помечены needs_review.
- scenario="leader_smi" + Акт → стандартная логика, все строки помечены needs_review.
- scenario пустой → автоопределение по source_file_type (как раньше).
"""
import pytest
import respx
from httpx import Response

from app.config import settings
from app.services.file_parser import ParsedDocument
from app.services.matcher import _resolve_scenario, match_positions


PRICES = [
    {"№": 1, "Наименование": "Мойка кузова седан", "Цена": 1000, "_row_index": 0},
]


def _doc(rows):
    return ParsedDocument(rows=rows, text="", metadata={})


@pytest.fixture
def mock_llm_empty():
    with respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False) as m:
        m.post("/api/generate").mock(return_value=Response(200, json={"response": "0"}))
        yield m


class TestResolveScenario:
    """Чистые case'ы для функции выбора ветки."""

    @pytest.mark.parametrize("scenario,file_type,expected", [
        # автоопределение
        (None, "act", (True, False)),
        (None, "upd", (False, False)),
        ("", "act", (True, False)),
        # явный d_lux
        ("d_lux", "act", (True, False)),
        ("d_lux", "upd", (True, True)),  # mismatch
        # явные стандартные
        ("leader_smi", "upd", (False, False)),
        ("leader_smi", "act", (False, True)),  # mismatch
        ("veneta", "upd", (False, False)),
        ("veneta", "act", (False, True)),  # mismatch
    ])
    def test_combinations(self, scenario, file_type, expected):
        assert _resolve_scenario(scenario, file_type) == expected


@pytest.mark.asyncio
class TestScenarioOverridesFileType:
    """D1: явный сценарий перевешивает source_file_type."""

    async def test_dlux_scenario_with_upd_file_applies_act_logic(self, mock_llm_empty):
        """scenario=d_lux + file_type=upd → скидка 15% (логика акта)."""
        upd_rows = [{"Наименование": "Мойка кузова седан", "Количество": 1, "Сумма": 1000, "_row_index": 0}]
        results = await match_positions(
            _doc(PRICES), _doc(upd_rows),
            source_file_type="upd",
            scenario="d_lux",
        )
        assert len(results) == 1
        # Цена = 1000 * 0.85 = 850 (применилась логика акта)
        assert results[0].price == 850.0
        # И все строки помечены needs_review с пояснением
        assert results[0].needs_review is True
        assert "не соответствует" in (results[0].highlight_reason or "").lower()

    async def test_leader_smi_scenario_with_act_file_applies_standard_logic(self, mock_llm_empty):
        """scenario=leader_smi + file_type=act → НЕ применять скидку (стандартная логика)."""
        act_rows = [{
            "Наименование": "Мойка кузова седан",
            "Количество": 1,
            "Сумма": 1000,
            "Единица измерения": "шт",
            "_row_index": 0,
        }]
        results = await match_positions(
            _doc(PRICES), _doc(act_rows),
            source_file_type="act",
            scenario="leader_smi",
        )
        assert len(results) == 1
        # Без скидки: price = total/qty = 1000
        assert results[0].price == 1000.0
        assert results[0].needs_review is True
        assert "не соответствует" in (results[0].highlight_reason or "").lower()


@pytest.mark.asyncio
class TestScenarioAutoDetect:
    """Пустой / отсутствующий scenario сохраняет старое поведение."""

    async def test_empty_scenario_uses_act_logic_for_act_file(self, mock_llm_empty):
        act_rows = [{"Наименование работы": "Мойка кузова седан", "_row_index": 0}]
        results = await match_positions(
            _doc(PRICES), _doc(act_rows),
            source_file_type="act",
            scenario=None,
        )
        assert results[0].price == 850.0  # скидка применилась
        # mismatch отсутствует
        assert "не соответствует" not in (results[0].highlight_reason or "").lower()

    async def test_empty_scenario_uses_standard_logic_for_upd_file(self, mock_llm_empty):
        upd_rows = [{"Наименование": "Мойка кузова седан", "Количество": 1, "Сумма": 1000, "_row_index": 0}]
        results = await match_positions(
            _doc(PRICES), _doc(upd_rows),
            source_file_type="upd",
            scenario="",
        )
        assert results[0].price == 1000.0
