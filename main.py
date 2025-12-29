import asyncio
import logging
import os
import sys
from aiohttp import web  # Добавляем импорт веб-сервера
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты ваших модулей (убедитесь, что пути правильные)
from src.database.session import engine, init_models
from src.bot.handlers import router, auto_clean_old_rides

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- Функция "заглушка" для веб-сервера ---
async def health_check(request):
    """Просто отвечает 200 OK, чтобы Render знал, что бот жив."""
    return web.Response(text="Bot is running!")

# --- Запуск веб-сервера ---
async def start_web_server():
    # Создаем маленькое веб-приложение
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

# --- Основная функция ---
async def main():
    # 1. Инициализация базы данных (создание таблиц)
    # async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Раскомментировать, если нужно сбросить БД
        #await conn.run_sync(Base.metadata.create_all)
    await init_models()

    # 2. Настройка бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        return

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # 3. Запускаем веб-сервер (ВАЖНО: перед поллингом)
    await start_web_server()

    # 4. Фоновая задача очистки
    asyncio.create_task(auto_clean_old_rides())

    # 5. Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Bot started polling")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
