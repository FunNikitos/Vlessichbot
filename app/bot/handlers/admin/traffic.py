"""Admin & user: traffic accounting (Marzban counters).

Commands:
- ``/traffic``           (admin) — system summary + top-10 consumers.
- ``/traffic <tg_id>``   (admin) — per-user card by Telegram ID.
- ``/mytraffic``         (any user) — own usage card.
- callback ``adm:traffic`` — same as ``/traffic`` from admin menu.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.services.traffic import (
    format_system_summary,
    format_top_users,
    format_user_card,
    get_system_summary,
    get_user_traffic,
    list_top_users,
    resolve_marzban_username,
)
from app.services.user_service import get_or_create_user

router = Router(name="traffic")


# ---------- Admin ----------


admin_router = Router(name="admin.traffic")
admin_router.message.filter(IsAdmin())
admin_router.callback_query.filter(IsAdmin())


@admin_router.message(Command("traffic"))
async def cmd_traffic_admin(
    msg: Message, command: CommandObject, session: AsyncSession
) -> None:
    arg = (command.args or "").strip()
    if arg:
        # /traffic <tg_id>
        try:
            tg_id = int(arg)
        except ValueError:
            await msg.answer("Использование: <code>/traffic [telegram_id]</code>")
            return
        username = await resolve_marzban_username(session, tg_id)
        if not username:
            await msg.answer("Этот пользователь не зарегистрирован в Marzban.")
            return
        payload = await get_user_traffic(username)
        if not payload:
            await msg.answer("Marzban-юзер не найден или API недоступен.")
            return
        await msg.answer(format_user_card(payload))
        return

    stats = await get_system_summary()
    top = await list_top_users(limit=10)
    await msg.answer(
        f"{format_system_summary(stats)}\n{format_top_users(top)}",
        reply_markup=admin_menu(),
    )


@admin_router.callback_query(F.data == "adm:traffic")
async def cb_traffic(cb: CallbackQuery) -> None:
    stats = await get_system_summary()
    top = await list_top_users(limit=10)
    await cb.message.edit_text(
        f"{format_system_summary(stats)}\n{format_top_users(top)}",
        reply_markup=admin_menu(),
    )
    await cb.answer()


# ---------- User ----------


@router.message(Command("mytraffic"))
async def cmd_mytraffic(msg: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, msg.from_user)
    if not user.marzban_username:
        await msg.answer("У тебя пока нет активного конфига. /newconfig — создать.")
        return
    payload = await get_user_traffic(user.marzban_username)
    if not payload:
        await msg.answer("Не удалось получить статистику. Попробуй позже.")
        return
    await msg.answer(format_user_card(payload))
