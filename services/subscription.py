import logging
from typing import Tuple, List, Dict, Any
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import db

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = [
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED
]


async def check_user_subscription(bot: Bot, user_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Foydalanuvchining barcha majburiy kanallarga obuna bo'lganligini tekshiradi.
    (all_subscribed, unsubscribed_channels) qaytaradi.
    """
    channels = db.get_channels()
    if not channels:
        return True, []

    unsubscribed = []

    for ch in channels:
        chat_id = ch['chat_id']
        is_request = bool(ch['is_request'])

        # Agar bu zayavka (join request) kanal bo'lsa:
        if is_request:
            # 1. Foydalanuvchi allaqachon zayavka tashlaganmi?
            if db.has_join_request(user_id, chat_id):
                continue

            # 2. Yoki balki allaqachon a'zo bo'lgandir?
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status in ALLOWED_STATUSES:
                    continue
            except Exception as e:
                logger.debug(f"Zayavka kanal tekshirishda xatolik {chat_id}: {e}")

            # Hech biri bo'lmasa - zayavka talab etiladi
            unsubscribed.append(ch)

        # Agar oddiy kanal bo'lsa:
        else:
            try:
                member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status not in ALLOWED_STATUSES:
                    unsubscribed.append(ch)
            except Exception as e:
                logger.warning(f"Kanal obunasini tekshirib bo'lmadi ({chat_id}): {e}")
                # Agar bot kanalda admin bo'lmasa yoki xato bersa ham kanal talab etiladi
                unsubscribed.append(ch)

    return len(unsubscribed) == 0, unsubscribed


def build_subscription_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Obuna bo'lish tugmalari va tekshirish tugmasini yaratadi"""
    inline_keyboard = []

    for idx, ch in enumerate(channels, 1):
        btn_text = f"📢 {ch['title']}"
        if ch.get('is_request'):
            btn_text += " (Zayavka)"
        inline_keyboard.append([
            InlineKeyboardButton(text=btn_text, url=ch['url'])
        ])

    inline_keyboard.append([
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
