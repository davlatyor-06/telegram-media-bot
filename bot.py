import asyncio
import logging
import os
import sys
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ChatJoinRequest

from config import BOT_TOKEN
from database import db
from middlewares.user_tracker import UserTrackerMiddleware
from handlers.start import router as start_router
from handlers.downloader import router as download_router
from handlers.admin import router as admin_router

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def start_health_check_server():
    """Render.com va shunga o'xshash xizmatlar uchun portni tinglab turuvchi server"""
    port = int(os.getenv("PORT", "8080"))

    async def handle_ping(request):
        return web.Response(text="Bot muvaffaqiyatli ishlamoqda!")

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server port {port} da ishga tushdi.")


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "\n" + "=" * 60 + "\n"
            "XATOLIK: BOT_TOKEN ko'rsatilmagan!\n"
            "Iltimos, .env faylini oching va bot tokeningizni kiriting.\n"
            + "=" * 60
        )
        sys.exit(1)

    # Render.com port tekshiruvi uchun web serverni parallel yoqish
    try:
        await start_health_check_server()
    except Exception as e:
        logger.warning(f"Health check server ishga tushmadi (oddiy serverda bu muammo emas): {e}")

    # Bot va Dispatcher obyektlari
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Har qanday xabar yoki tugma bosilganda foydalanuvchini 100% bazaga yozib olish (Middleware)
    dp.message.outer_middleware(UserTrackerMiddleware())
    dp.callback_query.outer_middleware(UserTrackerMiddleware())

    # Zayavka (Join Request) hodisasini ushlash
    @dp.chat_join_request()
    async def join_request_handler(update: ChatJoinRequest):
        try:
            user = update.from_user
            chat_id = str(update.chat.id)
            db.add_user(user_id=user.id, full_name=user.full_name or "", username=user.username)
            db.record_join_request(user_id=user.id, chat_id=chat_id)
            logger.info(f"Yangi zayavka qabul qilindi: User {user.id} -> Chat {chat_id}")
        except Exception as e:
            logger.error(f"Zayavka qayd etishda xatolik: {e}")

    # Routerlarni ulash
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(download_router)

    # Bot ma'lumotlarini olish
    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username}")
    print(f"\n>>> Bot ishga tushdi! Telegramda @{bot_info.username} manziliga o'tib /start buyrug'ini bering.\n")

    try:
        # Pollingni boshlash
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_join_request"]
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
