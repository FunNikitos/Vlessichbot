"""Admin: deep-link invites."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.bot.texts.admin import INVITE_GENERATED
from app.services.invite_service import create_deep_link

router = Router(name="admin.invites")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("geninvite"))
async def gen_invite(msg: Message, command: CommandObject, session) -> None:
    """/geninvite <days>"""
    try:
        days = int((command.args or "30").split()[0])
    except ValueError:
        await msg.answer("Использование: /geninvite &lt;дней&gt;")
        return
    invite = await create_deep_link(session, created_by=msg.from_user.id, days=days)
    bot_user = await msg.bot.me()
    link = f"https://t.me/{bot_user.username}?start={invite.token}"
    await msg.answer(INVITE_GENERATED.format(link=link, days=days))


@router.callback_query(F.data == "adm:invites")
async def cb_invites(cb: CallbackQuery) -> None:
    await cb.message.edit_text(
        "Создать инвайт-ссылку: /geninvite &lt;дней&gt;", reply_markup=admin_menu()
    )
    await cb.answer()
