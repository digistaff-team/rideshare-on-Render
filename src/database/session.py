import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Создаём Base для моделей
Base = declarative_base()

# Получаем DATABASE_URL из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render может давать postgresql:// или postgres://
    # Для asyncpg нужен postgresql+asyncpg://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"DEBUG: Connecting to DB with scheme: {DATABASE_URL.split(':')[0]}")
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    # Fallback на SQLite для локальной разработки
    print("DEBUG: Using SQLite database")
    DATABASE_URL = "sqlite+aiosqlite:///./test_bot.db"
    engine = create_async_engine(DATABASE_URL, echo=False)

# Создаём фабрику сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_models():
    """Создание таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created/verified")
