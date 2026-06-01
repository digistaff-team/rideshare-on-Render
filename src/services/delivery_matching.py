"""
Сервис для поиска совпадений между заявками и предложениями доставки.
"""
import logging
from datetime import datetime
from sqlalchemy import select
from aiogram import Bot
from src.database.session import async_session
from src.database.models import DeliveryRequest, DeliveryOffer, DeliveryMatch, User

logger = logging.getLogger(__name__)


async def notify_user_about_match(
    bot: Bot,
    user_id: int,
    match_type: str,
    store: str,
    date: str,
    time: str,
    counterparty_username: str
):
    """
    Отправить уведомление пользователю о найденном match.
    
    Args:
        bot: Telegram bot instance
        user_id: Telegram ID пользователя
        match_type: 'request' или 'offer'
        store: Название магазина
        date: Дата доставки
        time: Время доставки
        counterparty_username: Username второй стороны
    """
    if match_type == "request":
        text = (
            f"🔔 <b>Найден исполнитель!</b>\n\n"
            f"🏪 Магазин: {store}\n"
            f"📅 Дата: {date}\n"
            f"🕐 Время: {time}\n\n"
            f"👤 Исполнитель: @{counterparty_username}\n\n"
            f"Нажмите /my_deliveries чтобы управлять заказом."
        )
    else:  # offer
        text = (
            f"🔔 <b>Найден заказ!</b>\n\n"
            f"🏪 Магазин: {store}\n"
            f"📅 Дата: {date}\n"
            f"🕐 Время: {time}\n\n"
            f"👤 Заказчик: @{counterparty_username}\n\n"
            f"Нажмите /my_deliveries чтобы управлять заказом."
        )
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        logger.info(f"📩 Уведомление отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить уведомление пользователю {user_id}: {e}")


async def find_matching_offers(request: DeliveryRequest) -> list[DeliveryOffer]:
    """
    Найти подходящие предложения для заявки.
    
    Критерии matching:
    - Тот же магазин
    - Та же дата (или обе не указаны)
    - Есть свободные места (capacity > orders_taken)
    - Статус active
    """
    async with async_session() as session:
        # Базовый запрос
        query = select(DeliveryOffer).where(
            DeliveryOffer.store == request.store,
            DeliveryOffer.status == "active",
            DeliveryOffer.capacity > DeliveryOffer.orders_taken
        )
        
        # Если дата указана в заявке, ищем точное совпадение
        if request.desired_date:
            query = query.where(DeliveryOffer.trip_date == request.desired_date)
        # Если дата не указана,匹配 только предложения без даты
        else:
            query = query.where(DeliveryOffer.trip_date.is_(None))
        
        result = await session.execute(query)
        return list(result.scalars().all())


async def find_matching_requests(offer: DeliveryOffer) -> list[DeliveryRequest]:
    """
    Найти подходящие заявки для предложения.
    
    Критерии matching:
    - Тот же магазин
    - Та же дата (или обе не указаны)
    - Статус active или matched
    """
    async with async_session() as session:
        # Базовый запрос
        query = select(DeliveryRequest).where(
            DeliveryRequest.store == offer.store,
            DeliveryRequest.status.in_(["active", "matched"]),
        )
        
        # Если дата указана в предложении, ищем точное совпадение
        if offer.trip_date:
            query = query.where(DeliveryRequest.desired_date == offer.trip_date)
        # Если дата не указана,匹配 только заявки без даты
        else:
            query = query.where(DeliveryRequest.desired_date.is_(None))
        
        result = await session.execute(query)
        return list(result.scalars().all())


async def create_match(
    request_id: int,
    offer_id: int,
    status: str = "pending"
) -> DeliveryMatch:
    """
    Создать связь между заявкой и предложением.
    """
    async with async_session() as session:
        match = DeliveryMatch(
            request_id=request_id,
            offer_id=offer_id,
            status=status
        )
        session.add(match)
        await session.commit()
        await session.refresh(match)
        return match


