"""Admin: block-events history."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.db.models import BlockEvent

router = Router(name="admin.history")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:history")
async def cb_history(cb: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(BlockEvent).order_by(BlockEvent.detected_at.desc()).limit(15)
    )
    rows = list(result.scalars().all())
    if not rows:
        text = "История блокировок пуста."
    else:
        lines = ["<b>📜 История блокировок</b>"]
        for ev in rows:
            ts = ev.detected_at.strftime("%Y-%m-%d %H:%M")
            resolved = ev.resolved_at.strftime("%H:%M") if ev.resolved_at else "—"
            lines.append(f"{ts}  {ev.protocol}  resolved:{resolved}  {ev.action or ''}")
        text = "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()
