"""
Conftest для интеграционных тестов.

Перед запуском: docker-compose up -d + создать тестовую БД:
    docker exec gazprom-db psql -U gazprom -d postgres -c "CREATE DATABASE gazprom_procurement_test;"

Тесты автоматически пропускаются если БД недоступна.
"""
import os

import pytest


TEST_DB_NAME = "gazprom_procurement_test"


def _ensure_test_db_available() -> bool:
    """
    Проверяет доступность postgres на localhost:5433 и создаёт тестовую БД, если её нет.
    Возвращает True если БД готова к использованию.
    """
    try:
        import asyncio
        import asyncpg
    except ImportError:
        return False

    async def _ensure():
        try:
            admin_conn = await asyncpg.connect(
                host="localhost", port=5433,
                user="gazprom", password="gazprom_secret",
                database="postgres", timeout=3.0,
            )
        except Exception:
            return False

        try:
            exists = await admin_conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME,
            )
            if not exists:
                await admin_conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        finally:
            await admin_conn.close()

        # Проверяем что можно подключиться
        try:
            test_conn = await asyncpg.connect(
                host="localhost", port=5433,
                user="gazprom", password="gazprom_secret",
                database=TEST_DB_NAME, timeout=3.0,
            )
            await test_conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_ensure())
    except Exception:
        return False


POSTGRES_AVAILABLE = _ensure_test_db_available()


def pytest_collection_modifyitems(config, items):
    """Помечаем все тесты в integration/ маркером + skip если нет БД."""
    skip_marker = pytest.mark.skip(
        reason="PostgreSQL на localhost:5433 недоступен. Запустите `docker-compose up -d` "
               "и создайте БД `gazprom_procurement_test`."
    )
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            if not POSTGRES_AVAILABLE:
                item.add_marker(skip_marker)
