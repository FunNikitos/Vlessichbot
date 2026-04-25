"""Brute-force protection for invite-code activation (counter persisted in DB)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class AntispamMiddleware(BaseMiddleware):
    """Pass-through stub. Реальная логика подсчёта попыток ввода кода
    реализуется в handlers/start.py через AuthAttempt-таблицу."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        return await handler(event, data)
