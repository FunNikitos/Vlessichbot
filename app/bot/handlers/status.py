"""/status — heatmap availability per protocol."""
from __future__ import annotations

import statistics

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.user import back_to_menu
from app.config import settings
from app.db.models import ProbeMetric
from app.services.marzban.client import get_marzban
from app.services.monitor.prober import PROTO_LABELS

router = Router(name="status")


async def _render_status(session: AsyncSession) -> str:
    lines = [f"📡 <b>Статус сервиса</b>  ({settings.server_domain})\n"]
    panel_ok = await get_marzban().health()
    lines.append(f"Marzban: {'🟢 online' if panel_ok else '🔴 offline'}")
    for protocol, label in PROTO_LABELS.items():
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await session.execute(
            select(ProbeMetric).where(
                ProbeMetric.protocol == protocol, ProbeMetric.probed_at >= cutoff
            )
        )
        probes = list(result.scalars().all())
        if not probes:
            lines.append(f"{label}  —  нет данных")
            continue
        ok = sum(1 for p in probes if p.success)
        avail = ok / len(probes)
        latencies = [p.latency_ms for p in probes if p.latency_ms is not None]
        ping = int(statistics.mean(latencies)) if latencies else 0
        icon = "✅" if avail > 0.9 else ("⚠️" if avail > 0.5 else "🔴")
        lines.append(f"{label}  {icon}  ping: {ping}ms  доступность: {avail*100:.0f}%")
    return "\n".join(lines)


@router.message(Command("status"))
async def status_cmd(msg: Message, session: AsyncSession) -> None:
    await msg.answer(await _render_status(session))


@router.callback_query(F.data == "status")
async def cb_status(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.message.edit_text(await _render_status(session), reply_markup=back_to_menu())
    await cb.answer()
