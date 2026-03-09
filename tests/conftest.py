"""
Конфигурация тестов и общие фикстуры.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.session import Base
from src.database.models import User, Ride, Booking
from src.config import ROUTE_ORDER


# Фикстура для асинхронной тестовой БД (SQLite in-memory)
@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Создаёт тестовый SQLite engine в памяти."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Создаёт тестовую сессию БД."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def user(db_session):
    """Создаёт тестового пользователя."""
    user = User(telegram_id=123456789, username="test_user")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def driver_ride(db_session, user):
    """Создаёт тестовую поездку водителя."""
    from datetime import date, timedelta
    ride = Ride(
        user_id=user.id,
        role="driver",
        origin="Краснодар",
        destination="Сказочный край",
        date=date.today() + timedelta(days=1),
        start_time="10:00",
        seats=3,
    )
    db_session.add(ride)
    await db_session.commit()
    await db_session.refresh(ride)
    return ride


@pytest_asyncio.fixture
async def passenger_ride(db_session, user):
    """Создаёт тестовую поездку пассажира."""
    from datetime import date, timedelta
    ride = Ride(
        user_id=user.id,
        role="passenger",
        origin="Здравое",
        destination="Краснодар",
        date=date.today() + timedelta(days=1),
        start_time=None,
        seats=1,
    )
    db_session.add(ride)
    await db_session.commit()
    await db_session.refresh(ride)
    return ride


@pytest.fixture
def mock_bot():
    """Создаёт мок бота."""
    bot = AsyncMock()
    bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    bot.session = AsyncMock()
    return bot


@pytest.fixture
def mock_message():
    """Создаёт мок сообщения."""
    message = MagicMock()
    message.from_user.id = 123456789
    message.from_user.username = "test_user"
    message.text = ""
    message.answer = AsyncMock()
    message.bot = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query():
    """Создаёт мок callback query."""
    callback = MagicMock()
    callback.from_user.id = 123456789
    callback.from_user.username = "test_user"
    callback.data = ""
    callback.message = MagicMock()
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.bot = AsyncMock()
    return callback


@pytest.fixture
def mock_state():
    """Создаёт мок FSM state."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.fixture
def route_order():
    """Возвращает список маршрутов."""
    return ROUTE_ORDER
