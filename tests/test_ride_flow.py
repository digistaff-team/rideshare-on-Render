"""
Тесты пошагового FSM-флоу создания поездки (без NLU).
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from src.bot.handlers import (
    ask_route,
    handle_ride_input,
    handle_ride_origin,
    handle_ride_destination,
    handle_ride_date,
    confirm_ride,
    cancel_ride,
    _parse_city_from_text,
)
from src.database.models import Ride


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _make_message(text: str, user_id: int = 123456789, username: str = "test_user"):
    msg = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.text = text
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()
    return msg


def _make_state(data: dict | None = None):
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


# ---------------------------------------------------------------------------
# Юнит: _parse_city_from_text
# ---------------------------------------------------------------------------

class TestParseCityFromText:
    def test_exact_button_match(self):
        assert _parse_city_from_text("Краснодар") == "Краснодар"

    def test_partial_match(self):
        assert _parse_city_from_text("Сказочный") == "Сказочный край"

    def test_lowercase(self):
        assert _parse_city_from_text("краснодар") == "Краснодар"

    def test_zdravoe_prefix(self):
        # Пользователь вводит начало слова — совпадает по подстроке
        assert _parse_city_from_text("Здрав") == "Здравое"

    def test_unknown_returns_none(self):
        assert _parse_city_from_text("Москва") is None

    def test_empty_returns_none(self):
        assert _parse_city_from_text("") is None


# ---------------------------------------------------------------------------
# ask_route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAskRoute:
    async def test_sets_passenger_role(self):
        msg = _make_message("🙋 Подвези")
        state = _make_state()
        await ask_route(msg, state)
        state.update_data.assert_called_once_with(role="passenger")
        msg.answer.assert_called_once()

    async def test_sets_driver_role(self):
        msg = _make_message("🚗 Подвезу")
        state = _make_state()
        await ask_route(msg, state)
        state.update_data.assert_called_once_with(role="driver")
        msg.answer.assert_called_once()

    async def test_clears_state_first(self):
        msg = _make_message("🙋 Подвези")
        state = _make_state()
        await ask_route(msg, state)
        state.clear.assert_called_once()


# ---------------------------------------------------------------------------
# handle_ride_input — парсинг первого сообщения
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHandleRideInput:
    async def test_full_message_sets_all_fields(self):
        """Сообщение с маршрутом, датой и временем — все поля в state."""
        msg = _make_message("Из Краснодара в Сказочный завтра в 9 утра, 2 места")
        state = _make_state({"role": "driver"})
        await handle_ride_input(msg, state)

        call_kwargs = {}
        for call in state.update_data.call_args_list:
            call_kwargs.update(call.kwargs if call.kwargs else call.args[0] if call.args else {})

        assert "origin" in call_kwargs
        assert "destination" in call_kwargs
        assert "date" in call_kwargs

    async def test_empty_message_proceeds_to_origin_question(self):
        """Пустое сообщение без данных → спрашивает откуда."""
        msg = _make_message("привет")
        state = _make_state({"role": "passenger"})
        await handle_ride_input(msg, state)
        state.set_state.assert_called_once()
        msg.answer.assert_called_once()
        assert "Откуда" in msg.answer.call_args[0][0]


# ---------------------------------------------------------------------------
# handle_ride_origin / handle_ride_destination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHandleRideOrigin:
    async def test_valid_city_saved(self):
        msg = _make_message("Краснодар")
        state = _make_state({"role": "passenger"})
        await handle_ride_origin(msg, state)
        state.update_data.assert_called_with(origin="Краснодар")

    async def test_unknown_city_shows_error(self):
        msg = _make_message("Нью-Йорк")
        state = _make_state({"role": "passenger"})
        await handle_ride_origin(msg, state)
        msg.answer.assert_called_once()
        assert "Не распознан" in msg.answer.call_args[0][0]

    async def test_partial_city_name_accepted(self):
        msg = _make_message("Сказочный")
        state = _make_state({"role": "driver", "origin": "Краснодар"})
        await handle_ride_destination(msg, state)
        state.update_data.assert_called_with(destination="Сказочный край")


# ---------------------------------------------------------------------------
# handle_ride_date
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHandleRideDate:
    async def test_today_button(self):
        today = date.today()
        msg = _make_message(f"Сегодня ({today.strftime('%d.%m')})")
        state = _make_state({"role": "passenger", "origin": "Здравое", "destination": "Краснодар"})
        await handle_ride_date(msg, state)
        state.update_data.assert_called_with(date=today.strftime("%Y-%m-%d"))

    async def test_tomorrow_button(self):
        tomorrow = date.today() + timedelta(days=1)
        msg = _make_message(f"Завтра ({tomorrow.strftime('%d.%m')})")
        state = _make_state({"role": "passenger", "origin": "Здравое", "destination": "Краснодар"})
        await handle_ride_date(msg, state)
        state.update_data.assert_called_with(date=tomorrow.strftime("%Y-%m-%d"))

    async def test_day_after_tomorrow(self):
        day_after = date.today() + timedelta(days=2)
        msg = _make_message(f"Послезавтра ({day_after.strftime('%d.%m')})")
        state = _make_state({"role": "driver", "origin": "Здравое", "destination": "Краснодар"})
        await handle_ride_date(msg, state)
        state.update_data.assert_called_with(date=day_after.strftime("%Y-%m-%d"))

    async def test_explicit_date_ddmm(self):
        msg = _make_message("15.06.2026")
        state = _make_state({"role": "passenger", "origin": "Здравое", "destination": "Краснодар"})
        await handle_ride_date(msg, state)
        state.update_data.assert_called_with(date="2026-06-15")

    async def test_invalid_date_shows_error(self):
        msg = _make_message("когда-нибудь")
        state = _make_state({"role": "passenger", "origin": "Здравое", "destination": "Краснодар"})
        await handle_ride_date(msg, state)
        msg.answer.assert_called_once()
        assert "Не понял" in msg.answer.call_args[0][0]


# ---------------------------------------------------------------------------
# confirm_ride / cancel_ride
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
class TestConfirmRide:
    async def test_saves_ride_on_confirm(self, mock_message, mock_state, db_session, user):
        mock_message.from_user.id = user.telegram_id
        mock_state.get_data = AsyncMock(return_value={
            "role": "driver",
            "origin": "Краснодар",
            "destination": "Сказочный край",
            "date": "2026-06-15",
            "start_time": "09:00",
            "seats": 2,
        })
        with patch("src.bot.handlers.async_session", return_value=db_session):
            await confirm_ride(mock_message, mock_state)

        result = await db_session.execute(select(Ride))
        rides = result.scalars().all()
        assert len(rides) == 1
        assert rides[0].origin == "Краснодар"
        assert rides[0].role == "driver"


@pytest.mark.asyncio
class TestCancelRide:
    async def test_clears_state_and_shows_main_kb(self):
        msg = _make_message("❌ Отменить")
        state = _make_state()
        await cancel_ride(msg, state)
        state.clear.assert_called_once()
        msg.answer.assert_called_once()
        assert "Отменено" in msg.answer.call_args[0][0]
