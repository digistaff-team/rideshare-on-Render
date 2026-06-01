# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Запуск бота
python main.py

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-test.txt  # для тестов

# Запуск всех тестов
pytest

# Запуск с покрытием
pytest --cov=src --cov-report=term-missing

# Запуск конкретного файла
pytest tests/test_routes.py -v

# Линтинг (только критические ошибки)
flake8 src --count --select=E9,F63,F7,F82 --show-source --statistics
```

## Architecture

### Entry point

`main.py` запускает два параллельных компонента:
1. **aiohttp веб-сервер** на `PORT` (дефолт 8000) — только health-check endpoints `/` и `/health` для Render
2. **aiogram polling** с одним Router из `src/bot/handlers.py`
3. **Фоновая задача** `auto_clean_old_rides()` — удаляет поездки старше 2 дней каждый час

### Два функциональных домена

**Поездки (Rides):** Пользователь нажимает «🙋 Подвези» или «🚗 Подвезу», входит в пошаговый FSM: `RideForm.waiting_for_input` → `waiting_for_origin` → `waiting_for_destination` → `waiting_for_date` → `waiting_for_confirmation`. Первое сообщение парсится `SimpleParser` (`src/services/simple_parser.py`) целиком — если все поля найдены, бот сразу показывает экран подтверждения. Недостающие поля запрашиваются по одному с клавиатурой (города из `ROUTE_ORDER`, даты кнопками). После подтверждения вызывается `process_ride_data`, которая сохраняет поездку и ищет совпадения (`match_passengers` / `notify_drivers_about_passenger`). NLU/Pro-Talk API не используется.

**Доставка (Delivery):** Пользователь нажимает «🛍 Привези» или «🛒 Привезу», входит в `DeliveryRequestForm` / `DeliveryOfferForm`. Текст парсится простым regex-парсером `parse_delivery_text()` (NLU для доставки не реализован — помечен TODO в коде). После подтверждения запускается `run_matching_for_request` / `run_matching_for_offer` из `src/services/delivery_matching.py`.

### Сопоставление маршрутов

`ROUTE_ORDER` в `src/config.py` задаёт упорядоченный список остановок. `is_route_compatible()` в `handlers.py` проверяет, что маршрут пассажира лежит внутри маршрута водителя в том же направлении (по индексам в списке).

### База данных

- Локальная разработка: SQLite (`test_bot.db`)
- Продакшен: PostgreSQL (URL из `DATABASE_URL`, автоматически конвертируется `postgres://` → `postgresql+asyncpg://` в `session.py`)
- FSM-состояния: `MemoryStorage` локально, `RedisStorage` при наличии `REDIS_URL`
- Все запросы асинхронные через `async_session` (фабрика из `session.py`)

### Модели данных

- `User` → `Ride` (1:many) → `Booking` (связывает driver_ride и passenger_ride)
- `User` → `DeliveryRequest` (1:many) и `User` → `DeliveryOffer` (1:many)
- `DeliveryMatch` связывает `DeliveryRequest` и `DeliveryOffer`; статусы: `pending → confirmed/rejected → completed`

### Переменные окружения

| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | Telegram Bot token (обязательно) |
| `DATABASE_URL` | PostgreSQL URL (иначе SQLite) |
| `REDIS_URL` | Redis для FSM в продакшене |
| `PORT` | Порт веб-сервера (дефолт 8000) |

### Тесты

Тесты используют SQLite in-memory через фикстуры в `tests/conftest.py`. Общие фикстуры: `db_session`, `user`, `driver_ride`, `passenger_ride`, `mock_bot`, `mock_message`, `mock_state`.

### Утилиты

`src/utils/__init__.py` содержит три функции, используемые в `handlers.py`: `extract_seats(text)`, `validate_city_name(city)`, `validate_seats(seats)`.
