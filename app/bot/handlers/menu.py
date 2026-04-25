"""/menu — главное меню."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu
from app.bot.texts.messages import MAIN_MENU

router = Router(name="menu")


@router.message(Command("menu"))
async def menu_cmd(msg: Message) -> None:
    await msg.answer(MAIN_MENU, reply_markup=main_menu())


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery) -> None:
    await cb.message.edit_text(MAIN_MENU, reply_markup=main_menu())
    await cb.answer()
