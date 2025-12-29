import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Получаем URL
raw_url = os.getenv("DATABASE_URL")

if not raw_url:
    raise ValueError("DATABASE_URL is missing!")

# ПРИНУДИТЕЛЬНАЯ ЗАМЕНА СХЕМЫ
# Мы используем asyncpg, поэтому URL ОБЯЗАН начинаться с postgresql+asyncpg://
# Даже если там было postgresql:// или postgres:// - мы это перепишем.

# Разбираем URL (грубо), чтобы заменить только начало
scheme, rest = raw_url.split("://", 1)
DATABASE_URL = f"postgresql+asyncpg://{rest}"

print(f"DEBUG: Connecting to DB with scheme: {DATABASE_URL.split('://')[0]}")

# Создаем движок
engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

async def init_models():
    from src.database.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
