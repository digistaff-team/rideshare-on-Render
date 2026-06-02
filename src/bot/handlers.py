import asyncio
import logging
import html
import re
from datetime import datetime, timedelta, date
from sqlalchemy import delete, select, update
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database.session import async_session
from src.database.models import User, Ride, Booking, DeliveryRequest, DeliveryOffer, DeliveryMatch
from src.services.simple_parser import SimpleParser
from src.services.delivery_matching import run_matching_for_request, run_matching_for_offer
from src.config import (
    ROUTE_ORDER,
    POPULAR_STORES,
    CLEANUP_INTERVAL_SECONDS,
    CLEANUP_DAYS_BACK,
    DELIVERY_CLEANUP_DAYS,
    MAX_RIDES_TO_FETCH,
    MAX_RIDES_TO_DISPLAY,
    MAX_CITY_NAME_LENGTH,
    MAX_STORE_NAME_LENGTH,
    MAX_REQUEST_TEXT_LENGTH,
    MIN_SEATS,
    MAX_SEATS,
    MIN_CAPACITY,
    MAX_CAPACITY,
)
from src.utils import extract_seats, validate_city_name, validate_seats

logger = logging.getLogger(__name__)
router = Router()
parser = SimpleParser()


# ============================================================
# FSM STATES
# ============================================================

class RideForm(StatesGroup):
    waiting_for_input = State()
    waiting_for_origin = State()
    waiting_for_destination = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_seats = State()
    waiting_for_confirmation = State()


class DeliveryRequestForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirmation = State()


class DeliveryOfferForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirmation = State()


# ============================================================
# KEYBOARDS
# ============================================================

