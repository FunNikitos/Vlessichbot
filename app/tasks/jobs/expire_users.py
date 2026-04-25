"""Expire users whose access_expires_at < now: disable in Marzban + notify."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select

from app.bot.texts.admin import USER_EXPIRED_NOTIFY, USER_EXPIRED_OWNER
from app.config import settings
from app.db.models import Connection, User
from app.db.session import SessionLocal
from app.services.marzban.service import deactivate_marzban_user
from app.utils.errors import log_error

log = logging.getLogger(__name__)


async def run(bot: Bot) -> None:
    """Single-pass expiration check."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.status == "active",
                User.access_expires_at.is_not(None),
                User.access_expires_at < now,
            )
        )
        users = list(result.scalars().all())
        if not users:
            return
        log.info("expire job: %d users to expire", len(users))

        for user in users:
            try:
                await deactivate_marzban_user(user)
            except Exception as e:  # noqa: BLE001
                await log_error(
                    source="job.expire_users",
                    message=f"deactivate failed for {user.telegram_id}: {e}",
                    user_id=user.telegram_id,
                    exc=e,
                    session=session,
                )

            conn_count = await session.scalar(
                select(Connection.id).where(Connection.user_id == user.id).limit(1)
            )
            connections_count_q = await session.execute(
                select(Connection).where(Connection.user_id == user.id)
            )
            connections_count = len(list(connections_count_q.scalars().all()))

            user.status = "expired"

            # notify user
            try:
                await bot.send_message(user.telegram_id, USER_EXPIRED_NOTIFY)
            except Exception as e:  # noqa: BLE001
                log.warning("notify user %s failed: %s", user.telegram_id, e)

            # notify owner
            try:
                await bot.send_message(
                    settings.owner_id,
                    USER_EXPIRED_OWNER.format(
                        name=user.username or user.first_name or "—",
                        telegram_id=user.telegram_id,
                        connections_count=connections_count,
                    ),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("notify owner failed: %s", e)

        await session.commit()
