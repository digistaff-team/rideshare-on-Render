"""
Константы проекта Ride Share Bot.
"""

# Очерёдность остановок на маршруте
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

# Популярные магазины для доставки
POPULAR_STORES = [
    "Пятёрочка"
]

# Интервалы и лимиты
CLEANUP_INTERVAL_SECONDS = 3600  # 1 час
CLEANUP_DAYS_BACK = 2  # Удалять поездки старше 2 дней
DELIVERY_CLEANUP_DAYS = 7  # Удалять завершённые доставки через 7 дней

MAX_RIDES_TO_FETCH = 20  # Максимум поездок для выборки из БД
MAX_RIDES_TO_DISPLAY = 10  # Максимум поездок для отображения

# Лимиты валидации
MAX_CITY_NAME_LENGTH = 100
MAX_USERNAME_LENGTH = 100
MAX_STORE_NAME_LENGTH = 100
MAX_REQUEST_TEXT_LENGTH = 1000
MIN_SEATS = 1
MAX_SEATS = 10
MIN_CAPACITY = 1
MAX_CAPACITY = 10

# Таймауты
API_TIMEOUT_SECONDS = 30
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 1800  # 30 минут

# Уровни логирования
LOG_LEVEL_DEFAULT = "INFO"
LOG_LEVEL_DEBUG = "DEBUG"

# Статусы доставки
DELIVERY_REQUEST_STATUSES = ["active", "matched", "confirmed", "completed", "cancelled"]
DELIVERY_OFFER_STATUSES = ["active", "full", "completed", "cancelled"]
DELIVERY_MATCH_STATUSES = ["pending", "confirmed", "rejected", "completed"]
