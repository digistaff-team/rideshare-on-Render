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

# Интервалы и лимиты
CLEANUP_INTERVAL_SECONDS = 3600  # 1 час
CLEANUP_DAYS_BACK = 2  # Удалять поездки старше 2 дней

MAX_RIDES_TO_FETCH = 20  # Максимум поездок для выборки из БД
MAX_RIDES_TO_DISPLAY = 10  # Максимум поездок для отображения

# Лимиты валидации
MAX_CITY_NAME_LENGTH = 100
MAX_USERNAME_LENGTH = 100
MIN_SEATS = 1
MAX_SEATS = 10

# Таймауты
API_TIMEOUT_SECONDS = 30
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 1800  # 30 минут

# Уровни логирования
LOG_LEVEL_DEFAULT = "INFO"
LOG_LEVEL_DEBUG = "DEBUG"
