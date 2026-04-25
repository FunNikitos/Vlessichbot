"""Build the aiogram bot + dispatcher with full middleware chain."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings


def create_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # ----- Middlewares -----
    from app.bot.middlewares.db_session import DbSessionMiddleware
    from app.bot.middlewares.rate_limit import RateLimitMiddleware
    from app.bot.middlewares.antispam import AntispamMiddleware
    from app.bot.middlewares.auth import AuthMiddleware

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(AntispamMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # ----- Routers -----
    from app.bot.handlers import (
        connections,
        help as help_router,
        instructions,
        menu,
        start,
        status,
    )
    from app.bot.handlers.admin import (
        codes as admin_codes,
        errors as admin_errors,
        history as admin_history,
        honeypot as admin_honeypot,
        invites as admin_invites,
        panel as admin_panel,
        rotation as admin_rotation,
        stats as admin_stats,
        users as admin_users,
    )

    for r in (
        start.router,
        menu.router,
        connections.router,
        instructions.router,
        status.router,
        help_router.router,
        admin_panel.router,
        admin_codes.router,
        admin_invites.router,
        admin_users.router,
        admin_rotation.router,
        admin_stats.router,
        admin_history.router,
        admin_honeypot.router,
        admin_errors.router,
    ):
        dp.include_router(r)

    return dp
