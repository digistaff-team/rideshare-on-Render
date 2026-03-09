# Тестирование Ride Share Bot

## Структура тестов

```
tests/
├── conftest.py           # Общие фикстуры и настройки
├── test_utils.py         # Тесты утилит (extract_seats, validate)
├── test_config.py        # Тесты конфигурации
├── test_routes.py        # Тесты логики маршрутов
├── test_dates.py         # Тесты дат
├── test_simple_parser.py # Тесты простого парсера
├── test_nlu.py           # Тесты NLU процессора
├── test_models.py        # Тесты моделей БД
└── test_handlers.py      # Интеграционные тесты обработчиков
```

## Запуск тестов

### Установка зависимостей

```bash
pip install -r requirements-test.txt
```

### Команды

```bash
# Запустить все тесты
pytest

# Запустить с подробным выводом
pytest -v

# Запустить unit тесты
pytest -m unit

# Запустить integration тесты
pytest -m integration

# Запустить с отчётом о покрытии
pytest --cov=src --cov-report=term-missing

# Генерировать HTML отчёт
pytest --cov=src --cov-report=html
# Откроется в htmlcov/index.html
```

## Покрытие тестами

| Модуль | Тесты |
|--------|-------|
| `src/utils/` | ✅ extract_seats, validate_city_name, validate_seats |
| `src/config.py` | ✅ Все константы |
| `src/bot/handlers.py` | ✅ get_city_index, is_route_compatible, parse_date, fmt_date |
| `src/services/simple_parser.py` | ✅ Парсинг городов, дат, времени, мест |
| `src/services/nlu.py` | ✅ parse_intent, _normalize_date |
| `src/database/models.py` | ✅ User, Ride, Booking модели |
| `src/bot/handlers.py` | ✅ start, find_rides, list_rides, delete_ride |

## Фикстуры

Доступные фикстуры в `conftest.py`:

- `db_engine` — тестовый SQLite engine в памяти
- `db_session` — тестовая сессия БД
- `user` — тестовый пользователь
- `driver_ride` — тестовая поездка водителя
- `passenger_ride` — тестовая поездка пассажира
- `mock_bot` — мок бота
- `mock_message` — мок сообщения Telegram
- `mock_callback_query` — мок callback query
- `mock_state` — мок FSM state
- `route_order` — список маршрутов

## CI/CD

Тесты запускаются автоматически при:
- Push в ветки `main`, `develop`, `feature/*`
- Pull request в `main` или `develop`

GitHub Actions workflow: `.github/workflows/tests.yml`
