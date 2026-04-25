"""APScheduler bootstrap. Здесь регистрируются все периодические задачи.
Stub-версия для шага 1: создаём планировщик, но job'ов пока нет —
их добавим в фазе мониторинга и ротаций."""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)


async def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.start()
    log.info("Scheduler started (no jobs registered yet)")
    return scheduler


async def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
