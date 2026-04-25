"""APScheduler bootstrap. Регистрирует все периодические задачи."""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

log = logging.getLogger(__name__)


async def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    from app.tasks.jobs import expire_users, probe_protocols, rotate_short_id

    scheduler.add_job(
        expire_users.run,
        IntervalTrigger(minutes=settings.expiration_interval_min),
        kwargs={"bot": bot},
        id="expire_users",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        probe_protocols.run,
        IntervalTrigger(minutes=settings.monitor_interval_min),
        kwargs={"bot": bot},
        id="probe_protocols",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        rotate_short_id.run,
        IntervalTrigger(days=settings.short_id_rotation_days),
        kwargs={"bot": bot},
        id="rotate_short_id",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "Scheduler started: expire/%dm, probe/%dm, rotate_short_id/%dd",
        settings.expiration_interval_min,
        settings.monitor_interval_min,
        settings.short_id_rotation_days,
    )
    return scheduler


async def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
