"""Admin: Marzban panel diagnostics — health + inbounds."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.filters.admin import IsAdmin
from app.services.marzban.client import MarzbanError, get_marzban

router = Router(name="admin.marzban")
router.message.filter(IsAdmin())

log = logging.getLogger(__name__)


@router.message(Command("marzban"))
async def marzban_cmd(msg: Message) -> None:
    client = get_marzban()
    ok = await client.health()
    lines = [f"<b>Marzban</b>: {'🟢 online' if ok else '🔴 offline'}"]
    if ok:
        try:
            inbounds = await client.get_inbounds()
            lines.append("\n<b>Inbounds:</b>")
            # формат: { "vless": [ {tag, port, network, ...}, ... ], ... }
            for proto, items in inbounds.items():
                lines.append(f"\n<i>{proto}</i>")
                for it in items:
                    tag = it.get("tag", "?")
                    port = it.get("port", "?")
                    net = it.get("network", "?")
                    sec = it.get("security", "?")
                    lines.append(f"• <code>{tag}</code> :{port} {net}/{sec}")
        except MarzbanError as e:
            lines.append(f"\n❌ get_inbounds: {e}")
    await msg.answer("\n".join(lines))
