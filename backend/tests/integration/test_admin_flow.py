"""
Integration: админ-эндпоинты (список пользователей, смена роли, удаление, защита от self-harm).
"""
import pytest


@pytest.mark.asyncio
class TestListUsers:
    async def test_admin_sees_all_users(self, async_client, admin_user, regular_user, admin_token, auth_headers):
        response = await async_client.get("/api/admin/users", headers=auth_headers(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        usernames = {u["username"] for u in data}
        assert "test_admin" in usernames
        assert "test_user" in usernames

    async def test_regular_user_forbidden(self, async_client, regular_user, user_token, auth_headers):
        response = await async_client.get("/api/admin/users", headers=auth_headers(user_token))
        assert response.status_code == 403


@pytest.mark.asyncio
class TestUpdateUser:
    async def test_promote_to_admin(self, async_client, admin_user, regular_user, admin_token, auth_headers):
        response = await async_client.patch(
            f"/api/admin/users/{regular_user.id}",
            json={"role": "admin"},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_deactivate_user(self, async_client, admin_user, regular_user, admin_token, auth_headers):
        response = await async_client.patch(
            f"/api/admin/users/{regular_user.id}",
            json={"is_active": False},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    async def test_cannot_deactivate_self(self, async_client, admin_user, admin_token, auth_headers):
        response = await async_client.patch(
            f"/api/admin/users/{admin_user.id}",
            json={"is_active": False},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 400

    async def test_update_not_found(self, async_client, admin_user, admin_token, auth_headers):
        import uuid
        fake_id = uuid.uuid4()
        response = await async_client.patch(
            f"/api/admin/users/{fake_id}",
            json={"role": "admin"},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteUser:
    async def test_delete_user(self, async_client, admin_user, regular_user, admin_token, auth_headers):
        response = await async_client.delete(
            f"/api/admin/users/{regular_user.id}",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200

    async def test_cannot_delete_self(self, async_client, admin_user, admin_token, auth_headers):
        response = await async_client.delete(
            f"/api/admin/users/{admin_user.id}",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 400
