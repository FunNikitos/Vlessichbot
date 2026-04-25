"""Admin: rotation (SNI / port / short_id) — real Marzban core-config edits."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu, rotate_menu
from app.bot.texts.admin import (
    ROTATE_FAIL,
    ROTATE_OK_PORT,
    ROTATE_OK_SHORT_ID,
    ROTATE_OK_SNI,
)
from app.services.reality_sni.rotator import (
    rotate_port,
    rotate_short_id,
    rotate_sni,
)

router = Router(name="admin.rotation")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:rotate")
async def cb_rotate_menu(cb: CallbackQuery) -> None:
    await cb.message.edit_text("Что ротируем?", reply_markup=rotate_menu())
    await cb.answer()


@router.callback_query(F.data == "rot:sni")
async def cb_rotate_sni(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer("Ротирую SNI…")
    ok, value, err = await rotate_sni(session)
    text = ROTATE_OK_SNI.format(value=value) if ok else f"{ROTATE_FAIL}\n{err}"
    await cb.message.edit_text(text, reply_markup=admin_menu())


@router.callback_query(F.data == "rot:port")
async def cb_rotate_port(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer("Ротирую порт…")
    ok, value, err = await rotate_port(session)
    text = ROTATE_OK_PORT.format(value=value) if ok else f"{ROTATE_FAIL}\n{err}"
    await cb.message.edit_text(text, reply_markup=admin_menu())


@router.callback_query(F.data == "rot:sid")
async def cb_rotate_sid(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer("Ротирую short_id…")
    ok, value, err = await rotate_short_id(session)
    text = ROTATE_OK_SHORT_ID.format(value=value) if ok else f"{ROTATE_FAIL}\n{err}"
    await cb.message.edit_text(text, reply_markup=admin_menu())