async def run_matching_for_request(
    request: DeliveryRequest,
    bot: Bot = None
) -> list[DeliveryMatch]:
    """
    Запустить поиск совпадений для заявки.
    Создаёт matches для всех подходящих предложений и отправляет уведомления.
    """
    offers = await find_matching_offers(request)
    matches = []

    for offer in offers:
        # Проверяем, нет ли уже существующего match
        async with async_session() as session:
            existing = await session.execute(
                select(DeliveryMatch).where(
                    DeliveryMatch.request_id == request.id,
                    DeliveryMatch.offer_id == offer.id
                )
            )
            if existing.scalar():
                continue  # Уже есть match

        # Создаём новый match
        match = await create_match(request.id, offer.id)
        matches.append(match)

        logger.info(
            f"🛍 Match найден: request={request.id}, offer={offer.id}, "
            f"store={request.store}, date={request.desired_date}"
        )

        # Отправляем уведомления
        if bot:
            async with async_session() as session:
                offer_user_result = await session.execute(
                    select(User).where(User.id == offer.user_id)
                )
                offer_user = offer_user_result.scalar()

                request_user_result = await session.execute(
                    select(User).where(User.id == request.user_id)
                )
                request_user = request_user_result.scalar()

            await notify_user_about_match(
                bot=bot,
                user_id=request_user.telegram_id,
                match_type="request",
                store=request.store,
                date=request.desired_date or "Не указана",
                time=request.desired_time_text or "Не указано",
                counterparty_username=offer_user.username or "unknown"
            )

            await notify_user_about_match(
                bot=bot,
                user_id=offer_user.telegram_id,
                match_type="offer",
                store=offer.store,
                date=offer.trip_date or "Не указана",
                time=offer.trip_time or "Не указано",
                counterparty_username=request_user.username or "unknown"
            )

    return matches


async def run_matching_for_offer(
    offer: DeliveryOffer,
    bot: Bot = None
) -> list[DeliveryMatch]:
    """
    Запустить поиск совпадений для предложения.
    Создаёт matches для всех подходящих заявок и отправляет уведомления.
    """
    requests = await find_matching_requests(offer)
    matches = []

    for request in requests:
        # Проверяем, нет ли уже существующего match
        async with async_session() as session:
            existing = await session.execute(
                select(DeliveryMatch).where(
                    DeliveryMatch.request_id == request.id,
                    DeliveryMatch.offer_id == offer.id
                )
            )
            if existing.scalar():
                continue  # Уже есть match

        # Создаём новый match
        match = await create_match(request.id, offer.id)
        matches.append(match)

        logger.info(
            f"🛒 Match найден: offer={offer.id}, request={request.id}, "
            f"store={offer.store}, date={offer.trip_date}"
        )

        # Отправляем уведомления
        if bot:
            async with async_session() as session:
                offer_user_result = await session.execute(
                    select(User).where(User.id == offer.user_id)
                )
                offer_user = offer_user_result.scalar()

                request_user_result = await session.execute(
                    select(User).where(User.id == request.user_id)
                )
                request_user = request_user_result.scalar()

            await notify_user_about_match(
                bot=bot,
                user_id=offer_user.telegram_id,
                match_type="offer",
                store=offer.store,
                date=offer.trip_date or "Не указана",
                time=offer.trip_time or "Не указано",
                counterparty_username=request_user.username or "unknown"
            )

            await notify_user_about_match(
                bot=bot,
                user_id=request_user.telegram_id,
                match_type="request",
                store=request.store,
                date=request.desired_date or "Не указана",
                time=request.desired_time_text or "Не указано",
                counterparty_username=offer_user.username or "unknown"
            )

    return matches


async def confirm_match(match_id: int) -> bool:
    """
    Подтвердить match.
    Обновляет статусы match, request и offer.
    """
    async with async_session() as session:
        match = await session.get(DeliveryMatch, match_id)
        if not match:
            return False
        
        match.status = "confirmed"
        match.confirmed_at = datetime.utcnow()
        
        # Увеличиваем orders_taken у offer
        offer = await session.get(DeliveryOffer, match.offer_id)
        if offer:
            offer.orders_taken += 1
            if offer.orders_taken >= offer.capacity:
                offer.status = "full"
        
        # Обновляем статус request
        request = await session.get(DeliveryRequest, match.request_id)
        if request and request.status == "active":
            request.status = "matched"
        
        await session.commit()
        return True


async def reject_match(match_id: int) -> bool:
    """
    Отклонить match.
    """
    async with async_session() as session:
        match = await session.get(DeliveryMatch, match_id)
        if not match:
            return False
        
        match.status = "rejected"
        await session.commit()
        return True


async def complete_match(match_id: int) -> bool:
    """
    Завершить match (доставка выполнена).
    """
    async with async_session() as session:
        match = await session.get(DeliveryMatch, match_id)
        if not match:
            return False
        
        match.status = "completed"
        
        # Проверяем, все ли matches для request завершены
        request = await session.get(DeliveryRequest, match.request_id)
        if request:
            all_completed = True
            for m in request.matches:
                if m.status != "completed":
                    all_completed = False
                    break
            if all_completed:
                request.status = "completed"

        await session.commit()
        return True
