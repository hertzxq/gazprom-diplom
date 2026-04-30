"""
Integration: auth flow (login, /me, 401 на невалидном токене, 403 при неактивном пользователе).
"""
import pytest


@pytest.mark.asyncio
class TestLogin:
    async def test_admin_login_success(self, async_client, admin_user):
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "test_admin", "password": "adminpass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_wrong_password(self, async_client, admin_user):
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "test_admin", "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_unknown_user(self, async_client):
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "anything"},
        )
        assert response.status_code == 401

    async def test_inactive_user_cannot_login(self, async_client, regular_user, db_session):
        regular_user.is_active = False
        await db_session.commit()
        response = await async_client.post(
            "/api/auth/login",
            json={"username": "test_user", "password": "userpass"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
class TestGetMe:
    async def test_returns_current_user(self, async_client, regular_user, user_token, auth_headers):
        response = await async_client.get("/api/auth/me", headers=auth_headers(user_token))
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "test_user"
        assert data["role"] == "user"

    async def test_no_token_returns_403(self, async_client):
        response = await async_client.get("/api/auth/me")
        # HTTPBearer отсутствие → 403
        assert response.status_code in (401, 403)

    async def test_invalid_token_returns_401(self, async_client, auth_headers):
        response = await async_client.get("/api/auth/me", headers=auth_headers("garbage.token.here"))
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRegister:
    async def test_admin_can_register_user(self, async_client, admin_user, admin_token, auth_headers):
        response = await async_client.post(
            "/api/auth/register",
            json={
                "username": "new_user",
                "email": "new@test.local",
                "password": "securepass",
                "full_name": "New User",
            },
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "new_user"
        assert data["role"] == "user"

    async def test_regular_user_cannot_register(self, async_client, regular_user, user_token, auth_headers):
        response = await async_client.post(
            "/api/auth/register",
            json={
                "username": "another",
                "email": "another@test.local",
                "password": "pass",
            },
            headers=auth_headers(user_token),
        )
        assert response.status_code == 403

    async def test_duplicate_username_conflict(self, async_client, admin_user, admin_token, auth_headers):
        response = await async_client.post(
            "/api/auth/register",
            json={
                "username": "test_admin",
                "email": "other@test.local",
                "password": "pass",
            },
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 409
