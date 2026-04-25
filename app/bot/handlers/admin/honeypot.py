"""Admin: honeypot hits log."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.db.models import HoneypotHit

router = Router(name="admin.honeypot")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:honeypot")
async def cb_honeypot(cb: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(HoneypotHit).order_by(HoneypotHit.hit_at.desc()).limit(20)
    )
    rows = list(result.scalars().all())
    if not rows:
        text = "👁 Honeypot пока никого не словил."
    else:
        lines = ["<b>👁 Honeypot — последние удары</b>"]
        for h in rows:
            ts = h.hit_at.strftime("%Y-%m-%d %H:%M")
            country = f" [{h.country}]" if h.country else ""
            blocked = "🚫" if h.blocked else "·"
            lines.append(f"{blocked} {ts}  {h.ip}{country}  :{h.port}")
        text = "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()
