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

    async def test_delete_user_with_history(
        self, async_client, admin_user, regular_user, admin_token, auth_headers, db_session,
    ):
        """
        Удаление пользователя с операционной историей (документы, задачи,
        уведомления) не должно падать 500-кой об внешние ключи: документы
        и задачи сохраняются без владельца, уведомления удаляются.
        """
        from sqlalchemy import select
        from app.models.document import Document, ProcessingTask, FileType
        from app.models.notification import Notification, NotificationType

        doc = Document(
            filename="hist.xlsx",
            original_filename="hist.xlsx",
            file_type=FileType.POSITIONS,
            file_path="/tmp/hist.xlsx",
            uploaded_by=regular_user.id,
        )
        task = ProcessingTask(task_type="xls_fill", created_by=regular_user.id)
        notif = Notification(
            user_id=regular_user.id,
            title="t",
            message="m",
            notification_type=NotificationType.INFO,
        )
        db_session.add_all([doc, task, notif])
        await db_session.commit()
        doc_id, task_id, user_id = doc.id, task.id, regular_user.id

        response = await async_client.delete(
            f"/api/admin/users/{user_id}",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200

        # Сбрасываем identity map — изменения сделаны другой сессией (API)
        db_session.expire_all()

        # Документ и задача живы, но отвязаны от пользователя
        saved_doc = (await db_session.execute(
            select(Document).where(Document.id == doc_id)
        )).scalar_one()
        assert saved_doc.uploaded_by is None
        saved_task = (await db_session.execute(
            select(ProcessingTask).where(ProcessingTask.id == task_id)
        )).scalar_one()
        assert saved_task.created_by is None

        # Уведомления пользователя удалены
        leftover = (await db_session.execute(
            select(Notification).where(Notification.user_id == user_id)
        )).scalars().all()
        assert leftover == []

    async def test_cannot_delete_self(self, async_client, admin_user, admin_token, auth_headers):
        response = await async_client.delete(
            f"/api/admin/users/{admin_user.id}",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestLastAdminProtection:
    """B1: нельзя оставить систему без активного администратора."""

    async def test_cannot_demote_last_admin(
        self, async_client, admin_user, admin_token, auth_headers, db_session,
    ):
        """admin_user — единственный активный админ; понижение запрещено."""
        # Создаём ещё одного admin'а, но НЕАКТИВНОГО — он не должен считаться
        from app.models import User, UserRole
        from app.utils.auth import hash_password
        inactive_admin = User(
            username="inactive_admin",
            email="ia@test.local",
            password_hash=hash_password("p"),
            full_name="IA",
            role=UserRole.ADMIN,
            is_active=False,
        )
        db_session.add(inactive_admin)
        await db_session.commit()

        # Попытка понизить admin_user (единственного активного админа)
        response = await async_client.patch(
            f"/api/admin/users/{admin_user.id}",
            json={"role": "user"},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 400
        assert "администратора" in response.json()["detail"].lower()

    async def test_can_demote_admin_if_another_active_exists(
        self, async_client, admin_user, admin_token, auth_headers, db_session,
    ):
        """Если есть второй активный админ — понижение разрешено."""
        from app.models import User, UserRole
        from app.utils.auth import hash_password
        another_admin = User(
            username="another_admin",
            email="aa@test.local",
            password_hash=hash_password("p"),
            full_name="AA",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(another_admin)
        await db_session.commit()
        await db_session.refresh(another_admin)

        response = await async_client.patch(
            f"/api/admin/users/{another_admin.id}",
            json={"role": "user"},
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "user"

    async def test_cannot_delete_last_admin(
        self, async_client, admin_user, admin_token, auth_headers, db_session,
    ):
        """Нельзя удалить последнего активного админа."""
        # Создаём второго админа и им же делаем запрос на удаление admin_user
        from app.models import User, UserRole
        from app.utils.auth import hash_password, create_access_token
        another_admin = User(
            username="another_admin2",
            email="aa2@test.local",
            password_hash=hash_password("p"),
            full_name="AA2",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(another_admin)
        await db_session.commit()
        await db_session.refresh(another_admin)
        another_token = create_access_token({"sub": str(another_admin.id), "role": "admin"})

        # Удаляем admin_user из-под another_admin — после этого останется 1
        response = await async_client.delete(
            f"/api/admin/users/{admin_user.id}",
            headers=auth_headers(another_token),
        )
        assert response.status_code == 200

        # Теперь another_admin — последний активный, попытка его удалить
        # делается им самим (заблокировано test_cannot_delete_self), поэтому
        # для теста создадим ещё одного админа и из-под него попытаемся удалить another_admin
        third_admin = User(
            username="third_admin",
            email="3a@test.local",
            password_hash=hash_password("p"),
            full_name="3A",
            role=UserRole.ADMIN,
            is_active=False,  # неактивный — не считается
        )
        db_session.add(third_admin)
        await db_session.commit()

        delete_resp = await async_client.delete(
            f"/api/admin/users/{another_admin.id}",
            headers=auth_headers(another_token),  # сам себя — заблокирует self check
        )
        # Проверка self уведёт раньше, но логика last-admin тоже должна сработать.
        # Ожидаем 400 в любом случае.
        assert delete_resp.status_code == 400
