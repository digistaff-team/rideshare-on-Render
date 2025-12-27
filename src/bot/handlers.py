import asyncio
import logging
import json
import re
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

logger = logging.getLogger(__name__)
router = Router()
nlu = NLUProcessor()

class RideForm(StatesGroup):
    chatting_with_ai = State()

def main_kb():
    kb = [
        [KeyboardButton(text="🙋 Подвези"), KeyboardButton(text="🚗 Подвезу")],
        [KeyboardButton(text="🔍 Найти поездку"), KeyboardButton(text="📋 Мои поездки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- НАСТРОЙКА МАРШРУТОВ ---

ROUTE_ORDER = [
    "Сказочный край",
    "Живой дом",
    "Здравое",
    "Григорьевская",
    "Смоленская",
    "Афипский",
    "Энем",
    "Яблоновский",
    "Краснодар"
]

def get_city_index(city_name: str) -> int:
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
    """Вспомогательная функция для форматирования даты в DD.MM.YYYY"""
    if not d:
        return ""
    if isinstance(d, str):
        parsed = parse_date(d)
        if parsed:
            return parsed.strftime("%d.%m.%Y")
        return d
    return d.strftime("%d.%m.%Y")


# --- ФОНОВЫЕ ЗАДАЧИ ---
async def auto_clean_old_rides():
    while True:
        try:
            async with async_session() as session:
                limit = datetime.utcnow() - timedelta(days=2)
                await session.execute(delete(Ride).where(Ride.created_at < limit))
                await session.execute(delete(Booking).where(Booking.created_at < limit))
                await session.commit()
                logger.info("Фоновая очистка базы завершена успешно.")
            await asyncio.sleep(43200)
        except Exception as e:
            logger.error(f"Ошибка фоновой очистки: {e}")
            await asyncio.sleep(3600)

# --- ПРИВЕТСТВИЕ ---
@router.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == m.from_user.id))
        if not result.scalar():
            session.add(User(telegram_id=m.from_user.id, username=m.from_user.username))
            await session.commit()
    
    welcome_text = (
        "Привет! Я помогу найти попутчиков.\n\n"
        "Используйте кнопки внизу экрана.\n\n"
        "<b>Чтобы создать запись о поездке:</b>\n"
        "Вы пассажир - нажмите 🙋 Подвези\n"
        "Вы водитель - нажмите 🚗 Подвезу\n\n"
        "<b>Посмотреть все активные поездки:</b>\n"
        "Нажмите 🔍 Найти поездку\n\n"
        "<b>Проверить/удалить свои поездки:</b>\n"
        "Нажмите кнопку 📋 Мои поездки"
    )
    await m.answer(welcome_text, reply_markup=main_kb(), parse_mode="HTML")

# --- ПОИСК ПОПУТЧИКОВ ---
@router.message(Command("all_rides"))
@router.message(F.text.in_({"🔍 Найти поездку"}))
async def find_rides(m: types.Message, state: FSMContext):
    await state.clear()
    
    async with async_session() as s:
        # Ищем только водителей, у которых есть свободные места
        rides_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.created_at > datetime.utcnow() - timedelta(days=2),
                Ride.role == 'driver',
                Ride.seats > 0
            ).order_by(Ride.created_at.desc()).limit(10)
        )
        rides = rides_stmt.all()
        
        if not rides:
            return await m.answer("Нет актуальных объявлений водителей.")
        
        for r, u in rides:
            role_icon = '🚗 Водитель'
            seats_text = f"Мест: {r.seats}"
            
            username = html.escape(u.username or 'скрыт')
            
            txt = (
                f"<b>{role_icon}</b>\n"
                f"📍 {html.escape(r.origin)} -> {html.escape(r.destination)}\n"
                f"📅 {fmt_date(r.ride_date)} | {r.start_time}\n"
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

        rides_stmt = await s.execute(select(Ride).where(Ride.user_id == u_id_res).order_by(Ride.ride_date.desc()))
        rides = rides_stmt.scalars().all()
        
        if not rides:
            return await m.answer("У вас пока нет активных поездок.")
        
        for r in rides:
            role_text = "🚗 Я - Водитель" if r.role == 'driver' else "🙋 Я - Пассажир"
            txt = (
                f"<b>{role_text}</b>\n"
                f"📍 <b>{html.escape(r.origin)}</b> -> <b>{html.escape(r.destination)}</b>\n"
                f"📅 {fmt_date(r.ride_date)} | {r.start_time}"
            )
            kb = InlineKeyboardBuilder().button(text="❌ Удалить", callback_data=f"del_{r.id}").as_markup()
            await m.answer(txt, reply_markup=kb, parse_mode="HTML")

# --- ВЫБОР РОЛИ ---
@router.message(F.text.in_(["🙋 Подвези", "🚗 Подвезу"]))
async def ask_route(m: types.Message, state: FSMContext):
    await state.clear()
    
    role = "passenger" if "🙋" in m.text else "driver"
    await state.update_data(role=role)
    await state.set_state(RideForm.chatting_with_ai)
    
    text = (
        "Напишите маршрут поездки, например: <i>'Из Здравого в Краснодар завтра в 9 утра'</i>."
        if role == "passenger" else
        "Напишите детали: <i>'Еду из Краснодара в Здравое 27.12 в 18:00, есть 3 места'</i>."
    )
    await m.answer(text, parse_mode="HTML")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ДИАЛОГА (AI) ---
@router.message(
    RideForm.chatting_with_ai, 
    F.text & ~F.text.startswith("/") & ~F.text.in_({"📋 Мои поездки", "🔍 Найти поездку", "🙋 Подвези", "🚗 Подвезу"})
)
async def handle_ai_conversation(m: types.Message, state: FSMContext):
    # 1. Получаем текущие данные из состояния
    data = await state.get_data()
    role = data.get("role")
    
    # 2. Если роль не задана в состоянии (например, бот перезагрузился),
    # попробуем найти последнюю роль пользователя в БД
    if not role:
        async with async_session() as s:
            # Ищем пользователя
            user_res = await s.execute(select(User.id).where(User.telegram_id == m.from_user.id))
            u_id = user_res.scalar()
            
            if u_id:
                # Ищем последнюю поездку этого пользователя
                last_ride_res = await s.execute(
                    select(Ride.role)
                    .where(Ride.user_id == u_id)
                    .order_by(Ride.created_at.desc())
                    .limit(1)
                )
                last_role = last_ride_res.scalar()
                if last_role:
                    role = last_role
    
    # Если роль так и не нашли (новый юзер без кнопок), ставим passenger по умолчанию
    if not role:
        role = "passenger"
        # Запишем в стейт, чтобы дальше не дергать БД
        await state.update_data(role=role) 

    # 3. Передаем роль в NLU
    res = await nlu.parse_intent(m.text, m.from_user.id, role=role)
    
    if not res:
        return await m.answer("Извините, сервис временно недоступен.")

    is_ride_saved = False
    if res.get("origin") and res.get("destination") and res.get("date"):
        # Если мы "угадали" роль из БД, надо обновить её в стейте перед сохранением,
        # так как process_ride_data берет роль из state
        await state.update_data(role=role)
        
        await process_ride_data(m, res, state)
        is_ride_saved = True
    
    # Фильтруем ответ от мусора
    ai_reply = res.get("raw_text", "")
    
    # Удаляем любые блоки кода ``````
    clean_reply = re.sub(r"``````", "", ai_reply, flags=re.DOTALL).strip()
    
    # На всякий случай удаляем остаточные JSON-подобные структуры, если они не были в блоке кода
    # (если ответ начинается с { и заканчивается }, считаем его техническим и скрываем)
    if clean_reply.strip().startswith("{") and clean_reply.strip().endswith("}"):
        clean_reply = ""
    
    if clean_reply:
        await m.answer(clean_reply)
    elif not is_ride_saved:
        await m.answer("🤷🏻‍♂️ Поездка не сохранена! Я не понял детали маршрута. Попробуйте еще раз, указав Откуда, Куда и Дату.")

async def process_ride_data(m: types.Message, res: dict, state: FSMContext):
    data = await state.get_data()
    role = data.get('role', 'passenger')
    
    async with async_session() as s:
        user_stmt = await s.execute(select(User).where(User.telegram_id == m.from_user.id))
        user = user_stmt.scalar()
        if not user: return
    
        parsed_date = parse_date(res['date'])
        if not parsed_date:
            parsed_date = datetime.utcnow().date() + timedelta(days=1) 

        seats = int(res.get('seats', 1 if role == 'passenger' else 3))
        
        # Если время не указано, ставим "По договоренности"
        start_time = res.get('start_time')
        if not start_time or start_time == 'None' or start_time == '':
            start_time = "По договоренности"

        new_ride = Ride(
            user_id=user.id,
            origin=res['origin'],
            destination=res['destination'],
            ride_date=parsed_date,
            start_time=start_time,
            initial_seats=seats,
            seats=seats,
            role=role
        )
        s.add(new_ride)
        await s.commit()
        await s.refresh(new_ride)

        await m.answer(f"✅ Поездка сохранена!", reply_markup=main_kb())

    if role == 'driver':
        await match_passengers(m, new_ride, res, user)
    elif role == 'passenger':
        await notify_drivers_about_passenger(m, new_ride, user)


    await state.clear()

async def match_passengers(m: types.Message, new_ride: Ride, res: dict, user: User):
    target_date = parse_date(res['date'])
    if not target_date: return

    async with async_session() as s:
        matches_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.ride_date == target_date, 
                Ride.role == 'passenger',
                Ride.user_id != user.id
            )
        )
        matches = matches_stmt.all()

        for r_obj, match_user in matches:
            if is_route_compatible(new_ride.origin, new_ride.destination, r_obj.origin, r_obj.destination):
                if new_ride.seats > 0:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="✅ Взять пассажира", callback_data=f"take_{r_obj.id}_{new_ride.id}")
                    
                    username = html.escape(match_user.username or 'скрыт')
                    match_msg = (
                        f"🔔 <b>Найден попутчик (по пути)!</b>\n"
                        f"📍 {html.escape(r_obj.origin)} ➡️ {html.escape(r_obj.destination)}\n"
                        f"📅 {fmt_date(r_obj.ride_date)} | {r_obj.start_time}\n"
                        f"👤 @{username}"
                    )
                    try:
                        await m.bot.send_message(m.from_user.id, match_msg, reply_markup=kb.as_markup(), parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка уведомления водителю: {e}")

async def notify_drivers_about_passenger(m: types.Message, passenger_ride: Ride, passenger_user: User):
    target_date = passenger_ride.ride_date

    async with async_session() as s:
        drivers_stmt = await s.execute(
            select(Ride, User).join(User).where(
                Ride.ride_date == target_date,
                Ride.role == 'driver',
                Ride.seats > 0,
                Ride.user_id != passenger_user.id
            )
        )
        drivers = drivers_stmt.all()

        for driver_ride, driver_user in drivers:
            if not is_route_compatible(driver_ride.origin, driver_ride.destination,
                                       passenger_ride.origin, passenger_ride.destination):
                continue

            kb = InlineKeyboardBuilder()
            kb.button(
                text="✅ Взять пассажира",
                callback_data=f"take_{passenger_ride.id}_{driver_ride.id}"
            )

            msg = (
                f"🔔 <b>Для вас найден пассажир!</b>\n"
                f"📍 {html.escape(passenger_ride.origin)} ➡️ {html.escape(passenger_ride.destination)}\n"
                f"📅 {fmt_date(passenger_ride.ride_date)} | {passenger_ride.start_time}\n"
                f"👥 Нужно мест: {passenger_ride.initial_seats}\n"
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
                return await cb.answer("Места закончились!", show_alert=True)
            
            new_booking = Booking(
                driver_ride_id=d_ride_id,
                passenger_ride_id=p_ride_id,
                status='pending'
            )
            s.add(new_booking)
            await s.commit()
            await s.refresh(new_booking)
            
            p_user_stmt = await s.execute(select(User.telegram_id, User.username).join(Ride).where(Ride.id == p_ride_id))
            res = p_user_stmt.first()
            if not res:
                return await cb.answer("Пассажир не найден (удален)", show_alert=True)
            
            p_tid, p_username = res
            
            kb = InlineKeyboardBuilder()
            kb.button(text="🤝 Еду с вами", callback_data=f"confirm_{new_booking.id}")
            
            driver_username = html.escape(cb.from_user.username or 'скрыт')
            match_msg = (
                f"🔔 <b>Водитель готов вас подвезти!</b>\n"
                f"📍 {html.escape(driver_ride.origin)} ➡️ {html.escape(driver_ride.destination)}\n"
                f"📅 Дата: {fmt_date(driver_ride.ride_date)}\n"
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
            seats_needed = passenger_ride.initial_seats if passenger_ride else 1

            if driver_ride.seats < seats_needed:
                booking.status = 'rejected'
                await s.commit()
                await cb.answer("К сожалению, мест недостаточно!", show_alert=True)
                await cb.message.edit_text(cb.message.text + "\n\n❌ Недостаточно мест")
                return
            
            # --- ВАЖНОЕ ИЗМЕНЕНИЕ ---
            # Обновляем время у пассажира на время водителя
            if passenger_ride and driver_ride.start_time != "По договоренности":
                passenger_ride.start_time = driver_ride.start_time
            # ------------------------

            booking.status = 'confirmed'
            driver_ride.seats -= seats_needed
            await s.commit()
            
            d_user_stmt = await s.execute(select(User.telegram_id).join(Ride).where(Ride.id == booking.driver_ride_id))
            d_tid = d_user_stmt.scalar()
            
            if d_tid:
                await cb.bot.send_message(d_tid, f"🎉 Пассажир подтвердил поездку! Занято мест: {seats_needed}. Приятного пути!")
            
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
                # Удаляем зависимости перед удалением самой поездки
                await s.execute(delete(Booking).where(Booking.driver_ride_id == r_id))
                await s.execute(delete(Booking).where(Booking.passenger_ride_id == r_id))
                
                await s.delete(ride)
                await s.commit()
                await cb.answer("Поездка удалена")
                await cb.message.delete()
            else:
                await cb.answer("Поездка уже удалена", show_alert=True)
                try:
                    await cb.message.delete()
                except:
                    pass
    except Exception as e:
        logger.error(f"Error in delete_ride: {e}")
        await cb.answer("Ошибка при удалении")
