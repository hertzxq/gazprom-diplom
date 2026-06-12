"""
Integration: notification mark-as-read и list flow.

Главное regression: после PATCH /{id}/read запись остаётся `is_read=True`
после повторного GET (раньше изменение не коммитилось).
"""
import pytest

from app.models.notification import Notification, NotificationType


@pytest.mark.asyncio
class TestMarkAsRead:
    async def test_mark_as_read_persists(
        self, async_client, regular_user, user_token, auth_headers, db_session,
    ):
        # Создаём уведомление напрямую в БД
        notification = Notification(
            user_id=regular_user.id,
            title="Test",
            message="hello",
            notification_type=NotificationType.INFO,
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)

        # Mark as read
        resp = await async_client.patch(
            f"/api/notifications/{notification.id}/read",
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

        # Read back via list — должно остаться True
        list_resp = await async_client.get(
            "/api/notifications/", headers=auth_headers(user_token),
        )
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert any(n["id"] == str(notification.id) and n["is_read"] is True for n in items)

    async def test_mark_as_read_returns_404_for_other_user(
        self, async_client, regular_user, admin_user, user_token, auth_headers, db_session,
    ):
        # Уведомление для admin_user
        notification = Notification(
            user_id=admin_user.id,
            title="Admin only",
            message="x",
            notification_type=NotificationType.INFO,
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)

        # regular_user пытается mark-as-read чужое уведомление
        resp = await async_client.patch(
            f"/api/notifications/{notification.id}/read",
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListNotifications:
    async def test_unread_only_filter(
        self, async_client, regular_user, user_token, auth_headers, db_session,
    ):
        for i, is_read in enumerate([True, False, False]):
            db_session.add(Notification(
                user_id=regular_user.id,
                title=f"N{i}",
                message="x",
                notification_type=NotificationType.INFO,
                is_read=is_read,
            ))
        await db_session.commit()

        all_resp = await async_client.get(
            "/api/notifications/", headers=auth_headers(user_token),
        )
        assert len(all_resp.json()) == 3

        unread_resp = await async_client.get(
            "/api/notifications/?unread_only=true", headers=auth_headers(user_token),
        )
        assert len(unread_resp.json()) == 2

    async def test_mark_all_as_read(
        self, async_client, regular_user, user_token, auth_headers, db_session,
    ):
        for i in range(3):
            db_session.add(Notification(
                user_id=regular_user.id,
                title=f"N{i}",
                message="x",
                notification_type=NotificationType.INFO,
                is_read=False,
            ))
        await db_session.commit()

        resp = await async_client.patch(
            "/api/notifications/read-all", headers=auth_headers(user_token),
        )
        assert resp.status_code == 200

        unread_resp = await async_client.get(
            "/api/notifications/?unread_only=true", headers=auth_headers(user_token),
        )
        assert unread_resp.json() == []
