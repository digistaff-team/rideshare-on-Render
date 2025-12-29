import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Исправление начала строки
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 👇 ВАЖНО: Мы должны УБРАТЬ ?pgbouncer=true из самой строки перед передачей в create_async_engine,
# иначе asyncpg ругается на "extra arguments". Но мы используем это знание для логов.
if "?pgbouncer=true" in DATABASE_URL:
    print("⚠️ Detected pgbouncer param, removing it for asyncpg compatibility")
    DATABASE_URL = DATABASE_URL.replace("?pgbouncer=true", "")
if "&pgbouncer=true" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("&pgbouncer=true", "")

print("🔥🔥🔥 DEBUG: Final DB URL (hidden pass):", DATABASE_URL.split('@')[-1])

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0
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
