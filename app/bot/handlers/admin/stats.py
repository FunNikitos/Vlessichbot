"""Admin: aggregated stats."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.db.models import Connection, InviteCode, User

router = Router(name="admin.stats")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:stats")
async def cb_stats(cb: CallbackQuery, session: AsyncSession) -> None:
    users_total = await session.scalar(select(func.count(User.id)))
    users_active = await session.scalar(
        select(func.count(User.id)).where(User.status == "active")
    )
    conns_total = await session.scalar(select(func.count(Connection.id)))
    codes_active = await session.scalar(
        select(func.count(InviteCode.id)).where(InviteCode.status == "active")
    )
    text = (
        "<b>📊 Статистика</b>\n"
        f"Пользователей: {users_total} (активных: {users_active})\n"
        f"Конфигов: {conns_total}\n"
        f"Активных кодов: {codes_active}"
    )
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()
