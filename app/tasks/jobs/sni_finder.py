"""Periodic Reality SNI freshness probe.

Runs the curated seed list (and any existing donors) through TLS1.3+h2
checks weekly and updates ``sni_donors`` scores. Notifies owner on
material changes (e.g., zero eligible donors -> ops alert).
"""
from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy import select

from app.bot.texts.admin import OWNER_GENERIC_ALERT
from app.config import settings
from app.db.models import SniDonor
from app.db.session import SessionLocal
from app.services.reality_sni.finder import DEFAULT_SEEDS, probe_domains

log = logging.getLogger(__name__)


async def run(bot: Bot) -> None:
    async with SessionLocal() as session:
        existing = await session.execute(select(SniDonor.domain))
        seeds = set(DEFAULT_SEEDS) | {row[0] for row in existing.all()}
        results = await probe_domains(session, seeds)

    eligible = sum(1 for v in results.values() if v[2] >= 2)
    log.info("sni_finder job: %d probed, %d eligible", len(results), eligible)
    if eligible == 0 and settings.owner_id:
        try:
            await bot.send_message(
                settings.owner_id,
                OWNER_GENERIC_ALERT.format(
                    title="SNI Finder",
                    body="Ни один из донорских доменов не прошёл TLS1.3+h2. Reality-маскировка может деградировать.",
                ),
            )
        except Exception:  # noqa: BLE001
            pass
