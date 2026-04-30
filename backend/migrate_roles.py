"""
Миграция enum UserRole в PostgreSQL:
PostgreSQL хранит ИМЕНА enum (ADMIN, OPERATOR, VIEWER), а не значения.
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    # Шаг 1: добавить 'USER' (uppercase!) в enum
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'USER'"))

    # Шаг 2: обновить записи OPERATOR/VIEWER -> USER
    async with engine.begin() as conn:
        await conn.execute(text(
            "UPDATE users SET role = 'USER' WHERE role::text IN ('OPERATOR', 'VIEWER')"
        ))
        
        # Проверка
        result = await conn.execute(text("SELECT username, role::text FROM users"))
        rows = result.fetchall()
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
        print(f"Миграция завершена. Всего пользователей: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(migrate())
