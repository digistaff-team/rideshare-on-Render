import os
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Настройки пула соединений
POOL_SIZE = 10
MAX_OVERFLOW = 20
POOL_TIMEOUT = 30
POOL_RECYCLE = 1800  # Пересоздавать соединения каждые 30 минут

# Render использует postgres://, нужно заменить на postgresql+asyncpg://
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        logger.info("Using PostgreSQL database")
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        logger.info("Using PostgreSQL database")
    elif DATABASE_URL.startswith("sqlite"):
        logger.info("Using SQLite database")
else:
    # Для локальной разработки
    DATABASE_URL = "sqlite+aiosqlite:///./test_bot.db"
    logger.info("Using SQLite database (default)")


def create_engine_with_retry(max_retries: int = 5) -> create_async_engine:
    """Создаёт engine с повторными попытками подключения"""
    for attempt in range(max_retries):
        try:
            engine = create_async_engine(
                DATABASE_URL,
                echo=False,
                future=True,
                pool_pre_ping=True,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=POOL_TIMEOUT,
                pool_recycle=POOL_RECYCLE,
            )
            logger.info(f"Database engine created (pool_size={POOL_SIZE}, max_overflow={MAX_OVERFLOW})")
            return engine
        except Exception as e:
            wait_time = 2 ** attempt
            logger.warning(f"DB connection failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                asyncio.sleep(wait_time)
            else:
                raise


engine = create_engine_with_retry()


async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


Base = declarative_base()


async def init_models():
    """Создаёт все таблицы в базе данных с повторными попытками"""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created/verified")
            return
        except Exception as e:
            wait_time = 2 ** attempt
            logger.warning(f"DB init failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                raise
