"""User-domain operations: get-or-create, activation by code."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActivationLog, AuthAttempt, InviteCode, User
from app.config import settings
from app.services.marzban.service import sync_user_expire

log = logging.getLogger(__name__)


async def get_or_create_user(session: AsyncSession, tg_user: TgUser) -> User:
    result = await session.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # держим username/first_name актуальными
        changed = False
        if user.username != tg_user.username:
            user.username = tg_user.username
            changed = True
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
            changed = True
        if changed:
            await session.commit()
    return user


async def _attempt_record(session: AsyncSession, telegram_id: int) -> AuthAttempt:
    result = await session.execute(
        select(AuthAttempt).where(
            AuthAttempt.telegram_id == telegram_id, AuthAttempt.section == "vpn"
        )
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        attempt = AuthAttempt(telegram_id=telegram_id, section="vpn")
        session.add(attempt)
        await session.flush()
    return attempt


async def activate_with_code(session: AsyncSession, user: User, code: str) -> bool:
    """Validate invite code and grant access. Returns True on success."""
    now = datetime.now(timezone.utc)
    attempt = await _attempt_record(session, user.telegram_id)

    if attempt.blocked_until and attempt.blocked_until > now:
        return False

    result = await session.execute(select(InviteCode).where(InviteCode.code == code))
    invite = result.scalar_one_or_none()
    valid = (
        invite is not None
        and invite.status == "active"
        and invite.used_count < invite.max_uses
        and (invite.expires_at is None or invite.expires_at > now)
    )

    if not valid:
        attempt.attempts += 1
        attempt.last_attempt_at = now
        if attempt.attempts >= settings.auth_max_attempts:
            attempt.block_streak += 1
            attempt.attempts = 0
            attempt.blocked_until = now + timedelta(minutes=settings.auth_block_minutes)
        await session.commit()
        return False

    invite.used_count += 1
    if invite.used_count >= invite.max_uses:
        invite.status = "used"

    user.status = "active"
    user.access_type = "code"
    user.activated_at = now
    user.access_expires_at = now + timedelta(days=invite.access_duration_days)

    session.add(
        ActivationLog(user_id=user.id, invite_code_id=invite.id, activation_type="code")
    )
    attempt.attempts = 0
    attempt.blocked_until = None
    attempt.last_attempt_at = now
    await session.commit()
    # Если уже есть marzban-аккаунт — продлим срок и активируем там.
    await sync_user_expire(user)
    return True
