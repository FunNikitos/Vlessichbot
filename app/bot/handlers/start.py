"""/start + deep-link invites + /activate (FSM for invite-code input)."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.user import main_menu
from app.bot.texts.messages import (
    ACCESS_GRANTED,
    CODE_BAD,
    CODE_PROMPT,
    INVITE_BAD,
    WELCOME,
)
from app.config import settings
from app.services.invite_service import use_deep_link_invite
from app.services.user_service import activate_with_code, get_or_create_user

log = logging.getLogger(__name__)
router = Router(name="start")


class ActivateFlow(StatesGroup):
    waiting_code = State()


@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(
    msg: Message, command: CommandObject, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    user = await get_or_create_user(session, msg.from_user)
    token = (command.args or "").strip()
    if token.startswith("inv_"):
        ok = await use_deep_link_invite(session, token, user)
        if not ok:
            await msg.answer(INVITE_BAD)
            return
        await msg.answer(ACCESS_GRANTED, reply_markup=main_menu())
        return
    await msg.answer(WELCOME, reply_markup=main_menu() if user.status == "active" else None)


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await get_or_create_user(session, msg.from_user)
    if user.telegram_id == settings.owner_id and user.status != "active":
        user.status = "active"
        await session.commit()
    await msg.answer(WELCOME, reply_markup=main_menu() if user.status == "active" else None)


@router.message(Command("activate"))
async def activate_cmd(msg: Message, state: FSMContext) -> None:
    await state.set_state(ActivateFlow.waiting_code)
    await msg.answer(CODE_PROMPT)


@router.message(ActivateFlow.waiting_code)
async def activate_code_input(msg: Message, state: FSMContext, session: AsyncSession) -> None:
    code = (msg.text or "").strip()
    user = await get_or_create_user(session, msg.from_user)
    ok = await activate_with_code(session, user, code)
    if ok:
        await state.clear()
        await msg.answer(ACCESS_GRANTED, reply_markup=main_menu())
    else:
        await msg.answer(CODE_BAD)
