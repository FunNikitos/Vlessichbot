"""/help — справка."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.texts.messages import HELP

router = Router(name="help")


@router.message(Command("help"))
async def help_cmd(msg: Message) -> None:
    await msg.answer(HELP)
