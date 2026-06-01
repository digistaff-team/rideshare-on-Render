import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Принудительно UTF-8 для вывода логов (Windows CP1251 не поддерживает emoji)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Redis storage (опционально)
try:
    from aiogram.fsm.storage.redis import RedisStorage
    REDIS_AVAILABLE = True
except ImportError:
    RedisStorage = None
    REDIS_AVAILABLE = False

from sqlalchemy import select

# Импорты ваших модулей (убедитесь, что пути правильные)
from src.database.session import engine, init_models
from src.bot.handlers import router, auto_clean_old_rides

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- Глобальные переменные для graceful shutdown ---
background_tasks = set()
shutdown_event = asyncio.Event()

# --- Функция "заглушка" для веб-сервера ---
async def health_check(request):
    """Просто отвечает 200 OK, чтобы Render знал, что бот жив."""
    return web.Response(text="Bot is running!")


async def start_webserver():
    """Start web server for health checks"""
    app = web.Application()
    app.router.add_get('/', health_check)  # На главной странице будет текст
    app.router.add_get('/health', health_check) # И на /health тоже

    # Получаем порт из окружения Render (или 8000 по умолчанию)
    port = int(os.environ.get("PORT", 8000))

    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🕸 Web server started on port {port}")
    return runner


async def main():
    # 1. Инициализация базы данных (создание таблиц)
    # async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Раскомментировать, если нужно сбросить БД
        #await conn.run_sync(Base.metadata.create_all)
    await init_models()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        return
    
    bot = Bot(token=bot_token)
    
    # 3. Настраиваем хранилище FSM (Redis или Memory)
    redis_url = os.getenv("REDIS_URL")
    if redis_url and REDIS_AVAILABLE:
        # Для продакшена используем Redis
        storage = RedisStorage.from_url(redis_url)
        logger.info(f"💾 Using Redis storage for FSM states")
    else:
        # Для локальной разработки
        storage = MemoryStorage()
        if not REDIS_AVAILABLE:
            logger.info("💾 Redis package not installed, using Memory storage")
        else:
            logger.info("💾 Using Memory storage for FSM states (development)")
    
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # 4. Запускаем веб-сервер
    runner = await start_webserver()

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

if __name__ == "__main__":
    asyncio.run(main())
