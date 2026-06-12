"""
Helper для best-effort создания уведомлений.

Уведомления — вспомогательные сообщения для пользователя. Сбой их создания
никогда не должен ломать основной ответ API, поэтому весь helper обёрнут
в try/except и только логирует исключение.

Реальная фиксация в БД происходит на коммите сессии вызывающего.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)


def add_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: NotificationType,
) -> None:
    """Best-effort постановка уведомления в текущую сессию.

    Никогда не пробрасывает исключения — все ошибки логируются.
    """
    try:
        db.add(
            Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
            )
        )
    except Exception:
        logger.exception(
            "Не удалось добавить уведомление user_id=%s title=%r", user_id, title
        )
