import asyncio
import logging
import html
from datetime import datetime, timedelta, date
from sqlalchemy import delete, select, update
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database.session import async_session
from src.database.models import User, Ride, Booking
from src.services.nlu import NLUProcessor
from src.services.simple_parser import SimpleParser
from src.config import (
    ROUTE_ORDER,
    CLEANUP_INTERVAL_SECONDS,
    CLEANUP_DAYS_BACK,
    MAX_RIDES_TO_FETCH,
    MAX_RIDES_TO_DISPLAY,
    MAX_CITY_NAME_LENGTH,
    MIN_SEATS,
    MAX_SEATS,
)
from src.utils import extract_seats, validate_city_name, validate_seats

logger = logging.getLogger(__name__)
router = Router()
nlu = NLUProcessor()
fallback_parser = SimpleParser()


class RideForm(StatesGroup):
    chatting_with_ai = State()


def main_kb() -> ReplyKeyboardMarkup:
    """Возвращает основную клавиатуру бота."""
    kb = [
        [KeyboardButton(text="🙋 Подвези"), KeyboardButton(text="🚗 Подвезу")],
        [KeyboardButton(text="🔍 Найти поездку"),
         KeyboardButton(text="📋 Мои поездки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_city_index(city_name: str) -> int:
    """
    Возвращает индекс города в маршруте.
    
    Args:
        city_name: Название города
        
    Returns:
        Индекс города или -1 если не найден
    """
    city_name = city_name.lower()
    for i, stop in enumerate(ROUTE_ORDER):
        if stop.lower() in city_name:
            return i
    return -1


def is_route_compatible(driver_origin, driver_dest, pass_origin, pass_dest):
    d_start = get_city_index(driver_origin)
    d_end = get_city_index(driver_dest)
    p_start = get_city_index(pass_origin)
    p_end = get_city_index(pass_dest)

    if -1 in [d_start, d_end, p_start, p_end]:
        return (pass_origin.lower() in driver_origin.lower()) and \
               (pass_dest.lower() in driver_dest.lower())

    driver_direction = d_end > d_start
    pass_direction = p_end > p_start

    if driver_direction != pass_direction:
        return False

    if driver_direction:
        return p_start >= d_start and p_end <= d_end
    else:
        return p_start <= d_start and p_end >= d_end


def parse_date(date_str: str):
    """Парсит строку даты в datetime.date объект"""
    formats = [
        "%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(d) -> str:
    """
    Вспомогательная функция для форматирования даты в DD.MM.YYYY.
    
    Args:
        d: Дата (date объект или строка)
        
    Returns:
        Отформатированная строка даты
    """
    if not d:
        return ""

    # Если это date объект
    if isinstance(d, date):
        return d.strftime("%d.%m.%Y")

    # Если строка - парсим
    if isinstance(d, str):
        parsed = parse_date(d)
        if parsed:
            return parsed.strftime("%d.%m.%Y")
        return d

    return str(d)


# --- ФОНОВЫЕ ЗАДАЧИ ---
async def auto_clean_old_rides():
    """
    Фоновая задача для удаления старых записей.
    Работает до отмены через asyncio.CancelledError.
    """
    while True:
        try:
            async with async_session() as session:
                cutoff = datetime.now().date() - timedelta(days=CLEANUP_DAYS_BACK)

                result = await session.execute(
                    delete(Ride).where(Ride.date < cutoff)
                )
                await session.commit()
                deleted = result.rowcount
                if deleted > 0:
                    logger.info(f"🧹 Удалено {deleted} старых поездок")
                else:
                    logger.debug("Фоновая очистка: нет старых поездок")
        except asyncio.CancelledError:
            logger.info("Фоновая задача очистки остановлена")
            raise
        except Exception as e:
            if "no such table" not in str(e):
                logger.error(f"Ошибка фоновой очистки: {e}", exc_info=True)

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


# --- ПРИВЕТСТВИЕ ---
@router.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == m.from_user.id))
        if not result.scalar():
            session.add(User(telegram_id=m.from_user.id,
                        username=m.from_user.username))
            await session.commit()

    welcome_text = (
        "Привет! Я помогу найти попутчиков.\n\n"
        "Используйте кнопки внизу экрана.\n\n"
        "Чтобы создать запись о поездке:\n"
        "Вы пассажир - нажмите 🙋 Подвези\n"
        "Вы водитель - нажмите 🚗 Подвезу\n\n"
        "Посмотреть все активные поездки:\n"
        "Нажмите 🔍 Найти поездку\n\n"
        "Проверить/удалить свои поездки:\n"
        "Нажмите кнопку 📋 Мои поездки"
    )
    await m.answer(welcome_text, reply_markup=main_kb(), parse_mode="HTML")


# --- ПОИСК ПОПУТЧИКОВ ---
@router.message(Command("all_rides"))
@router.message(F.text.in_({"🔍 Найти поездку"}))
async def find_rides(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as s:
        now = datetime.now()
        today = now.date()
        current_time = now.time()

        # Ищем только водителей с свободными местами
        rides_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.role == 'driver',
                Ride.seats > 0,
                Ride.date >= today
            ).order_by(Ride.date.asc(), Ride.created_at.desc()).limit(MAX_RIDES_TO_FETCH)
        )

        all_rides = rides_stmt.all()
        rides = []

        for r, u in all_rides:
            # r.date уже datetime.date объект
            if r.date > today:
                rides.append((r, u))
            elif r.date == today:
                if not r.start_time or r.start_time == "По договоренности":
                    rides.append((r, u))
                else:
                    try:
                        ride_time = datetime.strptime(
                            r.start_time, "%H:%M").time()
                        if ride_time > current_time:
                            rides.append((r, u))
                    except ValueError:
                        rides.append((r, u))

            if len(rides) >= MAX_RIDES_TO_DISPLAY:
                break

        if not rides:
            return await m.answer("Нет актуальных объявлений водителей.")

        for r, u in rides:
            role_icon = '🚗 Водитель'
            seats_text = f"Мест: {r.seats}"
            username = html.escape(u.username or 'скрыт')
            txt = (
                f"{role_icon}\n"
                f"📍 {html.escape(r.origin)} -> {html.escape(r.destination)}\n"
                f"📅 {fmt_date(r.date)} | {r.start_time}\n"
                f"{seats_text}\n"
                f"👤 @{username}"
            )
            await m.answer(txt, parse_mode="HTML")


# --- КНОПКИ МОИ ПОЕЗДКИ ---
@router.message(Command("my_rides"))
@router.message(F.text == "📋 Мои поездки")
async def list_rides(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as s:
        user_stmt = await s.execute(select(User.id).where(User.telegram_id == m.from_user.id))
        u_id_res = user_stmt.scalar()

        if not u_id_res:
            return await m.answer("Сначала нажмите /start")

        rides_stmt = await s.execute(
            select(Ride).where(Ride.user_id ==
                               u_id_res).order_by(Ride.date.desc())
        )
        rides = rides_stmt.scalars().all()

        if not rides:
            return await m.answer("У вас пока нет активных поездок.")

        for r in rides:
            role_text = "🚗 Я - Водитель" if r.role == 'driver' else "🙋 Я - Пассажир"
            txt = (
                f"<b>{role_text}</b>\n"
                f"📍<b>{html.escape(r.origin)}</b> ➡️ <b>{html.escape(r.destination)}</b>\n"
                f"📅 {fmt_date(r.date)} в {r.start_time}\n"
                f"💺 Мест: <b>{r.seats}</b>"
            )
            kb = InlineKeyboardBuilder().button(
                text="❌ Удалить", callback_data=f"del_{r.id}").as_markup()
            await m.answer(txt, reply_markup=kb, parse_mode="HTML")


# --- ВЫБОР РОЛИ ---
@router.message(F.text.in_(["🙋 Подвези", "🚗 Подвезу"]))
async def ask_route(m: types.Message, state: FSMContext):
    await state.clear()
    role = "passenger" if "🙋" in m.text else "driver"
    await state.update_data(role=role)
    await state.set_state(RideForm.chatting_with_ai)

    text = (
        "Напишите о желаемой поездке, например: 'Из Краснодара в Сказочный сегодня в 18:00, одно место'."
        if role == "passenger" else
        "Напишите маршрут, дату и время вашей поездки, например: 'Из Сказочного края в Краснодар завтра в 9 утра, есть два места'."
    )
    await m.answer(text, parse_mode="HTML")


# --- ГЛАВНЫЙ ОБРАБОТЧИК ДИАЛОГА (AI) ---
@router.message(
    RideForm.chatting_with_ai,
    F.text & ~F.text.startswith(
        "/") & ~F.text.in_({"📋 Мои поездки", "🔍 Найти поездку", "🙋 Подвези", "🚗 Подвезу"})
)
async def handle_ai_conversation(m: types.Message, state: FSMContext):
    """
    Главный обработчик диалога с пользователем.
    Использует NLU (Pro-Talk) с fallback на простой парсер.
    """

    # 1. Получаем роль пользователя
    data = await state.get_data()
    role = data.get("role")

    # 2. Если роль не задана, пробуем найти из истории
    if not role:
        async with async_session() as s:
            user_res = await s.execute(select(User.id).where(User.telegram_id == m.from_user.id))
            u_id = user_res.scalar()

            if u_id:
                last_ride_res = await s.execute(
                    select(Ride.role)
                    .where(Ride.user_id == u_id)
                    .order_by(Ride.created_at.desc())
                    .limit(1)
                )
                last_role = last_ride_res.scalar()
                if last_role:
                    role = last_role

        if not role:
            role = "passenger"

        await state.update_data(role=role)

    logger.info(
        f"🔍 Обработка сообщения: user={m.from_user.id}, role={role}, text='{m.text}'")

    # 3. Пробуем NLU (Pro-Talk)
    res = await nlu.parse_intent(m.text, m.from_user.id, role=role)

    logger.info(f"📥 NLU вернул: {res}")

    # 4. Если NLU не вернул полные данные - используем fallback парсер
    has_complete_data = (
        res and
        res.get("origin") and
        res.get("destination") and
        res.get("date")
    )

    if not has_complete_data:
        logger.info("⚠️ NLU не вернул полные данные, пробуем fallback parser")
        fallback_res = fallback_parser.parse(m.text, role=role)

        if fallback_res and fallback_res.get("origin") and fallback_res.get("destination"):
            logger.info("✅ Fallback parser успешно извлёк данные")
            res = fallback_res
            has_complete_data = True

    # 5. Если есть полные данные - сохраняем поездку
    if has_complete_data:
        await process_ride_data(m, res, state)
        return

    # 6. Если данных нет, но есть текстовый ответ от AI - показываем его
    ai_reply = res.get("raw_text", "") if res else ""

    clean_reply = re.sub(r'```.*?```', '', ai_reply, flags=re.DOTALL).strip()
    clean_reply = clean_reply.replace('```', '').strip()

    if clean_reply.strip().startswith("{") and clean_reply.strip().endswith("}"):
        clean_reply = ""

    if clean_reply:
        logger.info(f"💬 Показываем ответ AI: {clean_reply[:100]}...")
        await m.answer(clean_reply)
    else:
        logger.warning("❌ Не удалось извлечь данные о поездке")
        await m.answer(
            "🤷🏻 Не могу понять детали маршрута. Попробуйте еще раз, указав Откуда, Куда и Дату.\n\n"
            "Наример:\n"
            "'Из Здравого в Краснодар завтра в 10 утра, есть 2 места'"
        )


async def process_ride_data(m: types.Message, res: dict, state: FSMContext):
    """Сохранение данных поездки в БД"""

    data = await state.get_data()
    role = data.get('role', 'passenger')

    async with async_session() as s:
        user_stmt = await s.execute(select(User).where(User.telegram_id == m.from_user.id))
        user = user_stmt.scalar()

        if not user:
            logger.error(f"❌ Пользователь {m.from_user.id} не найден в БД")
            return

        # Парсим дату
        if isinstance(res['date'], str):
            parsed_date = parse_date(res['date'])
        else:
            parsed_date = res['date']

        if not parsed_date:
            parsed_date = datetime.now().date() + timedelta(days=1)
            logger.warning(f"⚠️ Не удалось распарсить дату '{res['date']}', используем завтра")

        # Количество мест
        seats = res.get("seats")
        if seats is None or seats == "null":
            seats = extract_seats(m.text)
        else:
            seats = int(seats)
        
        # Валидируем количество мест
        seats = validate_seats(seats, MIN_SEATS, MAX_SEATS)
        
        # Валидируем названия городов
        if not validate_city_name(res['origin'], MAX_CITY_NAME_LENGTH):
            logger.warning(f"⚠️ Некорректное название origin: {res['origin'][:50]}")
        if not validate_city_name(res['destination'], MAX_CITY_NAME_LENGTH):
            logger.warning(f"⚠️ Некорректное название destination: {res['destination'][:50]}")

        # Время (пробуем оба варианта ключа для совместимости)
        start_time = res.get("start_time") or res.get("starttime")
        if start_time is None or start_time == "" or start_time == "None" or start_time == "null":
            start_time = None

        logger.info(
            f"💾 Сохранение поездки: {res['origin']} → {res['destination']}, "
            f"дата={parsed_date}, время={start_time or 'не указано'}, мест={seats}, роль={role}"
        )

        # Создаем объект Ride
        new_ride = Ride(
            user_id=user.id,
            origin=res['origin'][:MAX_CITY_NAME_LENGTH],
            destination=res['destination'][:MAX_CITY_NAME_LENGTH],
            date=parsed_date,
            start_time=start_time,
            seats=seats,
            role=role
        )
        
        s.add(new_ride)
        await s.commit()
        await s.refresh(new_ride)

        logger.info(
            f"✅ Поездка сохранена: ID={new_ride.id}, user={m.from_user.id}, "
            f"role={role}, origin={res['origin']}, destination={res['destination']}, "
            f"date={parsed_date}, seats={seats}"
        )

        await m.answer("✅ Поездка сохранена!", reply_markup=main_kb())

        if role == 'driver':
            await match_passengers(m, new_ride, res, user)
        elif role == 'passenger':
            await notify_drivers_about_passenger(m, new_ride, user)

        await state.clear()


async def match_passengers(m: types.Message, new_ride: Ride, res: dict, user: User):
    """Поиск и уведомление пассажиров для водителя"""

    target_date = parse_date(res['date'])
    if not target_date:
        return

    async with async_session() as s:
        matches_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.date == target_date,
                Ride.role == 'passenger',
                Ride.user_id != user.id
            )
        )
        matches = matches_stmt.all()

        for r_obj, match_user in matches:
            if is_route_compatible(new_ride.origin, new_ride.destination, r_obj.origin, r_obj.destination):
                if new_ride.seats > 0:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="✅ Взять пассажира",
                              callback_data=f"take_{r_obj.id}_{new_ride.id}")

                    username = html.escape(match_user.username or 'скрыт')
                    seats_needed = r_obj.seats

                    match_msg = (
                        f"🔔 Найден попутчик!\n"
                        f"📍 {html.escape(r_obj.origin)} ➡️ {html.escape(r_obj.destination)}\n"
                        f"📅 {fmt_date(r_obj.date)}\n"
                        f"⏱️ {r_obj.start_time}\n"
                        f"💺 Нужно мест: {seats_needed}\n"
                        f"🙋🏼 @{username}"
                    )

                    try:
                        await m.bot.send_message(m.from_user.id, match_msg, reply_markup=kb.as_markup(), parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка уведомления водителю: {e}")


async def notify_drivers_about_passenger(m: types.Message, passenger_ride: Ride, passenger_user: User):
    """Уведомление водителей о новом пассажире"""

    target_date = passenger_ride.date  # Уже date объект

    async with async_session() as s:
        drivers_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.date == target_date,
                Ride.role == 'driver',
                Ride.seats > 0,
                Ride.user_id != passenger_user.id
            )
        )
        drivers = drivers_stmt.all()

        for driver_ride, driver_user in drivers:
            if not is_route_compatible(
                driver_ride.origin, driver_ride.destination,
                passenger_ride.origin, passenger_ride.destination
            ):
                continue

            kb = InlineKeyboardBuilder()
            kb.button(
                text="✅ Взять пассажира",
                callback_data=f"take_{passenger_ride.id}_{driver_ride.id}"
            )

            seats_needed = passenger_ride.seats

            msg = (
                f"🔔 Для вас найден пассажир!\n"
                f"📍 {html.escape(passenger_ride.origin)} ➡️ {html.escape(passenger_ride.destination)}\n"
                f"📅 {fmt_date(passenger_ride.date)}\n" 
                f"🕒 {passenger_ride.start_time}\n"
                f"💺 Нужно мест: {seats_needed}\n"
                f"👤 Контакт: @{html.escape(passenger_user.username or 'скрыт')}"
            )

            try:
                await m.bot.send_message(
                    driver_user.telegram_id,
                    msg,
                    reply_markup=kb.as_markup(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления водителю: {e}")


# --- CALLBACKS ---
@router.callback_query(F.data.startswith("take_"))
async def take_passenger(cb: types.CallbackQuery):
    try:
        _, p_ride_id, d_ride_id = cb.data.split("_")
        p_ride_id = int(p_ride_id)
        d_ride_id = int(d_ride_id)

        async with async_session() as s:
            driver_ride = await s.get(Ride, d_ride_id)

            if not driver_ride or driver_ride.seats <= 0:
                return await cb.answer("Места закончились🤷🏻♂️", show_alert=True)

            new_booking = Booking(
                driver_ride_id=d_ride_id,
                passenger_ride_id=p_ride_id,
                status='pending'
            )

            s.add(new_booking)
            await s.commit()
            await s.refresh(new_booking)

            p_user_stmt = await s.execute(
                select(User.telegram_id, User.username).join(
                    Ride).where(Ride.id == p_ride_id)
            )
            res = p_user_stmt.first()

            if not res:
                return await cb.answer("Пассажир не найден (удален)", show_alert=True)

            p_tid, p_username = res

            kb = InlineKeyboardBuilder()
            kb.button(text="🤝 Еду с вами",
                      callback_data=f"confirm_{new_booking.id}")

            driver_username = html.escape(cb.from_user.username or 'скрыт')

            match_msg = (
                f"🔔 Водитель готов вас подвезти!\n"
                f"📍 {html.escape(driver_ride.origin)} ➡️ {html.escape(driver_ride.destination)}\n"
                f"📅 Дата: {fmt_date(driver_ride.date)}\n"
                f"🕒 Время: {driver_ride.start_time}\n"
                f"👤 Контакт: @{driver_username}"
            )

            try:
                await cb.bot.send_message(p_tid, match_msg, reply_markup=kb.as_markup(), parse_mode="HTML")
                await cb.answer("Пассажир уведомлен!")
                await cb.message.edit_text(cb.message.text + "\n\n📩 Уведомление отправлено пассажиру")
            except Exception as e:
                logger.error(f"Ошибка уведомления пассажиру: {e}")
                await cb.answer("Ошибка отправки уведомления")

    except Exception as e:
        logger.error(f"Error in take_passenger: {e}")
        await cb.answer("Произошла ошибка")


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_booking(cb: types.CallbackQuery):
    try:
        _, booking_id = cb.data.split("_")
        booking_id = int(booking_id)

        async with async_session() as s:
            booking = await s.get(Booking, booking_id)

            if not booking or booking.status != 'pending':
                return await cb.answer("Бронирование уже обработано!", show_alert=True)

            driver_ride = await s.get(Ride, booking.driver_ride_id)

            if not driver_ride:
                return await cb.answer("Поездка водителя не найдена", show_alert=True)

            passenger_ride = await s.get(Ride, booking.passenger_ride_id)
            
            if not passenger_ride:
                booking.status = 'rejected'
                await s.commit()
                return await cb.answer("Поездка пассажира не найдена", show_alert=True)
            
            seats_needed = passenger_ride.seats if passenger_ride.seats else 1

            if driver_ride.seats < seats_needed:
                booking.status = 'rejected'
                await s.commit()
                await cb.answer("К сожалению, мест недостаточно!", show_alert=True)
                await cb.message.edit_text(cb.message.text + "\n\n❌ Недостаточно мест")
                return

            if driver_ride.start_time != "По договоренности":
                passenger_ride.start_time = driver_ride.start_time

            booking.status = 'confirmed'
            driver_ride.seats -= seats_needed
            await s.commit()

            d_user_stmt = await s.execute(
                select(User.telegram_id).join(Ride).where(
                    Ride.id == booking.driver_ride_id)
            )
            d_tid = d_user_stmt.scalar()

            if d_tid:
                await cb.bot.send_message(
                    d_tid,
                    f"🎉 Пассажир подтвердил поездку! Занято мест: {seats_needed}. Приятного пути!"
                )

            await cb.answer("Поездка подтверждена!")
            await cb.message.edit_text(cb.message.text + "\n\n✅ Подтверждено")

    except Exception as e:
        logger.error(f"Error in confirm_booking: {e}")
        await cb.answer("Ошибка подтверждения")


@router.callback_query(F.data.startswith("del_"))
async def delete_ride(cb: types.CallbackQuery):
    try:
        r_id = int(cb.data.split("_")[1])

        async with async_session() as s:
            ride = await s.get(Ride, r_id)

            if ride:
                await s.execute(delete(Booking).where(Booking.driver_ride_id == r_id))
                await s.execute(delete(Booking).where(Booking.passenger_ride_id == r_id))
                await s.delete(ride)
                await s.commit()
                logger.info(f"🗑️ Поездка удалена: ID={r_id}, user={cb.from_user.id}")
                await cb.answer("Поездка удалена")
                await cb.message.delete()
            else:
                logger.warning(f"⚠️ Попытка удалить несуществующую поездку: ID={r_id}, user={cb.from_user.id}")
                await cb.answer("Поездка уже удалена", show_alert=True)
                try:
                    await cb.message.delete()
                except:
                    pass

    except Exception as e:
        logger.error(f"Error in delete_ride: {e}")
        await cb.answer("Ошибка при удалении")
