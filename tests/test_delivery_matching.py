"""
Тесты для сервиса доставки (delivery_matching).
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from src.database.models import DeliveryRequest, DeliveryOffer, DeliveryMatch, User
from src.services.delivery_matching import (
    find_matching_offers,
    find_matching_requests,
    run_matching_for_request,
    run_matching_for_offer,
    create_match,
    confirm_match,
    reject_match,
    notify_user_about_match,
)


@pytest.mark.unit
class TestNotifyUserAboutMatch:
    """Тесты уведомлений."""

    @pytest.mark.asyncio
    async def test_notify_request_user(self):
        """Уведомление заказчика об исполнителе."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()

        await notify_user_about_match(
            bot=bot,
            user_id=123456,
            match_type="request",
            store="Пятёрочка",
            date="2024-03-15",
            time="18:00",
            counterparty_username="driver_user"
        )

        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args[0][1]
        assert "Найден исполнитель" in call_args
        assert "@driver_user" in call_args

    @pytest.mark.asyncio
    async def test_notify_offer_user(self):
        """Уведомление исполнителя о заказе."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()

        await notify_user_about_match(
            bot=bot,
            user_id=789012,
            match_type="offer",
            store="Пятёрочка",
            date="2024-03-15",
            time="15:00",
            counterparty_username="customer_user"
        )

        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args[0][1]
        assert "Найден заказ" in call_args
        assert "@customer_user" in call_args

    @pytest.mark.asyncio
    async def test_notify_send_message_error(self, caplog):
        """Обработка ошибки при отправке уведомления."""
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))

        await notify_user_about_match(
            bot=bot,
            user_id=123456,
            match_type="request",
            store="Пятёрочка",
            date="2024-03-15",
            time="18:00",
            counterparty_username="user"
        )

        assert "Не удалось отправить уведомление" in caplog.text


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestFindMatchingOffers:
    """Тесты поиска предложений для заявки."""

    @pytest.mark.asyncio
    async def test_find_matching_offers(self, db_session, user):
        """Поиск подходящих предложений."""
        # Создаём предложение
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            trip_time="15:00",
            capacity=3,
            orders_taken=0,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        # Создаём заявку
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            desired_time_text="18:00",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        # Ищем matching offers
        offers = await find_matching_offers(request)

        assert len(offers) == 1
        assert offers[0].id == offer.id

    @pytest.mark.asyncio
    async def test_find_matching_offers_different_store(self, db_session, user):
        """Разные магазины — нет совпадений."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Магнит",  # Другой магазин
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        offers = await find_matching_offers(request)
        assert len(offers) == 0

    @pytest.mark.asyncio
    async def test_find_matching_offers_different_date(self, db_session, user):
        """Разные даты — нет совпадений."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-16",  # Другая дата
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        offers = await find_matching_offers(request)
        assert len(offers) == 0

    @pytest.mark.asyncio
    async def test_find_matching_offers_no_capacity(self, db_session, user):
        """Нет свободных мест — нет совпадений."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=2,
            orders_taken=2,  # Все места заняты
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        offers = await find_matching_offers(request)
        assert len(offers) == 0

    @pytest.mark.asyncio
    async def test_find_matching_offers_inactive(self, db_session, user):
        """Неактивный статус — нет совпадений."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="cancelled"  # Неактивно
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        offers = await find_matching_offers(request)
        assert len(offers) == 0


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestFindMatchingRequests:
    """Тесты поиска заявок для предложения."""

    @pytest.mark.asyncio
    async def test_find_matching_requests(self, db_session, user):
        """Поиск подходящих заявок."""
        # Создаём две заявки
        request1 = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        request2 = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="matched"  # matched тоже подходит
        )
        db_session.add_all([request1, request2])
        await db_session.commit()

        # Создаём предложение
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        # Ищем matching requests
        requests = await find_matching_requests(offer)

        assert len(requests) == 2

    @pytest.mark.asyncio
    async def test_find_matching_requests_cancelled_status(self, db_session, user):
        """Статус cancelled не подходит."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="cancelled"
        )
        db_session.add(request)
        await db_session.commit()

        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        requests = await find_matching_requests(offer)
        assert len(requests) == 0


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestCreateMatch:
    """Тесты создания match."""

    @pytest.mark.asyncio
    async def test_create_match(self, db_session, user):
        """Создание match между заявкой и предложением."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add_all([request, offer])
        await db_session.commit()

        match = await create_match(request.id, offer.id)

        assert match is not None
        assert match.request_id == request.id
        assert match.offer_id == offer.id
        assert match.status == "pending"


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestRunMatchingForRequest:
    """Тесты запуска matching для заявки."""

    @pytest.mark.asyncio
    async def test_run_matching_creates_match(self, db_session, user):
        """Matching создаёт match при нахождении предложения."""
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        matches = await run_matching_for_request(request, bot=None)

        assert len(matches) == 1
        assert matches[0].request_id == request.id
        assert matches[0].offer_id == offer.id

    @pytest.mark.asyncio
    async def test_run_matching_with_bot(self, db_session, user):
        """Matching с bot отправляет уведомления."""
        bot = AsyncMock()
        bot.send_message = AsyncMock()

        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        matches = await run_matching_for_request(request, bot=bot)

        assert len(matches) == 1
        # Проверяем, что уведомления были отправлены (2 раза: заказчику и исполнителю)
        assert bot.send_message.call_count == 2


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestRunMatchingForOffer:
    """Тесты запуска matching для предложения."""

    @pytest.mark.asyncio
    async def test_run_matching_creates_match(self, db_session, user):
        """Matching создаёт match при нахождении заявки."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        db_session.add(request)
        await db_session.commit()

        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add(offer)
        await db_session.commit()

        matches = await run_matching_for_offer(offer, bot=None)

        assert len(matches) == 1
        assert matches[0].request_id == request.id
        assert matches[0].offer_id == offer.id


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestConfirmMatch:
    """Тесты подтверждения match."""

    @pytest.mark.asyncio
    async def test_confirm_match(self, db_session, user):
        """Подтверждение match."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            orders_taken=0,
            status="active"
        )
        db_session.add_all([request, offer])
        await db_session.commit()

        match = DeliveryMatch(
            request_id=request.id,
            offer_id=offer.id,
            status="pending"
        )
        db_session.add(match)
        await db_session.commit()

        result = await confirm_match(match.id)

        assert result is True
        
        # Проверяем обновления
        await db_session.refresh(match)
        await db_session.refresh(offer)
        await db_session.refresh(request)

        assert match.status == "confirmed"
        assert offer.orders_taken == 1
        assert request.status == "matched"

    @pytest.mark.asyncio
    async def test_confirm_match_fills_offer(self, db_session, user):
        """Подтверждение match заполняет offer (capacity достигнут)."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=1,  # Только 1 место
            orders_taken=0,
            status="active"
        )
        db_session.add_all([request, offer])
        await db_session.commit()

        match = DeliveryMatch(
            request_id=request.id,
            offer_id=offer.id,
            status="pending"
        )
        db_session.add(match)
        await db_session.commit()

        result = await confirm_match(match.id)

        assert result is True
        
        await db_session.refresh(offer)
        assert offer.status == "full"  # Все места заняты

    @pytest.mark.asyncio
    async def test_confirm_match_not_found(self, db_session):
        """Подтверждение несуществующего match."""
        result = await confirm_match(99999)
        assert result is False


@pytest.mark.integration
@pytest.mark.usefixtures("patch_delivery_session")
class TestRejectMatch:
    """Тесты отклонения match."""

    @pytest.mark.asyncio
    async def test_reject_match(self, db_session, user):
        """Отклонение match."""
        request = DeliveryRequest(
            user_id=user.id,
            store="Пятёрочка",
            desired_date="2024-03-15",
            status="active"
        )
        offer = DeliveryOffer(
            user_id=user.id,
            store="Пятёрочка",
            trip_date="2024-03-15",
            capacity=3,
            status="active"
        )
        db_session.add_all([request, offer])
        await db_session.commit()

        match = DeliveryMatch(
            request_id=request.id,
            offer_id=offer.id,
            status="pending"
        )
        db_session.add(match)
        await db_session.commit()

        result = await reject_match(match.id)

        assert result is True
        
        await db_session.refresh(match)
        assert match.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_match_not_found(self, db_session):
        """Отклонение несуществующего match."""
        result = await reject_match(99999)
        assert result is False
