import asyncio
import logging
from aiogram import Bot, Dispatcher
from src.config import BOT_TOKEN
from src.handlers import router, auto_clean_old_rides
from src.database.session import init_models

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Запуск бота...")
    
    # Инициализация БД (создание таблиц)
    await init_models()
    logger.info("База данных инициализирована.")

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(router)

    # Запуск фоновой задачи очистки (без блокировки основного цикла)
    asyncio.create_task(auto_clean_old_rides())

    # Запуск поллинга (удаляем вебхуки на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
