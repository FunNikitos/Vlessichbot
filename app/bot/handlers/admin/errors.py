"""Admin: error log + /errors command."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.db.models import ErrorLog

router = Router(name="admin.errors")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def _render(session: AsyncSession) -> str:
    result = await session.execute(
        select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(15)
    )
    rows = list(result.scalars().all())
    if not rows:
        return "🐞 Ошибок не зафиксировано."
    lines = ["<b>🐞 Последние ошибки</b>"]
    for e in rows:
        ts = e.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{e.level}] {ts} {e.source}: {e.message[:120]}")
    return "\n".join(lines)


@router.message(Command("errors"))
async def errors_cmd(msg: Message, session: AsyncSession) -> None:
    await msg.answer(await _render(session))


@router.callback_query(F.data == "adm:errors")
async def cb_errors(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.message.edit_text(await _render(session), reply_markup=admin_menu())
    await cb.answer()
