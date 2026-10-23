import re
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.enums import ChatAction

from services.downloader import download_media
from services.subscription import check_user_subscription, build_subscription_keyboard
from config import MAX_FILE_SIZE_BYTES
from database import db

router = Router()

# URL qidirish uchun regex
URL_REGEX = re.compile(r'https?://[^\s]+')


def get_formatted_caption(media_title: str) -> str:
    """Yuklangan fayl ostiga chiqadigan matnni (caption) shakllantirish"""
    custom_caption = db.get_setting("custom_caption")

    if custom_caption:
        if media_title:
            caption = f"🎬 <b>{media_title[:70]}</b>\n\n{custom_caption}"
        else:
            caption = custom_caption
    else:
        caption = f"🎬 {media_title[:100]}" if media_title else "✅ Muvaffaqiyatli yuklandi!"

    # Telegram caption cheklovi maksimal 1024 belgi
    return caption[:1024]


@router.message(F.text)
async def handle_url(message: Message, bot: Bot):
    text = message.text.strip()
    user = message.from_user

    # Foydalanuvchini ro'yxatga olish / yangilash
    db.add_user(user_id=user.id, full_name=user.full_name, username=user.username)

    # Link mavjudligini aniqlash
    urls = URL_REGEX.findall(text)
    if not urls:
        # Agar admin buyrug'i bo'lsa yoki shunchaki matn bo'lsa
        if text.startswith("/"):
            return
        await message.reply(
            "Iltimos, yuklab olish uchun to'g'ri havola (link) yuboring.\n"
            "Masalan: TikTok, Instagram, Pinterest yoki YouTube havolasi."
        )
        return

    # 1. Majburiy obunani tekshirish (video yuklashdan oldin)
    is_subscribed, unsubscribed = await check_user_subscription(bot, user.id)
    if not is_subscribed:
        kb = build_subscription_keyboard(unsubscribed)
        await message.reply(
            "⚠️ <b>Video yuklash uchun quyidagi kanallarga a'zo bo'ling (yoki zayavka yuboring):</b>\n\n"
            "Barcha kanallarga a'zo bo'lgach, <b>«✅ Obunani tekshirish»</b> tugmasini bosing.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    target_url = urls[0]

    # "Yuklanmoqda..." xabari
    status_msg = await message.reply("⏳ Yuklanmoqda, iltimos kuting...")

    try:
        # Harakat indikatori
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_DOCUMENT)

        result = await download_media(target_url)

        try:
            files = result.files
            if not files:
                await status_msg.edit_text("❌ Hech qanday media fayl topilmadi.")
                return

            # Fayl hajmini tekshirish (Telegram Bot API 50MB limiti)
            oversized_files = [f for f in files if f.stat().st_size > MAX_FILE_SIZE_BYTES]
            if oversized_files:
                await status_msg.edit_text(
                    "❌ Kechirasiz, fayl hajmi 50MB dan katta bo'lgani sababli uni Telegram orqali yuborib bo'lmaydi."
                )
                return

            # Admin sozlagan matnni (caption) olish
            caption = get_formatted_caption(result.title)

            # Agar faqat bitta fayl bo'lsa
            if len(files) == 1:
                file_path = files[0]
                ext = file_path.suffix.lower()

                if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)
                    await message.reply_video(
                        video=FSInputFile(file_path),
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
                    await message.reply_photo(
                        photo=FSInputFile(file_path),
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif ext in ['.mp3', '.m4a', '.ogg', '.wav']:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE)
                    await message.reply_audio(
                        audio=FSInputFile(file_path),
                        caption=caption,
                        parse_mode="HTML"
                    )
                else:
                    await message.reply_document(
                        document=FSInputFile(file_path),
                        caption=caption,
                        parse_mode="HTML"
                    )

            # Agar bir nechta fayl (karusel / foto-albom) bo'lsa (10 talik guruhlarga bo'lib yuboriladi)
            else:
                chunk_size = 10
                for chunk_idx in range(0, len(files), chunk_size):
                    chunk_files = files[chunk_idx:chunk_idx + chunk_size]
                    media_group = []

                    for idx, file_path in enumerate(chunk_files):
                        ext = file_path.suffix.lower()
                        file_cap = caption if (chunk_idx == 0 and idx == 0) else None

                        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                            media_group.append(InputMediaVideo(media=FSInputFile(file_path), caption=file_cap, parse_mode="HTML"))
                        else:
                            media_group.append(InputMediaPhoto(media=FSInputFile(file_path), caption=file_cap, parse_mode="HTML"))

                    if media_group:
                        await message.reply_media_group(media=media_group)

            # Status xabarini o'chirish
            await status_msg.delete()

        finally:
            # Fayllarni diskdan tozalash
            result.cleanup()

    except Exception as e:
        err_text = str(e)
        if "Private video" in err_text or "login" in err_text.lower():
            msg = "❌ Ushbu video yopiq (profil yoki video maxfiy) bo'lgani uchun uni yuklab bo'lmadi."
        elif "max-filesize" in err_text.lower() or "too large" in err_text.lower():
            msg = "❌ Fayl hajmi 50MB dan katta bo'lgani sababli yuklab olinmadi."
        else:
            msg = "❌ Yuklab olishda xatolik yuz berdi. Havola to'g'riligini yoki video o'chirilmaganligini tekshiring."

        try:
            await status_msg.edit_text(msg)
        except Exception:
            await message.reply(msg)
