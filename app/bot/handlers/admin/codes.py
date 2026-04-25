"""Admin: invite codes (create / list)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.bot.texts.admin import CODE_GENERATED
from app.db.models import InviteCode
from app.services.invite_service import create_invite_code

router = Router(name="admin.codes")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("gencode"))
async def gen_code(msg: Message, command: CommandObject, session: AsyncSession) -> None:
    """/gencode <days> [max_uses]"""
    args = (command.args or "").split()
    if not args:
        await msg.answer("Использование: /gencode &lt;дней&gt; [max_uses]")
        return
    try:
        days = int(args[0])
        max_uses = int(args[1]) if len(args) > 1 else 1
    except ValueError:
        await msg.answer("Неверные аргументы.")
        return
    invite = await create_invite_code(
        session, created_by=msg.from_user.id, days=days, max_uses=max_uses
    )
    await msg.answer(
        CODE_GENERATED.format(code=invite.code, days=days, max_uses=max_uses)
    )


@router.callback_query(F.data == "adm:codes")
async def cb_codes(cb: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(InviteCode).order_by(InviteCode.created_at.desc()).limit(10)
    )
    rows = list(result.scalars().all())
    if not rows:
        text = "Активных кодов нет.\nСоздай: /gencode &lt;дней&gt; [max_uses]"
    else:
        lines = ["<b>Последние коды</b>"]
        for c in rows:
            lines.append(
                f"<code>{c.code}</code> — {c.access_duration_days}д, "
                f"{c.used_count}/{c.max_uses}, {c.status}"
            )
        text = "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()
