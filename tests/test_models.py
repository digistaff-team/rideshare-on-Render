"""
Тесты для моделей базы данных.
"""
import pytest
from sqlalchemy import select
from datetime import date, timedelta

from src.database.models import User, Ride, Booking


@pytest.mark.unit
class TestUserModel:
    """Тесты модели User."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """Создание пользователя."""
        user = User(telegram_id=987654321, username="new_user")
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.telegram_id == 987654321)
        )
        saved_user = result.scalar()

        assert saved_user is not None
        assert saved_user.username == "new_user"

    @pytest.mark.asyncio
    async def test_user_unique_telegram_id(self, db_session):
        """Telegram ID должен быть уникальным."""
        user1 = User(telegram_id=111111111, username="user1")
        user2 = User(telegram_id=111111111, username="user2")
        db_session.add(user1)
        await db_session.commit()

        with pytest.raises(Exception):
            db_session.add(user2)
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_user_without_username(self, db_session):
        """Пользователь может быть без username."""
        user = User(telegram_id=222222222)
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.telegram_id == 222222222)
        )
        saved_user = result.scalar()

        assert saved_user is not None
        assert saved_user.username is None


@pytest.mark.unit
class TestRideModel:
    """Тесты модели Ride."""

    @pytest.mark.asyncio
    async def test_create_driver_ride(self, db_session, user):
        """Создание поездки водителя."""
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

        result = await db_session.execute(
            select(Ride).where(Ride.id == ride.id)
        )
        saved_ride = result.scalar()

        assert saved_ride is not None
        assert saved_ride.role == "driver"
        assert saved_ride.seats == 3

    @pytest.mark.asyncio
    async def test_create_passenger_ride(self, db_session, user):
        """Создание поездки пассажира."""
        ride = Ride(
            user_id=user.id,
            role="passenger",
            origin="Здравое",
            destination="Краснодар",
            date=date.today() + timedelta(days=1),
            seats=1,
        )
        db_session.add(ride)
        await db_session.commit()

        result = await db_session.execute(
            select(Ride).where(Ride.id == ride.id)
        )
        saved_ride = result.scalar()

        assert saved_ride is not None
        assert saved_ride.role == "passenger"

    @pytest.mark.asyncio
    async def test_ride_default_seats(self, db_session, user):
        """Количество мест по умолчанию равно 1."""
        ride = Ride(
            user_id=user.id,
            role="driver",
            origin="Краснодар",
            destination="Сказочный край",
            date=date.today() + timedelta(days=1),
        )
        db_session.add(ride)
        await db_session.commit()

        assert ride.seats == 1

    @pytest.mark.asyncio
    async def test_ride_user_relationship(self, db_session, user):
        """Связь Ride -> User."""
        ride = Ride(
            user_id=user.id,
            role="driver",
            origin="Краснодар",
            destination="Сказочный край",
            date=date.today() + timedelta(days=1),
        )
        db_session.add(ride)
        await db_session.commit()

        result = await db_session.execute(
            select(Ride).where(Ride.id == ride.id)
        )
        saved_ride = result.scalar()

        assert saved_ride.user == user


@pytest.mark.unit
class TestBookingModel:
    """Тесты модели Booking."""

    @pytest.mark.asyncio
    async def test_create_booking(self, db_session, driver_ride, passenger_ride):
        """Создание бронирования."""
        booking = Booking(
            driver_ride_id=driver_ride.id,
            passenger_ride_id=passenger_ride.id,
            status="pending",
        )
        db_session.add(booking)
        await db_session.commit()

        result = await db_session.execute(
            select(Booking).where(Booking.id == booking.id)
        )
        saved_booking = result.scalar()

        assert saved_booking is not None
        assert saved_booking.status == "pending"

    @pytest.mark.asyncio
    async def test_booking_default_status(self, db_session, driver_ride, passenger_ride):
        """Статус по умолчанию - pending."""
        booking = Booking(
            driver_ride_id=driver_ride.id,
            passenger_ride_id=passenger_ride.id,
        )
        db_session.add(booking)
        await db_session.commit()

        assert booking.status == "pending"

    @pytest.mark.asyncio
    async def test_booking_update_status(self, db_session, driver_ride, passenger_ride):
        """Обновление статуса бронирования."""
        booking = Booking(
            driver_ride_id=driver_ride.id,
            passenger_ride_id=passenger_ride.id,
            status="pending",
        )
        db_session.add(booking)
        await db_session.commit()

        booking.status = "confirmed"
        await db_session.commit()

        result = await db_session.execute(
            select(Booking).where(Booking.id == booking.id)
        )
        saved_booking = result.scalar()

        assert saved_booking.status == "confirmed"
