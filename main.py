import asyncio
import logging
import os
import sys
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.database.session import engine, init_models, Base  # ← Добавь Base!
from src.bot.handlers import router, auto_clean_old_rides

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def healthcheck(request):
    """Health check endpoint for Render"""
    return web.Response(text="Bot is running!")


async def start_webserver():
    """Start web server for health checks"""
    app = web.Application()
    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)
    
    port = int(os.environ.get("PORT", 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🕸 Web server started on port {port}")


async def main():
    # ВРЕМЕННО: Пересоздать таблицы (закомментите # в начале строки после деплоя!)
    # async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        # await conn.run_sync(Base.metadata.create_all)

    await init_models()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        return
    
    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await start_webserver()
    asyncio.create_task(auto_clean_old_rides())
    
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
