"""Admin: honeypot — status, on/off toggle, hits log."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu, honeypot_menu
from app.config import settings
from app.db.models import HoneypotHit
from app.services.honeypot.server import get_instance
from app.services.settings_store import get_bool
from app.utils.audit import audit

router = Router(name="admin.honeypot")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

log = logging.getLogger(__name__)


async def _render_status() -> str:
    srv = get_instance()
    enabled = await get_bool("honeypot.enabled", settings.honeypot_enabled)
    running = bool(srv and srv.is_running)
    if running:
        state = "🟢 включён, слушает"
    elif enabled:
        state = "🟡 включён, но не слушает (порт занят?)"
    else:
        state = "🔴 выключен"
    return (
        "<b>👁 Honeypot</b>\n"
        f"Состояние: {state}\n"
        f"Порт: <code>{settings.honeypot_port}</code>"
    )


@router.callback_query(F.data == "adm:honeypot")
async def cb_honeypot(cb: CallbackQuery) -> None:
    srv = get_instance()
    running = bool(srv and srv.is_running)
    await cb.message.edit_text(await _render_status(), reply_markup=honeypot_menu(running))
    await cb.answer()


@router.callback_query(F.data == "hp:on")
async def cb_hp_on(cb: CallbackQuery) -> None:
    srv = get_instance()
    if srv is None:
        await cb.answer("Honeypot не инициализирован", show_alert=True)
        return
    running = await srv.enable()
    await audit(actor_type="admin", actor_id=cb.from_user.id, action="honeypot.enable")
    await cb.answer("Включил" if running else "Включено в настройках, но bind не удался")
    await cb.message.edit_text(await _render_status(), reply_markup=honeypot_menu(srv.is_running))


@router.callback_query(F.data == "hp:off")
async def cb_hp_off(cb: CallbackQuery) -> None:
    srv = get_instance()
    if srv is None:
        await cb.answer("Honeypot не инициализирован", show_alert=True)
        return
    await srv.disable()
    await audit(actor_type="admin", actor_id=cb.from_user.id, action="honeypot.disable")
    await cb.answer("Выключил")
    await cb.message.edit_text(await _render_status(), reply_markup=honeypot_menu(srv.is_running))


@router.callback_query(F.data == "hp:list")
async def cb_hp_list(cb: CallbackQuery, session: AsyncSession) -> None:
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
    srv = get_instance()
    await cb.message.edit_text(text, reply_markup=honeypot_menu(bool(srv and srv.is_running)))
    await cb.answer()


@router.message(Command("honeypot"))
async def honeypot_cmd(msg: Message) -> None:
    srv = get_instance()
    running = bool(srv and srv.is_running)
    await msg.answer(await _render_status(), reply_markup=honeypot_menu(running))
