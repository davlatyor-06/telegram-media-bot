from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from database import db
from services.subscription import check_user_subscription, build_subscription_keyboard

router = Router()

START_TEXT = """
👋 <b>Assalomu alaykum!</b>

Men ijtimoiy tarmoqlardan video va rasmlarni yuklab beruvchi botman.

📥 <b>Qo'llab-quvvatlanadigan platformalar:</b>
• 🎵 <b>TikTok</b> — Suv belgisiz videolar va foto-slaydlar
• 📸 <b>Instagram</b> — Reels, postlar, rasmlar va karusellar
• 📌 <b>Pinterest</b> — Rasmlar va videolar
• ▶️ <b>YouTube</b> — Shorts va qisqa videolar

🚀 <b>Foydalanish juda oson:</b>
Menga shunchaki video yoki rasm havolasini (linkini) yuboring!
"""

HELP_TEXT = """
ℹ️ <b>Qanday ishlatiladi?</b>

1. Instagram, TikTok, Pinterest yoki YouTube ilovasidan havolani nusxalang.
2. Botga yuboring.
3. Bot avtomatik ravishda yuklab oladi va sizga yuboradi!

⚠️ <b>Eslatma:</b>
Telegram Bot API cheklovi sababli bitta fayl hajmi maksimal 50 MB bo'lishi mumkin.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    # Foydalanuvchini bazaga qo'shish
    user = message.from_user
    db.add_user(user_id=user.id, full_name=user.full_name, username=user.username)

    # Majburiy obunani tekshirish
    is_subscribed, unsubscribed = await check_user_subscription(bot, user.id)
    if not is_subscribed:
        kb = build_subscription_keyboard(unsubscribed)
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling (yoki zayavka yuboring):</b>\n\n"
            "Barcha kanallarga a'zo bo'lgach, <b>«✅ Obunani tekshirish»</b> tugmasini bosing.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    await message.answer(START_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    is_subscribed, unsubscribed = await check_user_subscription(bot, user_id)
    if is_subscribed:
        await callback.answer("✅ Rahmat! Obuna tasdiqlandi.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(START_TEXT, parse_mode="HTML")
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz yoki zayavka yubormadingiz!", show_alert=True)
        kb = build_subscription_keyboard(unsubscribed)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
