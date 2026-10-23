from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from database import db


class UserTrackerMiddleware(BaseMiddleware):
    """
    Botga kelgan har qanday harakat (xabar, tugma bosish, zayavka) orqali
    foydalanuvchini bazaga 100% avtomatik ro'yxatga oluvchi middleware.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        event_user: User = data.get("event_from_user")

        if event_user and not event_user.is_bot:
            try:
                db.add_user(
                    user_id=event_user.id,
                    full_name=event_user.full_name or "Foydalanuvchi",
                    username=event_user.username
                )
            except Exception:
                pass

        return await handler(event, data)
