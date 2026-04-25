"""Access guard. /start, /help, /menu, /activate доступны всем; остальное —
только тем, у кого active access."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from app.config import settings
from app.db.models import User

PUBLIC_COMMANDS = {"/start", "/help", "/menu", "/activate"}


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)
        if user.id == settings.owner_id:
            return await handler(event, data)

        text = ""
        if isinstance(event, Message) and event.text:
            text = event.text
        elif isinstance(event, CallbackQuery) and event.data:
            text = event.data

        # Public-команды и стартовые callback'и пропускаем сразу.
        if text.startswith("/"):
            cmd = text.split()[0].split("@")[0]
            if cmd in PUBLIC_COMMANDS:
                return await handler(event, data)
        if text.startswith("auth:") or text.startswith("activate:"):
            return await handler(event, data)

        session = data["session"]
        result = await session.execute(select(User).where(User.telegram_id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user is None or db_user.status != "active":
            await _deny(event, "У тебя нет активного доступа. Введи код через /activate.")
            return None
        if db_user.access_expires_at and db_user.access_expires_at < datetime.now(timezone.utc):
            await _deny(event, "⏳ Срок твоего доступа истёк. Обратись к администратору.")
            return None

        data["db_user"] = db_user
        return await handler(event, data)


async def _deny(event: TelegramObject, text: str) -> None:
    if isinstance(event, Message):
        await event.answer(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
