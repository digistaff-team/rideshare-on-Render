import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 1. Получаем URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing!")

# 2. ОБЯЗАТЕЛЬНОЕ ИСПРАВЛЕНИЕ ДЛЯ RENDER
# Render дает ссылку вида postgres://..., а нам нужно postgresql+asyncpg://...
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# 3. Создаем движок
# Для внутренней базы Render (Internal URL) дополнительные аргументы не нужны
engine = create_async_engine(DATABASE_URL, echo=False)

# 4. Фабрика сессий
async_session = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def init_models():
    from src.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
