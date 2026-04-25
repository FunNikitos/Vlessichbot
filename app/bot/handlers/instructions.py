"""Per-platform Hiddify install instructions."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards.user import back_to_menu, platforms
from app.bot.texts.instructions import HIDDIFY_INSTRUCTIONS

router = Router(name="instructions")


@router.callback_query(F.data == "instructions")
async def cb_instructions(cb: CallbackQuery) -> None:
    await cb.message.edit_text("Выбери платформу:", reply_markup=platforms())
    await cb.answer()


@router.callback_query(F.data.startswith("instr:"))
async def cb_platform(cb: CallbackQuery) -> None:
    platform = cb.data.split(":")[1]
    text = HIDDIFY_INSTRUCTIONS.get(platform, "Инструкция для платформы не найдена.")
    await cb.message.edit_text(text, reply_markup=back_to_menu(), disable_web_page_preview=True)
    await cb.answer()
