"""
Integration: полный flow обработки документов (upload → process → download).

Использует respx для мока Ollama (не ходим в реальную нейронку).
"""
import io
from pathlib import Path

import openpyxl
import pytest
import respx
from httpx import Response

from app.config import settings


def _xlsx_bytes(rows: list[list]) -> bytes:
    """Генерирует xlsx-файл в памяти, возвращает его байты."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


@pytest.fixture
def positions_xlsx():
    return _xlsx_bytes([
        ["№", "Наименование", "Цена", "Ед. изм."],
        [1, "Мойка кузова", 1000, "шт"],
        [2, "Чистка салона", 500, "шт"],
        [3, "Полировка кузова", 1500, "шт"],
    ])


@pytest.fixture
def upd_xlsx():
    return _xlsx_bytes([
        ["№", "Наименование услуги", "Количество", "Сумма", "Единица измерения"],
        [1, "Мойка кузова", 2, 2000, "шт"],
        [2, "Полировка кузова", 1, 1500, "шт"],
    ])


@pytest.mark.asyncio
class TestDocumentUpload:
    async def test_upload_positions_xlsx(
        self, async_client, regular_user, user_token, auth_headers, positions_xlsx,
    ):
        files = {"file": ("positions.xlsx", positions_xlsx,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"file_type": "positions", "metadata": "{}"}
        response = await async_client.post(
            "/api/documents/upload",
            files=files,
            data=data,
            headers=auth_headers(user_token),
        )
        assert response.status_code == 200
        resp_data = response.json()
        assert resp_data["file_type"] == "positions"
        assert resp_data["filename"] == "positions.xlsx"

    async def test_rejects_unsupported_extension(
        self, async_client, regular_user, user_token, auth_headers,
    ):
        files = {"file": ("bad.txt", b"not a spreadsheet", "text/plain")}
        data = {"file_type": "positions"}
        response = await async_client.post(
            "/api/documents/upload",
            files=files,
            data=data,
            headers=auth_headers(user_token),
        )
        assert response.status_code == 400

    async def test_unauthorized_upload(self, async_client, positions_xlsx):
        files = {"file": ("p.xlsx", positions_xlsx, "application/xlsx")}
        data = {"file_type": "positions"}
        response = await async_client.post("/api/documents/upload", files=files, data=data)
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
class TestListDocuments:
    async def test_list_own_documents(
        self, async_client, regular_user, user_token, auth_headers, positions_xlsx,
    ):
        # Загружаем 1 документ
        files = {"file": ("positions.xlsx", positions_xlsx, "application/xlsx")}
        await async_client.post(
            "/api/documents/upload", files=files, data={"file_type": "positions"},
            headers=auth_headers(user_token),
        )
        # Запрашиваем список
        response = await async_client.get("/api/documents/", headers=auth_headers(user_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_filter_by_file_type(
        self, async_client, regular_user, user_token, auth_headers, positions_xlsx,
    ):
        await async_client.post(
            "/api/documents/upload",
            files={"file": ("p.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "positions"},
            headers=auth_headers(user_token),
        )
        response = await async_client.get(
            "/api/documents/?file_type=upd", headers=auth_headers(user_token),
        )
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestProcessFlow:
    """Полный flow: upload positions + upd → process → ответ с matches."""

    async def test_full_processing_flow(
        self, async_client, regular_user, user_token, auth_headers,
        positions_xlsx, upd_xlsx,
    ):
        # 1. Upload positions
        pos_resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("positions.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "positions"},
            headers=auth_headers(user_token),
        )
        positions_id = pos_resp.json()["id"]

        # 2. Upload UPD
        upd_resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("upd.xlsx", upd_xlsx, "application/xlsx")},
            data={"file_type": "upd"},
            headers=auth_headers(user_token),
        )
        upd_id = upd_resp.json()["id"]

        # 3. Process (мокируем Ollama)
        with respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False) as mock:
            mock.post("/api/generate").mock(return_value=Response(200, json={"response": "0"}))
            proc_resp = await async_client.post(
                "/api/documents/process",
                json={
                    "positions_document_id": positions_id,
                    "upd_document_id": upd_id,
                    "document_number": "INV-001",
                    "document_date": "15.03.2024",
                    "scenario": "leader_smi",
                },
                headers=auth_headers(user_token),
            )
            assert proc_resp.status_code == 200, proc_resp.text
            data = proc_resp.json()
            assert "matches" in data
            assert len(data["matches"]) == 2
            assert data["result_document_id"] is not None

    async def test_process_rejects_wrong_file_types(
        self, async_client, regular_user, user_token, auth_headers, positions_xlsx,
    ):
        # Загружаем как UPD, но передаём как positions → ошибка
        resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("f.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "upd"},  # загружен как upd
            headers=auth_headers(user_token),
        )
        upd_as_positions_id = resp.json()["id"]

        resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("f2.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "upd"},
            headers=auth_headers(user_token),
        )
        another_upd_id = resp.json()["id"]

        proc_resp = await async_client.post(
            "/api/documents/process",
            json={
                "positions_document_id": upd_as_positions_id,
                "upd_document_id": another_upd_id,
            },
            headers=auth_headers(user_token),
        )
        assert proc_resp.status_code == 400


@pytest.mark.asyncio
class TestDownloadDocument:
    async def test_download_own_document(
        self, async_client, regular_user, user_token, auth_headers, positions_xlsx,
    ):
        resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("p.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "positions"},
            headers=auth_headers(user_token),
        )
        doc_id = resp.json()["id"]

        dl_resp = await async_client.get(
            f"/api/documents/{doc_id}/download",
            headers=auth_headers(user_token),
        )
        assert dl_resp.status_code == 200
        assert len(dl_resp.content) > 0

    async def test_download_forbidden_for_other_user(
        self, async_client, regular_user, admin_user, user_token, auth_headers,
        positions_xlsx, db_session,
    ):
        # regular_user загружает
        resp = await async_client.post(
            "/api/documents/upload",
            files={"file": ("p.xlsx", positions_xlsx, "application/xlsx")},
            data={"file_type": "positions"},
            headers=auth_headers(user_token),
        )
        doc_id = resp.json()["id"]

        # Создаём второго обычного пользователя
        from app.models import User, UserRole
        from app.utils.auth import hash_password, create_access_token
        other = User(
            username="other", email="other@test.local",
            password_hash=hash_password("p"), full_name="Other",
            role=UserRole.USER,
        )
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)
        other_token = create_access_token({"sub": str(other.id), "role": "user"})

        dl_resp = await async_client.get(
            f"/api/documents/{doc_id}/download",
            headers=auth_headers(other_token),
        )
        assert dl_resp.status_code == 403
