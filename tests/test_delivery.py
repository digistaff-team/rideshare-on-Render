"""
Тесты для модуля доставки (Delivery Module).
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import select

from src.database.models import DeliveryRequest, DeliveryOffer, DeliveryMatch
from src.bot.handlers import parse_delivery_text


@pytest.mark.unit
class TestParseDeliveryText:
    """Тесты парсера текста для доставки."""

    def test_parse_store_pyaterochka(self):
        result = parse_delivery_text("Привези из Пятёрочки")
        assert result["store"] == "Пятёрочка"

    def test_parse_store_magnit(self):
        result = parse_delivery_text("Нужно из Магнита")
        assert result["store"] == "Магнит"

    def test_parse_store_perekrestok(self):
        result = parse_delivery_text("Еду в Перекрёсток")
        assert result["store"] == "Перекрёсток"

    def test_parse_store_lenta(self):
        result = parse_delivery_text("Закажу из Ленты")
        assert result["store"] == "Лента"

    def test_parse_store_ashan(self):
        result = parse_delivery_text("Продукты из Ашана")
        assert result["store"] == "Ашан"

    def test_parse_date_today(self):
        result = parse_delivery_text("Нужно сегодня")
        assert result["date"] == date.today().strftime("%Y-%m-%d")

    def test_parse_date_tomorrow(self):
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        result = parse_delivery_text("Нужно завтра")
        assert result["date"] == tomorrow

    def test_parse_date_day_after_tomorrow(self):
        day_after = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        result = parse_delivery_text("Послезавтра")
        assert result["date"] == day_after

    def test_parse_time_hhmm(self):
        result = parse_delivery_text("В 15:30")
        assert result["time"] == "15:30"

    def test_parse_time_morning(self):
        result = parse_delivery_text("В 9 утра")
        assert result["time"] == "09:00"

    def test_parse_time_evening(self):
        result = parse_delivery_text("В 9 вечера")
        assert result["time"] == "21:00"

    def test_parse_capacity(self):
        result = parse_delivery_text("Могу взять 3 заказа")
        assert result["capacity"] == 3

    def test_parse_full_message_request(self):
        result = parse_delivery_text(
            "Привези продукты из Пятёрочки сегодня в 18:00"
        )
        assert result["store"] == "Пятёрочка"
        assert result["date"] == date.today().strftime("%Y-%m-%d")
        assert result["time"] == "18:00"

    def test_parse_full_message_offer(self):
        result = parse_delivery_text(
            "Еду в Магнит завтра в 10:00, могу взять 5 заказов"
        )
        assert result["store"] == "Магнит"
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result["date"] == tomorrow
        assert result["time"] == "10:00"
        assert result["capacity"] == 5


@pytest.mark.unit
class TestDeliveryModels:
    """Тесты моделей доставки."""

    @pytest.mark.asyncio
    async def test_create_delivery_request(self, db_session, user):
        """Создание заявки на доставку."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            request_text="Молоко, хлеб, яйца",
            desired_date="2024-03-15",
            desired_time_text="18:00",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == request.id)
        )
        saved = result.scalar()

        assert saved is not None
        assert saved.store == "Пятёрочка"
        assert saved.status == "active"

    @pytest.mark.asyncio
    async def test_create_delivery_offer(self, db_session, user):
        """Создание предложения доставки."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Магнит",
            comment="Еду за продуктами",
            trip_date="2024-03-15",
            trip_time="15:00",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryOffer).where(DeliveryOffer.id == offer.id)
        )
        saved = result.scalar()

        assert saved is not None
        assert saved.store == "Магнит"
        assert saved.capacity == 3
        assert saved.orders_taken == 0

    @pytest.mark.asyncio
    async def test_create_delivery_match(self, db_session, user):
        """Создание匹配 между заявкой и предложением."""
        # Создаём заявку
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            request_text="Продукты",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        # Создаём предложение
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=2,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        # Создаём匹配
        match = DeliveryMatch(
            request_id=request.id,
            offer_id=offer.id,
            status="pending"
        )
        db_session.add(match)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryMatch).where(DeliveryMatch.id == match.id)
        )
        saved = result.scalar()

        assert saved is not None
        assert saved.request_id == request.id
        assert saved.offer_id == offer.id
        assert saved.status == "pending"

    @pytest.mark.asyncio
    async def test_delivery_request_user_relationship(self, db_session, user):
        """Проверка связи DeliveryRequest -> User."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            request_text="Тест",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == request.id)
        )
        saved = result.scalar()

        await db_session.refresh(user)
        assert saved.user == user
        assert len(user.delivery_requests) == 1

    @pytest.mark.asyncio
    async def test_delivery_offer_user_relationship(self, db_session, user):
        """Проверка связи DeliveryOffer -> User."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Магнит",
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryOffer).where(DeliveryOffer.id == offer.id)
        )
        saved = result.scalar()

        await db_session.refresh(user)
        assert saved.user == user
        assert len(user.delivery_offers) == 1

    @pytest.mark.asyncio
    async def test_delivery_offer_capacity_update(self, db_session, user):
        """Обновление количества занятых мест."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            capacity=3,
            orders_taken=0,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        offer.orders_taken = 2
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryOffer).where(DeliveryOffer.id == offer.id)
        )
        saved = result.scalar()

        assert saved.orders_taken == 2
        assert saved.capacity - saved.orders_taken == 1

    @pytest.mark.asyncio
    async def test_delivery_match_relationships(self, db_session, user):
        """Проверка связей DeliveryMatch с Request и Offer."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            request_text="Тест",
            status="active"
        )
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            status="active"
        )
        db_session.add_all([request, offer])
        await db_session.commit()

        match = DeliveryMatch(
            request_id=request.id,
            offer_id=offer.id,
            status="confirmed"
        )
        db_session.add(match)
        await db_session.commit()

        result = await db_session.execute(
            select(DeliveryMatch).where(DeliveryMatch.id == match.id)
        )
        saved = result.scalar()

        await db_session.refresh(request)
        await db_session.refresh(offer)
        assert saved.request == request
        assert saved.offer == offer
        assert len(request.matches) == 1
        assert len(offer.matches) == 1
