# 🚗 Ride Share Bot

Telegram-бот для организации совместных поездок между населенными пунктами Краснодарского края.

## 📋 Описание

**Ride Share Bot** — это умный помощник, который соединяет водителей и пассажиров, путешествующих по одному маршруту. Бот использует искусственный интеллект для распознавания естественного языка и автоматического создания заявок на поездку.

### Основные возможности

- 🙋 **Поиск водителя** — пассажиры могут быстро найти попутку
- 🚗 **Поиск пассажиров** — водители могут заполнить свободные места в машине
- 🤖 **AI-помощник** — распознавание маршрута из обычного сообщения (NLU на базе Pro-Talk API)
- 🔄 **Автоматическое匹配** — умное сопоставление маршрутов водителей и пассажиров
- 📅 **Актуальные поездки** — автоматическая очистка старых объявлений
- 🔔 **Уведомления** — мгновенные уведомления о найденных попутчиках
- ✅ **Покрыто тестами** — unit и integration тесты критической логики

## 🗺️ Маршрут

Бот работает на фиксированном маршруте со следующими остановками:

1. Сказочный край
2. Живой дом
3. Здравое
4. Григорьевская
5. Смоленская
6. Афипский
7. Энем
8. Яблоновский
9. Краснодар

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- PostgreSQL (для продакшена) или SQLite (для разработки)
- Токен Telegram-бота (получить у [@BotFather](https://t.me/BotFather))

### Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repository-url>
   cd Ride_Share_Bot
   ```

2. **Создайте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   .venv\Scripts\activate    # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте окружение:**
   
   Скопируйте `.env.example` в `.env` и заполните:
   ```env
   # Telegram Bot
   BOT_TOKEN=your_bot_token_here
   
   # Database
   DATABASE_URL=sqlite+aiosqlite:///./test_bot.db
   
   # Pro-Talk API (для AI-функций)
   PROTALK_BOT_ID=your_bot_id
   PROTALK_TOKEN=your_api_token
   PROTALK_API_URL=https://api.pro-talk.ru/api/v1.0
   
   # Server
   PORT=8000
   LOG_LEVEL=INFO
   ```

5. **Запустите бота:**
   ```bash
   python main.py
   ```

## 🐳 Docker

### Запуск с Docker Compose

```bash
docker-compose up -d
```

### Сборка образа

```bash
docker build -t rideshare-bot .
```

## 📱 Использование

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Запуск бота, главное меню |
| `/all_rides` | Показать все доступные поездки |
| `/my_rides` | Мои поездки (просмотр и удаление) |

### Кнопки меню

- **🙋 Подвези** — создать заявку пассажира
- **🚗 Подвезу** — создать заявку водителя
- **🔍 Найти поездку** — поиск доступных поездок
- **📋 Мои поездки** — управление своими заявками

### Примеры использования

**Для пассажира:**
```
Пользователь: 🙋 Подвези
Бот: Напишите о желаемой поездке, например: 
     "Из Краснодара в Сказочный сегодня в 18:00, одно место"

Пользователь: Из Здравого в Краснодар завтра в 10 утра, нужно 2 места
Бот: ✅ Поездка сохранена!
```

**Для водителя:**
```
Пользователь: 🚗 Подвезу
Бот: Напишите маршрут, дату и время вашей поездки

Пользователь: Из Сказочного края в Краснодар завтра в 9 утра, есть 3 места
Бот: ✅ Поездка сохранена!
     🔔 Найден попутчик! [уведомление о匹配]
```

## 🏗️ Архитектура

```
Ride_Share_Bot/
├── main.py              # Точка входа, веб-сервер + polling
├── requirements.txt     # Зависимости Python
├── docker-compose.yml   # Docker Compose конфигурация
├── Dockerfile           # Docker образ
├── rideshare.service    # systemd сервис
├── .env                 # Переменные окружения
└── src/
    ├── bot/
    │   └── handlers.py  # Обработчики команд Telegram
    ├── database/
    │   ├── models.py    # SQLAlchemy модели
    │   └── session.py   # Асинхронная сессия БД
    └── services/
        ├── nlu.py       # Интеграция с Pro-Talk API
        └── simple_parser.py  # Резервный парсер
```

## 💾 База данных

### Таблицы

**users** — пользователи
- `telegram_id` — уникальный ID Telegram
- `username` — имя пользователя

**rides** — поездки
- `user_id` — ссылку на пользователя
- `role` — "driver" или "passenger"
- `origin` / `destination` — маршрут
- `date` / `start_time` — дата и время
- `seats` — количество мест

**bookings** — бронирования
- `driver_ride_id` / `passenger_ride_id` — связанные поездки
- `status` — "pending", "confirmed", "rejected"

## 🔧 Продакшен-развертывание

### systemd сервис

1. **Скопируйте сервис:**
   ```bash
   sudo cp rideshare.service /etc/systemd/system/
   ```

2. **Отредактируйте пути в файле сервиса**

3. **Запустите:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rideshare
   sudo systemctl start rideshare
   sudo systemctl status rideshare
   ```

## 📊 Технологии

| Технология | Назначение |
|------------|------------|
| Python 3.11+ | Язык программирования |
| aiogram 3.x | Telegram Bot Framework |
| SQLAlchemy 2.x | ORM для работы с БД |
| PostgreSQL / SQLite | База данных |
| Redis | Хранилище FSM состояний |
| aiohttp | Асинхронный HTTP-клиент |
| Pro-Talk API | NLU для распознавания языка |
| Docker | Контейнеризация |
| pytest | Фреймворк для тестирования |

## 🧪 Тестирование

Проект покрыт unit и integration тестами.

### Запуск тестов

```bash
# Установка зависимостей
pip install -r requirements-test.txt

# Запустить все тесты
pytest

# Запустить с отчётом о покрытии
pytest --cov=src --cov-report=term-missing

# Запустить конкретный файл
pytest tests/test_utils.py -v
```

Подробная документация по тестам: [tests/README.md](tests/README.md)

## ⚙️ Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| `BOT_TOKEN` | Токен Telegram-бота | ✅ |
| `DATABASE_URL` | Строка подключения к БД | ✅ |
| `REDIS_URL` | URL Redis для FSM | Для продакшена |
| `PROTALK_TOKEN` | Токен Pro-Talk API | Для AI |
| `PROTALK_BOT_ID` | ID бота в Pro-Talk | Для AI |
| `PORT` | Порт веб-сервера | ❌ (8000) |
| `LOG_LEVEL` | Уровень логирования | ❌ (INFO) |

## 📝 Лицензия

MIT

## 👥 Контакты

https://t.me/DigiStaff
