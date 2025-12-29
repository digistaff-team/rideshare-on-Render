import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool  # 👈 Импортируем NullPool

# Настройка логгера для отладки
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найдена")

# Исправления URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Очистка параметров pgbouncer
if "?pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "")
if "&pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("&pgbouncer=true", "")

# 👇 ЯВНЫЙ ПРИНТ ДЛЯ ЛОГОВ
print("🔥🔥🔥 DEBUG: ЗАГРУЗКА session.py С НОВЫМИ НАСТРОЙКАМИ (NullPool + cache=0) 🔥🔥🔥")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # 👈 Отключаем удержание соединений в памяти бота
    connect_args={
        "statement_cache_size": 0  # 👈 Запрещаем asyncpg кэшировать запросы
    }
)

async_session = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def init_models():
    from src.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
