import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL")


# Render использует postgres://, нужно заменить на postgresql+asyncpg://
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        print(f"DEBUG: Using PostgreSQL database")
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        print(f"DEBUG: Using PostgreSQL database")
    elif DATABASE_URL.startswith("sqlite"):
        print(f"DEBUG: Using SQLite database")
else:
    # Для локальной разработки
    DATABASE_URL = "sqlite+aiosqlite:///./test_bot.db"
    print(f"DEBUG: Using SQLite database (default)")


engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    future=True,
    pool_pre_ping=True  # Проверка соединения перед использованием
)


async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


Base = declarative_base()


async def init_models():
    """Создаёт все таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created/verified")
