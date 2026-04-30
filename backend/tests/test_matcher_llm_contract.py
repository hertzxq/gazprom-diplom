"""
Contract-тесты с реальной Ollama (без respx-мока).

Запуск:
    pytest -m llm

Автоматически скипаются если Ollama не отвечает на REAL_OLLAMA_URL.
LLM недетерминирована, поэтому утверждения мягкие: проверяем, что вызов проходит
без ошибок и возвращает разумный результат.
"""
import pytest

from app.services.file_parser import ParsedDocument
from app.services.matcher import match_positions

pytestmark = [pytest.mark.llm, pytest.mark.slow]


PRICE_LIST = [
    {"№": 1, "Наименование": "Мойка кузова легкового автомобиля", "Цена": 1000, "_row_index": 0},
    {"№": 2, "Наименование": "Полировка кузова", "Цена": 2000, "_row_index": 1},
    {"№": 3, "Наименование": "Химчистка салона", "Цена": 3000, "_row_index": 2},
    {"№": 4, "Наименование": "Замена картриджа фильтра", "Цена": 500, "_row_index": 3},
]


def _doc(rows):
    return ParsedDocument(rows=rows, text="", metadata={})


@pytest.mark.asyncio
async def test_llm_resolves_borderline_match(real_ollama_settings):
    """
    Пограничный fuzzy-score (~50–85) → matcher идёт в LLM.
    Запрос «помойка авто» должен разрешиться LLM в позицию 1 («Мойка кузова»).
    Утверждение мягкое: либо matcher вернул валидную позицию, либо None — без ошибок.
    """
    upd = _doc([
        {"Наименование услуги": "помойка авто", "Количество": 1, "Сумма": 1000,
         "Единица измерения": "шт", "_row_index": 0},
    ])
    results = await match_positions(_doc(PRICE_LIST), upd, source_file_type="upd")
    assert len(results) == 1
    r = results[0]
    # Не падаем, structured-результат корректный
    assert r.upd_item_name == "помойка авто"
    # Если LLM смог сматчить — это позиция 1 (мойка). Если нет — None.
    assert r.matched_position_number in (1, None)


@pytest.mark.asyncio
async def test_llm_returns_none_for_irrelevant_query(real_ollama_settings):
    """Совершенно нерелевантный запрос — LLM должна ответить «нет совпадения» (или fuzzy дать low score)."""
    upd = _doc([
        {"Наименование услуги": "консультация юриста по договорам аренды",
         "Количество": 1, "Сумма": 5000, "_row_index": 0},
    ])
    results = await match_positions(_doc(PRICE_LIST), upd, source_file_type="upd")
    assert len(results) == 1
    r = results[0]
    # Реальная LLM может «угадать» что-то, но needs_review должен быть True
    # (либо score низкий → нет точного совпадения)
    if r.matched_position_number is not None:
        assert r.needs_review is True
