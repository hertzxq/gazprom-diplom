import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc, func, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.document import Document, ProcessingTask
from app.models.notification import Notification
from app.schemas import UserResponse, UserUpdateAdmin
from app.utils.auth import require_role

router = APIRouter(prefix="/api/admin", tags=["Администрирование"])


async def _count_active_admins(db: AsyncSession) -> int:
    """Сколько активных администраторов есть в системе."""
    result = await db.execute(
        select(func.count(User.id)).where(
            User.role == UserRole.ADMIN, User.is_active == True  # noqa: E712
        )
    )
    return int(result.scalar() or 0)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Список всех пользователей (только для администраторов)."""
    result = await db.execute(
        select(User).order_by(desc(User.created_at))
    )
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Обновление пользователя (роль, статус)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == current_user.id and data.is_active is False:
        raise HTTPException(
            status_code=400, detail="Нельзя деактивировать собственную учётную запись"
        )

    # Защита от потери последнего активного администратора:
    # понижение роли ИЛИ деактивация админа должны оставить ≥1 активного админа.
    will_lose_admin_status = (
        user.role == UserRole.ADMIN and user.is_active and (
            (data.role is not None and data.role != UserRole.ADMIN)
            or (data.is_active is False)
        )
    )
    if will_lose_admin_status:
        active_admins = await _count_active_admins(db)
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Нельзя оставить систему без активного администратора",
            )

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.full_name is not None:
        user.full_name = data.full_name

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Удаление пользователя."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Нельзя удалить собственную учётную запись"
        )

    # Защита: удаление активного админа не должно оставить систему без админов.
    if user.role == UserRole.ADMIN and user.is_active:
        active_admins = await _count_active_admins(db)
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалить последнего активного администратора",
            )

    # У пользователя может быть операционная история, на которую смотрят
    # внешние ключи (раньше это роняло удаление 500-кой IntegrityError).
    # Документы и задачи сохраняем для аналитики, но отвязываем от пользователя;
    # уведомления — личные, удаляем вместе с учётной записью.
    await db.execute(
        update(Document).where(Document.uploaded_by == user.id).values(uploaded_by=None)
    )
    await db.execute(
        update(ProcessingTask).where(ProcessingTask.created_by == user.id).values(created_by=None)
    )
    await db.execute(
        sa_delete(Notification).where(Notification.user_id == user.id)
    )

    await db.delete(user)
    await db.commit()
    return {"message": f"Пользователь {user.username} удалён"}
