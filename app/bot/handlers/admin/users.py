"""Admin: users list (read-only stub for step 1)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.db.models import User

router = Router(name="admin.users")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:users")
async def cb_users(cb: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(20)
    )
    rows = list(result.scalars().all())
    if not rows:
        text = "Пользователей пока нет."
    else:
        lines = ["<b>Последние 20 пользователей</b>"]
        for u in rows:
            uname = f"@{u.username}" if u.username else u.first_name or "—"
            lines.append(f"• {u.telegram_id} {uname} [{u.status}]")
        text = "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()
