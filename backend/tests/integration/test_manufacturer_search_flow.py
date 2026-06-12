"""
Integration: фоновый поиск производителей — запуск, опрос статуса, отмена.

Поиск вынесен из HTTP-запроса в asyncio-задачу (LLM на CPU работает минуты):
POST возвращает task_id, статус опрашивается GET /tasks/{id}, отмена —
POST /tasks/{id}/cancel. Ollama мокается respx; фоновые задачи пишут итог
через app.api.manufacturers.async_session, который подменяется на тестовый engine.
"""
import asyncio
import json
import uuid

import pytest
import pytest_asyncio
import respx
from httpx import Response

from app.config import settings


SPECS_PAYLOAD = {
    "product_name": "Подшипник шариковый",
    "characteristics": [{"key": "материал", "value": "сталь"}],
    "sources": None,
}

MOCK_RESULTS = [
    {
        "name": "АО «Тестовый завод»",
        "country": "Россия",
        "website": "test.ru",
        "contacts": "",
        "certificates": "ГОСТ 520",
        "products": "Подшипники",
        "source": "тест",
    }
]


@pytest_asyncio.fixture
async def bg_session_factory(test_engine, monkeypatch):
    """Фоновые задачи поиска должны писать в тестовую БД, а не в основную."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    import app.api.manufacturers as manufacturers_api

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(manufacturers_api, "async_session", factory)
    return factory


async def _poll_until_done(async_client, headers, task_id, timeout=5.0):
    """Опрашивает /tasks/{id} до выхода из processing (как делает фронт)."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        resp = await async_client.get(
            f"/api/manufacturers/tasks/{task_id}", headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] != "processing":
            return data
        assert asyncio.get_running_loop().time() < deadline, \
            "поиск не завершился за отведённое время"
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
class TestManufacturerSearchFlow:
    async def test_specs_search_runs_in_background(
        self, async_client, regular_user, user_token, auth_headers, bg_session_factory,
    ):
        headers = auth_headers(user_token)
        with respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False) as mock:
            mock.post("/api/generate").mock(
                return_value=Response(
                    200,
                    json={"response": json.dumps(MOCK_RESULTS, ensure_ascii=False)},
                )
            )

            start = await async_client.post(
                "/api/manufacturers/search-by-specs", json=SPECS_PAYLOAD, headers=headers,
            )
            assert start.status_code == 200
            body = start.json()
            # Результатов в ответе на запуск больше нет — только task_id
            assert "task_id" in body
            assert "results" not in body

            data = await _poll_until_done(async_client, headers, body["task_id"])

        assert data["status"] == "processed"
        assert data["cancelled"] is False
        assert [r["name"] for r in data["results"]] == ["АО «Тестовый завод»"]

    async def test_cancel_interrupts_search_and_marks_task(
        self, async_client, regular_user, user_token, auth_headers, bg_session_factory,
    ):
        headers = auth_headers(user_token)

        async def slow_ollama(request):
            # Имитация долгой CPU-генерации: отмена должна прервать ожидание
            await asyncio.sleep(30)
            return Response(200, json={"response": "[]"})

        with respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False) as mock:
            mock.post("/api/generate").mock(side_effect=slow_ollama)

            start = await async_client.post(
                "/api/manufacturers/search-by-specs", json=SPECS_PAYLOAD, headers=headers,
            )
            task_id = start.json()["task_id"]

            # Дать фоновой задаче дойти до вызова Ollama
            await asyncio.sleep(0.05)

            cancel = await async_client.post(
                f"/api/manufacturers/tasks/{task_id}/cancel", headers=headers,
            )
            assert cancel.status_code == 200

            data = await _poll_until_done(async_client, headers, task_id)

        assert data["status"] == "error"
        assert data["cancelled"] is True

        # Повторная отмена завершённой задачи — 409
        again = await async_client.post(
            f"/api/manufacturers/tasks/{task_id}/cancel", headers=headers,
        )
        assert again.status_code == 409

    async def test_unknown_task_returns_404(
        self, async_client, regular_user, user_token, auth_headers,
    ):
        resp = await async_client.get(
            f"/api/manufacturers/tasks/{uuid.uuid4()}", headers=auth_headers(user_token),
        )
        assert resp.status_code == 404
