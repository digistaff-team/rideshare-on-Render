import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Получаем URL из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найдена")

# Заменяем протокол на postgresql+asyncpg
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# ВАЖНО: Удаляем параметр pgbouncer=true, так как asyncpg его не понимает напрямую
if "?pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "")
if "&pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("&pgbouncer=true", "")
    
# Создаем движок
# Для Supabase (Transaction Pool 6543) нужно отключить prepared_statement_cache_size
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "prepared_statement_cache_size": 0,  # <--- Это критически важно для Supabase Pooler
        "statement_cache_size": 0
    }
)

# Создаем фабрику сессий
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_models():
    from src.database.models import Base
    async with engine.begin() as conn:
        # Создаем таблицы, если их нет
        await conn.run_sync(Base.metadata.create_all)