def main_kb() -> ReplyKeyboardMarkup:
    """Возвращает основную клавиатуру бота."""
    kb = [
        [KeyboardButton(text="🙋 Подвези"), KeyboardButton(text="🚗 Подвезу")],
        [KeyboardButton(text="🔍 Найти поездку"), KeyboardButton(text="📋 Мои поездки")],
        [KeyboardButton(text="🛍 Привези"), KeyboardButton(text="🛒 Привезу")],
        [KeyboardButton(text="📦 Мои доставки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def delivery_cancel_kb() -> ReplyKeyboardMarkup:
    """Клавиатура отмены для доставки."""
    kb = [[KeyboardButton(text="❌ Отменить")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def delivery_confirm_kb() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения для доставки."""
    kb = [
        [KeyboardButton(text="✅ Подтвердить")],
        [KeyboardButton(text="❌ Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def city_kb() -> ReplyKeyboardMarkup:
    """Клавиатура выбора города из маршрута."""
    rows = []
    row = []
    for i, city in enumerate(ROUTE_ORDER):
        row.append(KeyboardButton(text=city))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="❌ Отменить")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def date_kb() -> ReplyKeyboardMarkup:
    """Клавиатура выбора даты (сегодня/завтра/послезавтра)."""
    today = datetime.now().date()
    rows = [
        [
            KeyboardButton(text=f"Сегодня ({today.strftime('%d.%m')})"),
            KeyboardButton(text=f"Завтра ({(today + timedelta(days=1)).strftime('%d.%m')})"),
        ],
        [KeyboardButton(text=f"Послезавтра ({(today + timedelta(days=2)).strftime('%d.%m')})")],
        [KeyboardButton(text="❌ Отменить")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def seats_kb() -> ReplyKeyboardMarkup:
    """Клавиатура выбора количества свободных мест (1–3)."""
    kb = [
        [KeyboardButton(text="1 место"), KeyboardButton(text="2 места"), KeyboardButton(text="3 места")],
        [KeyboardButton(text="❌ Отменить")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def time_kb() -> ReplyKeyboardMarkup:
    """Клавиатура быстрого выбора времени выезда."""
    rows = [
        [KeyboardButton(text="06:00"), KeyboardButton(text="07:00"), KeyboardButton(text="08:00"), KeyboardButton(text="09:00")],
        [KeyboardButton(text="10:00"), KeyboardButton(text="11:00"), KeyboardButton(text="12:00"), KeyboardButton(text="13:00")],
        [KeyboardButton(text="14:00"), KeyboardButton(text="15:00"), KeyboardButton(text="16:00"), KeyboardButton(text="17:00")],
        [KeyboardButton(text="18:00"), KeyboardButton(text="19:00"), KeyboardButton(text="20:00"), KeyboardButton(text="21:00")],
        [KeyboardButton(text="❌ Отменить")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def ride_confirm_kb() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения поездки."""
    kb = [
        [KeyboardButton(text="✅ Подтвердить")],
        [KeyboardButton(text="❌ Отменить")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _parse_city_from_text(text: str) -> str | None:
    """Распознаёт город по нажатию кнопки или свободному вводу."""
    text_clean = text.strip()
    if not text_clean:
        return None
    text_lower = text_clean.lower()
    for city in ROUTE_ORDER:
        city_lower = city.lower()
        if city_lower in text_lower or text_lower in city_lower:
            return city
    return None


def get_city_index(city_name: str) -> int:
    """Возвращает индекс города в маршруте или -1 если не найден."""
    city_name = city_name.lower().strip()
    if not city_name:
        return -1
    for i, stop in enumerate(ROUTE_ORDER):
        stop_lower = stop.lower()
        if stop_lower in city_name or city_name in stop_lower:
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
        "Привет! Я помогу найти попутчиков и заказать доставку продуктов.\n\n"
        "<b>Поездки:</b>\n"
        "🙋 Подвези — найти водителя\n"
        "🚗 Подвезу — найти пассажиров\n"
        "🔍 Найти поездку — все доступные поездки\n"
        "📋 Мои поездки — управление поездками\n\n"
        "<b>Доставка:</b>\n"
        "🛍 Привези — заказать доставку из магазина\n"
        "🛒 Привезу — предложить доставку из магазина\n"
        "📦 Мои доставки — управление заявками"
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
_RIDE_MAIN_BUTTONS = {
    "📋 Мои поездки", "🔍 Найти поездку", "🙋 Подвези", "🚗 Подвезу",
    "🛍 Привези", "🛒 Привезу", "📦 Мои доставки",
}

@router.message(F.text.in_(["🙋 Подвези", "🚗 Подвезу"]))
async def ask_route(m: types.Message, state: FSMContext):
    await state.clear()
    role = "passenger" if "🙋" in m.text else "driver"
    await state.update_data(role=role)
    await state.set_state(RideForm.waiting_for_input)

    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отменить")]],
        resize_keyboard=True,
    )
    text = (
        "Напишите маршрут одним сообщением, например:\n"
        "«Из Краснодара в Сказочный завтра в 9 утра»\n\n"
        "Или я спрошу пошагово."
        if role == "passenger" else
        "Напишите маршрут одним сообщением, например:\n"
        "«Из Сказочного в Краснодар завтра в 9 утра, 2 места»\n\n"
        "Или я спрошу пошагово."
    )
    await m.answer(text, reply_markup=cancel_kb)


# --- ШАГ 1: первое сообщение — пробуем распарсить всё сразу ---
@router.message(
    RideForm.waiting_for_input,
    F.text & ~F.text.startswith("/") & ~F.text.in_(_RIDE_MAIN_BUTTONS | {"❌ Отменить"}),
)
async def handle_ride_input(m: types.Message, state: FSMContext):
    parsed = parser.parse(m.text)
    if parsed:
        updates = {k: v for k, v in parsed.items() if v is not None}
        if updates:
            await state.update_data(**updates)
    await _proceed_to_next_field(m, state)


async def _proceed_to_next_field(m: types.Message, state: FSMContext):
    """Переходит к следующему недостающему полю или к экрану подтверждения."""
    data = await state.get_data()

    if not data.get("origin"):
        await state.set_state(RideForm.waiting_for_origin)
        await m.answer("📍 <b>Откуда едете?</b>", reply_markup=city_kb(), parse_mode="HTML")
        return

    if not data.get("destination"):
        await state.set_state(RideForm.waiting_for_destination)
        await m.answer("📍 <b>Куда едете?</b>", reply_markup=city_kb(), parse_mode="HTML")
        return

    if not data.get("date"):
        await state.set_state(RideForm.waiting_for_date)
        await m.answer("📅 <b>Когда?</b>", reply_markup=date_kb(), parse_mode="HTML")
        return

    if not data.get("start_time") and data.get("role") == "driver":
        await state.set_state(RideForm.waiting_for_time)
        await m.answer("🕐 <b>Время выезда?</b>", reply_markup=time_kb(), parse_mode="HTML")
        return

    if data.get("seats") is None:
        await state.set_state(RideForm.waiting_for_seats)
        role = data.get("role", "passenger")
        label = "💺 <b>Сколько свободных мест?</b>" if role == "driver" else "💺 <b>Сколько мест нужно?</b>"
        await m.answer(label, reply_markup=seats_kb(), parse_mode="HTML")
        return

    await _show_ride_confirmation(m, state)


# --- ШАГ 2a: ввод города отправления ---
@router.message(
    RideForm.waiting_for_origin,
    F.text & ~F.text.startswith("/") & ~F.text.in_({"❌ Отменить"}),
)
async def handle_ride_origin(m: types.Message, state: FSMContext):
    city = _parse_city_from_text(m.text)
    if not city:
        await m.answer(
            "❓ Не распознан город. Выберите из списка или напишите название.",
            reply_markup=city_kb(),
        )
        return
    await state.update_data(origin=city)
    await _proceed_to_next_field(m, state)


# --- ШАГ 2b: ввод города назначения ---
@router.message(
    RideForm.waiting_for_destination,
    F.text & ~F.text.startswith("/") & ~F.text.in_({"❌ Отменить"}),
)
async def handle_ride_destination(m: types.Message, state: FSMContext):
    city = _parse_city_from_text(m.text)
    if not city:
        await m.answer(
            "❓ Не распознан город. Выберите из списка или напишите название.",
            reply_markup=city_kb(),
        )
        return
    await state.update_data(destination=city)
    await _proceed_to_next_field(m, state)


# --- ШАГ 2c: ввод даты ---
@router.message(
    RideForm.waiting_for_date,
    F.text & ~F.text.startswith("/") & ~F.text.in_({"❌ Отменить"}),
)
async def handle_ride_date(m: types.Message, state: FSMContext):
    text_lower = m.text.lower()
    today = datetime.now().date()

    if text_lower.startswith("послезавтра"):
        parsed_date = today + timedelta(days=2)
    elif text_lower.startswith("завтра"):
        parsed_date = today + timedelta(days=1)
    elif text_lower.startswith("сегодня"):
        parsed_date = today
    else:
        parsed_date = parse_date(m.text)

    if not parsed_date:
        await m.answer(
            "❓ Не понял дату. Выберите кнопку или напишите, например: 15.06.2026",
            reply_markup=date_kb(),
        )
        return

    await state.update_data(date=parsed_date.strftime("%Y-%m-%d"))
    await _proceed_to_next_field(m, state)


# --- ШАГ 2d: ввод времени выезда ---
@router.message(
    RideForm.waiting_for_time,
    F.text & ~F.text.startswith("/") & ~F.text.in_({"❌ Отменить"}),
)
async def handle_ride_time(m: types.Message, state: FSMContext):
    text = m.text.strip()

    # Прямой формат HH:MM
    time_match = re.match(r'^(\d{1,2}):(\d{2})$', text)
    if time_match:
        h, mins = int(time_match.group(1)), int(time_match.group(2))
        if 0 <= h <= 23 and 0 <= mins <= 59:
            await state.update_data(start_time=f"{h:02d}:{mins:02d}")
            await _proceed_to_next_field(m, state)
            return

    # Попытка распарсить через SimpleParser (поддерживает «9 утра», «в 18 часов» и т.п.)
    parsed = parser.parse(text)
    if parsed and parsed.get("start_time"):
        await state.update_data(start_time=parsed["start_time"])
        await _proceed_to_next_field(m, state)
        return

    await m.answer(
        "❓ Не понял время. Выберите кнопку или напишите, например: 09:00 или «в 9 утра»",
        reply_markup=time_kb(),
    )


# --- ШАГ 2e: выбор количества мест (только водитель) ---
@router.message(
    RideForm.waiting_for_seats,
    F.text & ~F.text.startswith("/") & ~F.text.in_({"❌ Отменить"}),
)
async def handle_ride_seats(m: types.Message, state: FSMContext):
    text = m.text.strip()
    seats_map = {"1 место": 1, "2 места": 2, "3 места": 3}
    if text in seats_map:
        await state.update_data(seats=seats_map[text])
        await _proceed_to_next_field(m, state)
        return
    # Свободный ввод числа
    digits = re.findall(r'\d+', text)
    if digits:
        n = int(digits[0])
        if 1 <= n <= 3:
            await state.update_data(seats=n)
            await _proceed_to_next_field(m, state)
            return
    await m.answer("❓ Выберите 1, 2 или 3 места.", reply_markup=seats_kb())


async def _show_ride_confirmation(m: types.Message, state: FSMContext):
    """Показывает итоговый экран перед сохранением поездки."""
    data = await state.get_data()
    role = data.get("role", "passenger")
    origin = data.get("origin", "—")
    destination = data.get("destination", "—")
    ride_date = data.get("date")
    time = data.get("start_time") or "По договоренности"
    seats = data.get("seats", 1 if role == "passenger" else 3)

    role_label = "🙋 Пассажир" if role == "passenger" else "🚗 Водитель"
    date_display = fmt_date(ride_date) if ride_date else "—"
    time_line = f"🕐 {time}\n" if role == "driver" else ""

    text = (
        f"<b>Подтвердите поездку</b>\n\n"
        f"{role_label}\n"
        f"📍 {html.escape(origin)} → {html.escape(destination)}\n"
        f"📅 {date_display}\n"
        f"{time_line}"
        f"💺 Мест: {seats}\n\n"
        "Всё верно?"
    )
    await state.set_state(RideForm.waiting_for_confirmation)
    await m.answer(text, reply_markup=ride_confirm_kb(), parse_mode="HTML")


# --- ШАГ 3: подтверждение ---
@router.message(RideForm.waiting_for_confirmation, F.text == "✅ Подтвердить")
async def confirm_ride(m: types.Message, state: FSMContext):
    data = await state.get_data()
    res = {
        "origin": data.get("origin"),
        "destination": data.get("destination"),
        "date": data.get("date"),
        "start_time": data.get("start_time"),
        "seats": data.get("seats"),
    }
    await process_ride_data(m, res, state)


# --- ОТМЕНА ПОЕЗДКИ (любой шаг) ---
@router.message(
    StateFilter(
        RideForm.waiting_for_input,
        RideForm.waiting_for_origin,
        RideForm.waiting_for_destination,
        RideForm.waiting_for_date,
        RideForm.waiting_for_time,
        RideForm.waiting_for_seats,
        RideForm.waiting_for_confirmation,
    ),
    F.text == "❌ Отменить",
)
async def cancel_ride(m: types.Message, state: FSMContext):
    await state.clear()
    chat_id = m.chat.id
    for msg_id in (m.message_id, m.message_id - 1, m.message_id - 2):
        try:
            await m.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    await m.answer("❌ Отменено. Выберите действие:", reply_markup=main_kb())


async def process_ride_data(m: types.Message, res: dict, state: FSMContext):
    """Сохранение данных поездки в БД"""

    data = await state.get_data()
    role = data.get('role', 'passenger')
    new_ride = None
    saved_user = None

    try:
        async with async_session() as s:
            user_stmt = await s.execute(select(User).where(User.telegram_id == m.from_user.id))
            user = user_stmt.scalar()
            if not user:
                user = User(telegram_id=m.from_user.id, username=m.from_user.username)
                s.add(user)
                await s.commit()
                await s.refresh(user)
            saved_user = user

            parsed_date = parse_date(res['date'])
            if not parsed_date:
                parsed_date = datetime.utcnow().date() + timedelta(days=1)

            seats = int(res.get('seats') or (1 if role == 'passenger' else 3))

            start_time = res.get('start_time')
            if not start_time or start_time == 'None' or start_time == '':
                start_time = "По договоренности"

            new_ride = Ride(
                user_id=user.id,
                origin=(res.get('origin') or '')[:MAX_CITY_NAME_LENGTH],
                destination=(res.get('destination') or '')[:MAX_CITY_NAME_LENGTH],
                date=parsed_date,
                start_time=start_time,
                seats=seats,
                initial_seats=seats,
                role=role
            )

            s.add(new_ride)
            await s.commit()
            await s.refresh(new_ride)

            logger.info(
                f"✅ Поездка сохранена: ID={new_ride.id}, user={m.from_user.id}, "
                f"role={role}, origin={res.get('origin')}, destination={res.get('destination')}, "
                f"date={parsed_date}, seats={seats}"
            )

        await m.answer("✅ Поездка сохранена!", reply_markup=main_kb())

        if role == 'driver':
            await match_passengers(m, new_ride, res, saved_user)
        elif role == 'passenger':
            await notify_drivers_about_passenger(m, new_ride, saved_user)

    except Exception as e:
        logger.error(f"Ошибка сохранения поездки: {e}", exc_info=True)
        await m.answer("❌ Ошибка при сохранении поездки. Попробуйте снова.", reply_markup=main_kb())
    finally:
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


# ============================================================
# ДОСТАВКА (Delivery Module)
# ============================================================

# --- КНОПКИ ДОСТАВКИ ---
@router.message(F.text.in_(["🛍 Привези", "🛒 Привезу"]))
async def ask_delivery(m: types.Message, state: FSMContext):
    """Обработчик кнопок доставки."""
    await state.clear()
    
    is_request = "🛍" in m.text  # True для "Привези", False для "Привезу"
    role = "request" if is_request else "offer"
    await state.update_data(role=role)
    
    if is_request:
        await state.set_state(DeliveryRequestForm.waiting_for_text)
        text = (
            "🛍 <b>Заказ доставки</b>\n\n"
            "Напишите, что нужно привезти. Например:\n"
            "«Привези продукты из Пятёрочки сегодня до 18:00»\n\n"
            "Укажите магазин, желаемое время и список товаров."
        )
    else:
        await state.set_state(DeliveryOfferForm.waiting_for_text)
        text = (
            "🛒 <b>Предложение доставки</b>\n\n"
            "Напишите, куда вы едете. Например:\n"
            "«Еду в Пятёрочку сегодня в 15:00, могу взять 3 заказа»\n\n"
            "Укажите магазин, время поездки и сколько заказов можете взять."
        )
    
    await m.answer(text, reply_markup=delivery_cancel_kb(), parse_mode="HTML")


# --- ОБРАБОТКА ТЕКСТА ДЛЯ ДОСТАВКИ ---
@router.message(
    DeliveryRequestForm.waiting_for_text,
    F.text & ~F.text.startswith("/")
)
async def handle_delivery_request_text(m: types.Message, state: FSMContext):
    """Обработка текста для заявки «Привези»."""
    await process_delivery_text(m, state, "request")


@router.message(
    DeliveryOfferForm.waiting_for_text,
    F.text & ~F.text.startswith("/")
)
async def handle_delivery_offer_text(m: types.Message, state: FSMContext):
    """Обработка текста для предложения «Привезу»."""
    await process_delivery_text(m, state, "offer")


async def process_delivery_text(m: types.Message, state: FSMContext, delivery_type: str):
    """
    Общая функция обработки текста для доставки.
    Использует NLU + fallback parser для извлечения данных.
    """
    user_text = m.text
    
    # TODO: Добавить NLU для доставки (Phase 2)
    # Пока используем простой парсинг
    parsed_data = parse_delivery_text(user_text)
    
    # Сохраняем данные в state
    await state.update_data(**parsed_data)
    await state.update_data(original_text=user_text)
    
    # Показываем подтверждение
    await show_delivery_confirmation(m, state, delivery_type)


_STORE_MAP = [
    (["пятёрочк", "пятерочк"], "Пятёрочка"),
    (["магнит"], "Магнит"),
    (["перекрёсток", "перекресток"], "Перекрёсток"),
    (["лент"], "Лента"),
    (["ашан"], "Ашан"),
]


def parse_delivery_text(text: str) -> dict:
    """Простой парсер для извлечения данных о доставке."""
    result = {
        "store": "Пятёрочка",
        "date": None,
        "time": None,
        "capacity": 1,
    }

    text_lower = text.lower()

    # Определение магазина
    for keywords, store_name in _STORE_MAP:
        if any(kw in text_lower for kw in keywords):
            result["store"] = store_name
            break

    # Поиск даты ("послезавтра" должен быть раньше "завтра")
    today = datetime.now().date()

    if "послезавтра" in text_lower:
        result["date"] = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "завтра" in text_lower:
        result["date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "сегодня" in text_lower:
        result["date"] = today.strftime("%Y-%m-%d")

    # Поиск времени
    time_match = re.search(r"(\d{1,2}):(\d{2})", text)
    if time_match:
        result["time"] = f"{time_match.group(1)}:{time_match.group(2)}"
    else:
        # Поиск времени словами
        if "утра" in text_lower or "вечера" in text_lower:
            hour_match = re.search(r"(\d{1,2})\s*(?:утра|вечера)", text_lower)
            if hour_match:
                hour = int(hour_match.group(1))
                if "вечера" in text_lower and hour < 12:
                    hour += 12
                result["time"] = f"{hour:02d}:00"

    # Поиск количества заказов
    capacity_match = re.search(r"(\d+)\s*(?:заказ|заказа|заказов)", text_lower)
    if capacity_match:
        result["capacity"] = int(capacity_match.group(1))

    return result


async def show_delivery_confirmation(m: types.Message, state: FSMContext, delivery_type: str):
    """Показывает подтверждение перед сохранением доставки."""
    data = await state.get_data()
    
    store = data.get("store", "Пятёрочка")
    date = data.get("date")
    time = data.get("time")
    capacity = data.get("capacity", 1)
    original_text = data.get("original_text", "")
    
    # Проверяем, что дата и время указаны
    if not date or not time:
        missing = []
        if not date:
            missing.append("дату (сегодня/завтра или в формате 15.03.2024)")
        if not time:
            missing.append("время (в 15:00 или в 3 часа дня)")
        
        await m.answer(
            f"⚠️ Не указаны {', '.join(missing)}.\n\n"
            f"Пожалуйста, напишите ещё раз с указанием всех деталей.\n"
            f"Например: «Привези продукты из Пятёрочки сегодня в 18:00»",
            reply_markup=delivery_cancel_kb()
        )
        await state.clear()
        return
    
    # Форматируем дату для отображения
    display_date = date
    if date:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            display_date = date_obj.strftime("%d.%m.%Y")
        except:
            pass
    
    if delivery_type == "request":
        text = (
            "🛍 <b>Подтверждение заявки</b>\n\n"
            f"🏪 Магазин: {store}\n"
            f"📅 Дата: {display_date}\n"
            f"🕐 Время: {time}\n\n"
            f"📝 Заказ: {original_text}\n\n"
            "Правильно ли я понял?"
        )
    else:
        text = (
            "🛒 <b>Подтверждение предложения</b>\n\n"
            f"🏪 Магазин: {store}\n"
            f"📅 Дата: {display_date}\n"
            f"🕐 Время: {time}\n"
            f"📦 Мест для заказов: {capacity}\n\n"
            f"💬 Комментарий: {original_text}\n\n"
            "Правильно ли я понял?"
        )
    
    await m.answer(text, reply_markup=delivery_confirm_kb(), parse_mode="HTML")
    await state.set_state(
        DeliveryRequestForm.waiting_for_confirmation if delivery_type == "request"
        else DeliveryOfferForm.waiting_for_confirmation
    )


# --- ПОДТВЕРЖДЕНИЕ ДОСТАВКИ ---
@router.message(
    StateFilter(DeliveryRequestForm.waiting_for_confirmation, DeliveryOfferForm.waiting_for_confirmation),
    F.text == "✅ Подтвердить"
)
async def confirm_delivery(m: types.Message, state: FSMContext):
    """Сохранение заявки/предложения доставки."""
    data = await state.get_data()
    delivery_type = data.get("role")
    
    # Получаем bot из state.storage
    bot = m.bot
    
    async with async_session() as s:
        # Находим или создаём пользователя
        user_result = await s.execute(select(User).where(User.telegram_id == m.from_user.id))
        user = user_result.scalar()

        if not user:
            user = User(telegram_id=m.from_user.id, username=m.from_user.username)
            s.add(user)
            await s.commit()
            await s.refresh(user)

        store = data.get("store", "Не указан")
        date = data.get("date")
        time = data.get("time")
        original_text = data.get("original_text", "")
        capacity = data.get("capacity", 1)

        if delivery_type == "request":
            # Создаём заявку
            request = DeliveryRequest(
                user_id=user.id,
                store=store[:MAX_STORE_NAME_LENGTH],
                request_text=original_text[:MAX_REQUEST_TEXT_LENGTH],
                desired_date=date,
                desired_time_text=time,
                status="active"
            )
            s.add(request)
            await s.commit()
            await s.refresh(request)

            logger.info(f"🛍 Создана доставка: ID={request.id}, user={user.id}, store={store}")

            await m.answer(
                f"✅ Заявка на доставку сохранена!\n\n"
                f"Ищу исполнителей...",
                reply_markup=main_kb()
            )

            # Запускаем matching с уведомлениями
            await run_matching_for_request(request, bot)

        else:
            # Создаём предложение
            offer = DeliveryOffer(
                user_id=user.id,
                store=store[:MAX_STORE_NAME_LENGTH],
                comment=original_text[:MAX_REQUEST_TEXT_LENGTH],
                trip_date=date,
                trip_time=time,
                capacity=min(capacity, MAX_CAPACITY),
                status="active"
            )
            s.add(offer)
            await s.commit()
            await s.refresh(offer)
            
            logger.info(f"🛒 Создано предложение: ID={offer.id}, user={user.id}, store={store}")

            await m.answer(
                f"✅ Предложение доставки сохранено!\n\n"
                f"Ищу заказы...",
                reply_markup=main_kb()
            )

            # Запускаем matching с уведомлениями
            await run_matching_for_offer(offer, bot)

    await state.clear()


# --- ОТМЕНА ДОСТАВКИ ---
@router.message(
    StateFilter(
        DeliveryRequestForm.waiting_for_text,
        DeliveryOfferForm.waiting_for_text,
        DeliveryRequestForm.waiting_for_confirmation,
        DeliveryOfferForm.waiting_for_confirmation,
    ),
    F.text == "❌ Отменить"
)
async def cancel_delivery(m: types.Message, state: FSMContext):
    """Отмена создания доставки."""
    await state.clear()
    await m.answer("❌ Отменено. Выберите действие:", reply_markup=main_kb())


# --- МОИ ДОСТАВКИ ---
@router.message(Command("my_deliveries"))
@router.message(F.text == "📦 Мои доставки")
async def list_deliveries(m: types.Message, state: FSMContext):
    """Показ списка доставок пользователя."""
    await state.clear()

    async with async_session() as s:
        # Находим пользователя
        user_result = await s.execute(select(User).where(User.telegram_id == m.from_user.id))
        user = user_result.scalar()

        if not user:
            return await m.answer("Сначала нажмите /start")

        # Получаем заявки и предложения
        requests_result = await s.execute(
            select(DeliveryRequest).where(
                DeliveryRequest.user_id == user.id
            ).order_by(DeliveryRequest.created_at.desc())
        )
        requests = requests_result.scalars().all()

        offers_result = await s.execute(
            select(DeliveryOffer).where(
                DeliveryOffer.user_id == user.id
            ).order_by(DeliveryOffer.created_at.desc())
        )
        offers = offers_result.scalars().all()

        if not requests and not offers:
            return await m.answer("У вас пока нет активных доставок.")

        messages_sent = 0
        
        # Показываем заявки
        if requests:
            messages_sent += 1
            for req in requests[:5]:  # Показываем последние 5
                status_emoji = {"active": "🟢", "matched": "🟡", "confirmed": "🔵", "completed": "✅", "cancelled": "❌"}.get(req.status, "⚪")
                date_display = req.desired_date or "Не указана"
                if date_display and len(date_display) == 10:
                    try:
                        date_display = datetime.strptime(date_display, "%Y-%m-%d").strftime("%d.%m.%Y")
                    except:
                        pass

                text = (
                    f"{status_emoji} <b>🛍 Мои заявки (Привези): {req.store}</b>\n"
                    f"📅 {date_display} | 🕐 {req.desired_time_text or 'Не указано'}\n"
                    f"📝 {req.request_text[:100]}{'...' if len(req.request_text) > 100 else ''}\n"
                    f"Статус: {req.status}"
                )

                # Кнопки управления
                kb = InlineKeyboardBuilder()
                if req.status == "active":
                    kb.button(text="❌ Отменить", callback_data=f"del_req_{req.id}")
                
                # Добавляем кнопки для pending matches
                if req.matches:
                    for match in req.matches[:3]:  # Показываем первые 3 match
                        if match.status == "pending":
                            offer = await s.get(DeliveryOffer, match.offer_id)
                            if offer:
                                kb.button(
                                    text="✅ Взять заказ",
                                    callback_data=f"confirm_match_{match.id}"
                                )
                                kb.button(
                                    text="❌ Отклонить",
                                    callback_data=f"reject_match_{match.id}"
                                )
                
                if kb.buttons:
                    await m.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
                else:
                    await m.answer(text, parse_mode="HTML")

        # Показываем предложения
        if offers:
            if messages_sent > 0:
                await asyncio.sleep(0.5)  # Небольшая пауза между сообщениями
            
            for offer in offers[:5]:  # Показываем последние 5
                status_emoji = {"active": "🟢", "full": "🔴", "completed": "✅", "cancelled": "❌"}.get(offer.status, "⚪")
                date_display = offer.trip_date or "Не указана"
                if date_display and len(date_display) == 10:
                    try:
                        date_display = datetime.strptime(date_display, "%Y-%m-%d").strftime("%d.%m.%Y")
                    except:
                        pass

                text = (
                    f"{status_emoji} <b>🛒 Мои предложения (Привезу): {offer.store}</b>\n"
                    f"📅 {date_display} | 🕐 {offer.trip_time or 'Не указано'}\n"
                    f"📦 Мест: {offer.capacity - offer.orders_taken}/{offer.capacity}\n"
                    f"Статус: {offer.status}"
                )

                # Кнопки управления
                kb = InlineKeyboardBuilder()
                if offer.status == "active":
                    kb.button(text="❌ Отменить", callback_data=f"del_offer_{offer.id}")
                
                # Добавляем кнопки для pending matches
                if offer.matches:
                    for match in offer.matches[:3]:  # Показываем первые 3 match
                        if match.status == "pending":
                            request = await s.get(DeliveryRequest, match.request_id)
                            if request:
                                kb.button(
                                    text="✅ Подтвердить",
                                    callback_data=f"confirm_match_{match.id}"
                                )
                                kb.button(
                                    text="❌ Отклонить",
                                    callback_data=f"reject_match_{match.id}"
                                )
                
                if kb.buttons:
                    await m.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
                else:
                    await m.answer(text, parse_mode="HTML")


# --- CALLBACKS ДЛЯ ДОСТАВКИ ---
@router.callback_query(F.data.startswith("del_req_"))
async def cancel_delivery_request(cb: types.CallbackQuery):
    """Отмена заявки на доставку."""
    try:
        req_id = int(cb.data.split("_")[-1])
        
        async with async_session() as s:
            request = await s.get(DeliveryRequest, req_id)
            
            if request and request.status == "active":
                request.status = "cancelled"
                await s.commit()
                logger.info(f"🗑️ Заявка на доставку отменена: ID={req_id}, user={cb.from_user.id}")
                await cb.answer("Заявка отменена")
                await cb.message.edit_text(cb.message.text + "\n\n❌ Отменено")
            else:
                await cb.answer("Заявка уже не активна", show_alert=True)
                
    except Exception as e:
        logger.error(f"Error in cancel_delivery_request: {e}")
        await cb.answer("Ошибка при отмене")


@router.callback_query(F.data.startswith("del_offer_"))
async def cancel_delivery_offer(cb: types.CallbackQuery):
    """Отмена предложения доставки."""
    try:
        offer_id = int(cb.data.split("_")[-1])

        async with async_session() as s:
            offer = await s.get(DeliveryOffer, offer_id)

            if offer and offer.status == "active":
                offer.status = "cancelled"
                await s.commit()
                logger.info(f"🗑️ Предложение доставки отменено: ID={offer_id}, user={cb.from_user.id}")
                await cb.answer("Предложение отменено")
                await cb.message.edit_text(cb.message.text + "\n\n❌ Отменено")
            else:
                await cb.answer("Предложение уже не активно", show_alert=True)

    except Exception as e:
        logger.error(f"Error in cancel_delivery_offer: {e}")
        await cb.answer("Ошибка при отмене")


# --- CALLBACKS ДЛЯ MATCH ---
@router.callback_query(F.data.startswith("confirm_match_"))
async def confirm_delivery_match(cb: types.CallbackQuery):
    """Подтверждение match."""
    try:
        match_id = int(cb.data.split("_")[-1])

        async with async_session() as s:
            match = await s.get(DeliveryMatch, match_id)
            
            if not match:
                return await cb.answer("Match не найден", show_alert=True)
            
            if match.status != "pending":
                return await cb.answer("Match уже обработан", show_alert=True)
            
            match.status = "confirmed"
            match.confirmed_at = datetime.utcnow()
            
            # Увеличиваем orders_taken у offer
            offer = await s.get(DeliveryOffer, match.offer_id)
            if offer:
                offer.orders_taken += 1
                if offer.orders_taken >= offer.capacity:
                    offer.status = "full"
            
            # Обновляем статус request
            request = await s.get(DeliveryRequest, match.request_id)
            if request and request.status == "active":
                request.status = "matched"
            
            await s.commit()
            
            logger.info(f"✅ Match подтверждён: ID={match_id}")
            await cb.answer("Доставка подтверждена!")
            await cb.message.edit_text(cb.message.text + "\n\n✅ Подтверждено")
            
    except Exception as e:
        logger.error(f"Error in confirm_delivery_match: {e}")
        await cb.answer("Ошибка при подтверждении")


@router.callback_query(F.data.startswith("reject_match_"))
async def reject_delivery_match(cb: types.CallbackQuery):
    """Отклонение match."""
    try:
        match_id = int(cb.data.split("_")[-1])

        async with async_session() as s:
            match = await s.get(DeliveryMatch, match_id)
            
            if not match:
                return await cb.answer("Match не найден", show_alert=True)
            
            if match.status != "pending":
                return await cb.answer("Match уже обработан", show_alert=True)
            
            match.status = "rejected"
            await s.commit()
            
            logger.info(f"❌ Match отклонён: ID={match_id}")
            await cb.answer("Match отклонён")
            await cb.message.edit_text(cb.message.text + "\n\n❌ Отклонено")
            
    except Exception as e:
        logger.error(f"Error in reject_delivery_match: {e}")
        await cb.answer("Ошибка при отклонении")
