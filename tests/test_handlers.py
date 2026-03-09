"""
Интеграционные тесты для обработчиков бота.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import types
from sqlalchemy import select

from src.bot.handlers import (
    start,
    find_rides,
    list_rides,
    process_ride_data,
    delete_ride,
)
from src.database.models import User, Ride


@pytest.mark.integration
@pytest.mark.asyncio
class TestStartHandler:
    """Тесты обработчика /start."""

    async def test_start_new_user(self, mock_message, mock_state, db_session):
        """Приветствие нового пользователя."""
        with patch('src.bot.handlers.async_session', return_value=db_session):
            await start(mock_message, mock_state)

        # Проверяем, что пользователь создан
        result = await db_session.execute(
            select(User).where(User.telegram_id == mock_message.from_user.id)
        )
        user = result.scalar()
        assert user is not None
        assert user.username == "test_user"

    async def test_start_existing_user(self, mock_message, mock_state, db_session, user):
        """Приветствие существующего пользователя."""
        # Пользователь уже создан в фикстуре
        mock_message.from_user.id = user.telegram_id

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await start(mock_message, mock_state)

        # Проверяем, что ответ отправлен
        mock_message.answer.assert_called_once()

    async def test_start_clears_state(self, mock_message, mock_state, db_session):
        """/start должен очищать состояние FSM."""
        with patch('src.bot.handlers.async_session', return_value=db_session):
            await start(mock_message, mock_state)

        mock_state.clear.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
class TestFindRidesHandler:
    """Тесты обработчика поиска поездок."""

    async def test_find_rides_empty(self, mock_message, mock_state, db_session):
        """Поиск при отсутствии поездок."""
        with patch('src.bot.handlers.async_session', return_value=db_session):
            await find_rides(mock_message, mock_state)

        mock_message.answer.assert_called_once()
        assert "Нет актуальных объявлений" in mock_message.answer.call_args[0][0]

    async def test_find_rides_with_data(self, mock_message, mock_state, db_session, driver_ride):
        """Поиск с наличием поездок."""
        with patch('src.bot.handlers.async_session', return_value=db_session):
            await find_rides(mock_message, mock_state)

        # Проверяем, что ответ был отправлен
        assert mock_message.answer.called


@pytest.mark.integration
@pytest.mark.asyncio
class TestListRidesHandler:
    """Тесты обработчика списка поездок пользователя."""

    async def test_list_rides_empty(self, mock_message, mock_state, db_session, user):
        """Список поездок пуст."""
        mock_message.from_user.id = user.telegram_id

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await list_rides(mock_message, mock_state)

        mock_message.answer.assert_called_once()
        assert "нет активных поездок" in mock_message.answer.call_args[0][0].lower()

    async def test_list_rides_with_data(self, mock_message, mock_state, db_session, driver_ride):
        """Список с наличием поездок."""
        mock_message.from_user.id = driver_ride.user.telegram_id

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await list_rides(mock_message, mock_state)

        # Проверяем, что ответ был отправлен с информацией о поездке
        assert mock_message.answer.called


@pytest.mark.integration
@pytest.mark.asyncio
class TestProcessRideData:
    """Тесты сохранения поездки."""

    async def test_process_ride_data_driver(
        self, mock_message, mock_state, db_session, user
    ):
        """Сохранение поездки водителя."""
        mock_message.from_user.id = user.telegram_id
        mock_state.get_data = AsyncMock(return_value={"role": "driver"})

        ride_data = {
            "origin": "Краснодар",
            "destination": "Сказочный край",
            "date": "2024-03-15",
            "start_time": "10:00",
            "seats": 2,
        }

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await process_ride_data(mock_message, ride_data, mock_state)

        # Проверяем, что поездка создана
        result = await db_session.execute(select(Ride))
        rides = result.scalars().all()
        assert len(rides) == 1
        assert rides[0].role == "driver"
        assert rides[0].seats == 2

    async def test_process_ride_data_passenger(
        self, mock_message, mock_state, db_session, user
    ):
        """Сохранение поездки пассажира."""
        mock_message.from_user.id = user.telegram_id
        mock_state.get_data = AsyncMock(return_value={"role": "passenger"})

        ride_data = {
            "origin": "Здравое",
            "destination": "Краснодар",
            "date": "2024-03-15",
            "seats": 1,
        }

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await process_ride_data(mock_message, ride_data, mock_state)

        # Проверяем, что поездка создана
        result = await db_session.execute(select(Ride))
        rides = result.scalars().all()
        assert len(rides) == 1
        assert rides[0].role == "passenger"


@pytest.mark.asyncio
class TestDeleteRideHandler:
    """Тесты удаления поездки."""

    async def test_delete_ride_success(
        self, mock_callback_query, db_session, driver_ride
    ):
        """Успешное удаление поездки."""
        mock_callback_query.data = f"del_{driver_ride.id}"

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await delete_ride(mock_callback_query)

        # Проверяем, что поездка удалена
        result = await db_session.execute(select(Ride).where(Ride.id == driver_ride.id))
        ride = result.scalar()
        assert ride is None

    async def test_delete_ride_not_found(self, mock_callback_query, db_session):
        """Удаление несуществующей поездки."""
        mock_callback_query.data = "del_99999"

        with patch('src.bot.handlers.async_session', return_value=db_session):
            await delete_ride(mock_callback_query)

        mock_callback_query.answer.assert_called_once()
        assert "уже удалена" in mock_callback_query.answer.call_args[0][0].lower()
