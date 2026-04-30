# v1.2 - notifications, admin, analytics, export
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings, SMSP_DEFAULT_RULES
from app.database import engine, Base, async_session
from app.models import User, UserRole, SmspExclusionRule
from app.utils.auth import hash_password
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.manufacturers import router as manufacturers_router
from app.api.notifications import router as notifications_router
from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create default admin user if not exists
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@gazprom.local",
                password_hash=hash_password("admin"),
                full_name="Администратор",
                role=UserRole.ADMIN,
            )
            session.add(admin)
            await session.commit()

        # Сид правил категоризации «Исключение из СМСП» при пустой таблице.
        existing = await session.execute(select(SmspExclusionRule.id).limit(1))
        if existing.first() is None:
            for category, keywords, point_letter, order_idx in SMSP_DEFAULT_RULES:
                session.add(SmspExclusionRule(
                    category=category,
                    keywords=keywords,
                    point_letter=point_letter,
                    order_idx=order_idx,
                    enabled=True,
                ))
            await session.commit()

    # Create upload directories
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Система поддержки закупочной деятельности",
    description="Автоматизация заполнения XLS-форм для ЕИС, обработка реестров, поиск производителей",
    version="1.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(manufacturers_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(analytics_router)


@app.get("/api/health")
async def health_check():
    """Проверка работоспособности API."""
    return {"status": "ok", "version": "1.2.0"}

