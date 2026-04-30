"""
Глобальные фикстуры для тестов.

Unit-тесты — без БД, без сети.
Integration-тесты (маркер `integration`) — через тестовую PostgreSQL в docker
(gazprom-db, порт 5433, отдельная БД gazprom_procurement_test).
"""
import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio


# Подменяем переменные окружения до импорта app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://gazprom:gazprom_secret@localhost:5433/gazprom_procurement_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://gazprom:gazprom_secret@localhost:5433/gazprom_procurement_test",
)
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama-mock.test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")

TEST_UPLOAD_DIR = Path(__file__).parent / "_tmp_uploads"
TEST_GENERATED_DIR = Path(__file__).parent / "_tmp_generated"
TEST_UPLOAD_DIR.mkdir(exist_ok=True)
TEST_GENERATED_DIR.mkdir(exist_ok=True)


# ─── Integration: тестовая БД ─────────────────────────────────────────
# Каждый тест получает свой engine и session, чтобы избежать
# "another operation is in progress" при параллельных async-фикстурах.


@pytest_asyncio.fixture
async def test_engine():
    """
    Async engine для тестовой БД. Создаёт/дропает все таблицы на каждый тест.
    БД должна уже существовать (создаётся автоматически в integration/conftest.py).
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings
    from app.database import Base
    # Импорт моделей регистрирует их в Base.metadata
    import app.models  # noqa: F401

    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Сессия на каждый тест. Коммитит изменения (нужны для API-запросов в том же тесте)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        # Не откатываем — данные нужны API-клиенту через override
        try:
            await session.commit()
        except Exception:
            await session.rollback()


@pytest_asyncio.fixture
async def async_client(test_engine, monkeypatch):
    """
    HTTP-клиент для FastAPI с override get_db → свежая сессия из того же engine.
    Подменяем каталоги загрузки на временные.
    """
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.main import app
    from app.database import get_db
    from app.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", TEST_UPLOAD_DIR)
    monkeypatch.setattr(settings, "GENERATED_DIR", TEST_GENERATED_DIR)

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Создаёт admin-пользователя в тестовой БД."""
    from app.models import User, UserRole
    from app.utils.auth import hash_password

    user = User(
        username="test_admin",
        email="admin@test.local",
        password_hash=hash_password("adminpass"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session):
    """Создаёт обычного пользователя."""
    from app.models import User, UserRole
    from app.utils.auth import hash_password

    user = User(
        username="test_user",
        email="user@test.local",
        password_hash=hash_password("userpass"),
        full_name="Test User",
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user):
    from app.utils.auth import create_access_token
    return create_access_token({"sub": str(admin_user.id), "username": admin_user.username})


@pytest_asyncio.fixture
async def user_token(regular_user):
    from app.utils.auth import create_access_token
    return create_access_token({"sub": str(regular_user.id), "username": regular_user.username})


@pytest.fixture
def auth_headers():
    """Хелпер для создания заголовков с токеном."""
    def _make(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _make


# ─── Ollama: автоскип LLM-тестов если Ollama недоступна ───────────────


REAL_OLLAMA_URL = "http://localhost:11434"


def _check_ollama_available() -> bool:
    """Быстрая проверка живости Ollama по REAL_OLLAMA_URL/api/tags."""
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen(f"{REAL_OLLAMA_URL}/api/tags", timeout=2.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


_OLLAMA_AVAILABLE: bool | None = None


def pytest_collection_modifyitems(config, items):
    """Автоматический skip для тестов с маркером llm, если Ollama не отвечает."""
    global _OLLAMA_AVAILABLE
    needs_check = any(any(m.name == "llm" for m in item.iter_markers()) for item in items)
    if not needs_check:
        return

    if _OLLAMA_AVAILABLE is None:
        _OLLAMA_AVAILABLE = _check_ollama_available()

    if _OLLAMA_AVAILABLE:
        return

    skip_marker = pytest.mark.skip(
        reason=f"Ollama недоступна на {REAL_OLLAMA_URL}. Запустите docker-compose up -d "
               "и убедитесь, что модель загружена: "
               "docker exec gazprom-ollama ollama pull mistral:7b-instruct-v0.3-q4_K_M"
    )
    for item in items:
        if any(m.name == "llm" for m in item.iter_markers()):
            item.add_marker(skip_marker)


@pytest.fixture
def real_ollama_settings(monkeypatch):
    """
    Подменяет settings.OLLAMA_BASE_URL на реальный URL вместо mock-URL,
    подставленного в начале conftest.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", REAL_OLLAMA_URL)
    return settings


# ─── Ollama мок (respx) ───────────────────────────────────────────────


@pytest.fixture
def mock_ollama_success():
    """
    Возвращает фабрику respx-мока Ollama-ответа.
    Использование:
        with mock_ollama_success(response_number=5):
            ...
    """
    import respx
    from httpx import Response
    from app.config import settings

    def _factory(response_number: int = 0, status_code: int = 200):
        mock = respx.mock(base_url=settings.OLLAMA_BASE_URL, assert_all_called=False)
        mock.post("/api/generate").mock(
            return_value=Response(
                status_code,
                json={"response": str(response_number)},
            )
        )
        return mock

    return _factory
