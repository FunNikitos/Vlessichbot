"""Refresh antifilter RU subnet cache periodically."""
from __future__ import annotations

import logging

from aiogram import Bot

from app.services.routing.antifilter import refresh_cache

log = logging.getLogger(__name__)


async def run(bot: Bot) -> None:  # noqa: ARG001 - signature unified across jobs
    count = await refresh_cache()
    if count == 0:
        log.warning("antifilter refresh: 0 subnets (kept stale cache if any)")
    else:
        log.info("antifilter refresh: %d subnets", count)
