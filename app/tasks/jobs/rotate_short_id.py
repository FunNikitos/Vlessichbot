"""Periodic short_id rotation (every SHORT_ID_ROTATION_DAYS)."""
from __future__ import annotations

import logging

from aiogram import Bot

from app.config import settings
from app.db.session import SessionLocal
from app.services.reality_sni.rotator import rotate_short_id

log = logging.getLogger(__name__)


async def run(bot: Bot) -> None:
    async with SessionLocal() as session:
        ok, value, err = await rotate_short_id(session)
    if ok:
        log.info("auto rotate_short_id ok: %s", value)
        try:
            await bot.send_message(
                settings.owner_id,
                f"🔄 Авто-ротация short_id: <code>{value}</code>",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("notify owner short_id rotation failed: %s", e)
    else:
        log.warning("auto rotate_short_id failed: %s", err)
