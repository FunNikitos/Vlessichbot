"""Admin: /findsni — on-demand probe of Reality SNI donor pool.

Runs the TLS1.3+h2 probe synchronously (small set, fast) and reports
top eligible donors. Useful before manual SNI rotation.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import IsAdmin
from app.bot.texts.admin import SNI_FINDER_RESULT
from app.db.models import SniDonor
from app.services.reality_sni.finder import DEFAULT_SEEDS, probe_domains

router = Router(name="admin.findsni")
router.message.filter(IsAdmin())


@router.message(Command("findsni"))
async def cmd_findsni(msg: Message, session: AsyncSession) -> None:
    await msg.answer("🔍 Запускаю TLS1.3+h2 probe (15-30 сек)…")
    existing = await session.execute(select(SniDonor.domain))
    seeds = set(DEFAULT_SEEDS) | {row[0] for row in existing.all()}
    results = await probe_domains(session, seeds)

    eligible = [(d, v) for d, v in results.items() if v[2] >= 2]
    eligible.sort(key=lambda x: (-x[1][2], x[0]))
    top_lines = "\n".join(
        f"• <code>{d}</code>  (tls1.3={'✓' if v[0] else '✗'} h2={'✓' if v[1] else '✗'})"
        for d, v in eligible[:15]
    ) or "<i>нет подходящих доменов</i>"

    await msg.answer(
        SNI_FINDER_RESULT.format(
            total=len(results),
            eligible=len(eligible),
            top=top_lines,
        )
    )
