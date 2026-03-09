import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy import select

# Импорты ваших модулей (убедитесь, что пути правильные)
from src.database.session import engine, init_models, async_session
from src.bot.handlers import router, auto_clean_old_rides

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- Глобальные переменные для graceful shutdown ---
background_tasks = set()
shutdown_event = asyncio.Event()

# --- Функция "заглушка" для веб-сервера ---
async def health_check(request):
    """Проверяет работоспособность бота и подключение к БД."""
    try:
        async with async_session() as session:
            await session.execute(select(1))
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return web.Response(text="DB Error", status=503)

# --- Запуск веб-сервера ---
async def start_web_server():
    # Создаем маленькое веб-приложение
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)

    # Получаем порт из окружения Render (или 8000 по умолчанию)
    port = int(os.environ.get("PORT", 8000))

    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🕸 Web server started on port {port}")
    return runner

# --- Основная функция ---
async def main():
    # 1. Инициализация базы данных (создание таблиц)
    await init_models()

    # 2. Настройка бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        return

    bot = Bot(token=bot_token)
    
    # 3. Настраиваем хранилище FSM (Redis или Memory)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # Для продакшена используем Redis
        storage = RedisStorage.from_url(redis_url)
        logger.info(f"💾 Using Redis storage for FSM states")
    else:
        # Для локальной разработки
        storage = MemoryStorage()
        logger.info("💾 Using Memory storage for FSM states (development)")
    
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # 4. Запускаем веб-сервер
    runner = await start_web_server()

    # 5. Создаём фоновую задачу очистки
    cleanup_task = asyncio.create_task(auto_clean_old_rides())
    background_tasks.add(cleanup_task)
    cleanup_task.add_done_callback(background_tasks.discard)

    # 6. Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Bot started polling")

    try:
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping bot...")
    finally:
        # Graceful shutdown
        logger.info("Cleaning up resources...")

        # Останавливаем фоновые задачи
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Закрываем сессию бота
        await bot.session.close()

        # Освобождаем ресурсы БД
        await engine.dispose()

        # Останавливаем веб-сервер
        await runner.cleanup()

        # Закрываем Redis connection
        await storage.close()

        logger.info("Bot stopped gracefully")

if __name__ == "__main__":
    asyncio.run(main())
