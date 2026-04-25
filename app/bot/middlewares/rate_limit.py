"""Sliding-window rate-limit per user via Redis."""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.redis import get_redis


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = _extract_user_id(event)
        if user_id is None or user_id == settings.owner_id:
            return await handler(event, data)

        redis = get_redis()
        key = f"rl:{user_id}"
        now = time.time()
        window = settings.rate_limit_window_sec
        await redis.zremrangebyscore(key, 0, now - window)
        count = await redis.zcard(key)
        if count >= settings.rate_limit_max:
            if isinstance(event, Message):
                await event.answer("⏳ Слишком быстро. Подожди пару секунд.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Слишком быстро", show_alert=False)
            return None
        await redis.zadd(key, {str(now): now})
        await redis.expire(key, window)
        return await handler(event, data)


def _extract_user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    return user.id if user else None
