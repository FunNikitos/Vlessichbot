"""Admin /admin entry + main menu callbacks."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu
from app.bot.texts.admin import ADMIN_PANEL

router = Router(name="admin.panel")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def admin_cmd(msg: Message) -> None:
    await msg.answer(ADMIN_PANEL, reply_markup=admin_menu())


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(cb: CallbackQuery) -> None:
    await cb.message.edit_text(ADMIN_PANEL, reply_markup=admin_menu())
    await cb.answer()
