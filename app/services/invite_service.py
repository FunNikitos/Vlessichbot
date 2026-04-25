"""Invite-code and deep-link invite domain operations."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActivationLog, DeepLinkInvite, InviteCode, User
from app.services.marzban.service import sync_user_expire

log = logging.getLogger(__name__)


def _gen_code(prefix: str = "", length: int = 12) -> str:
    return prefix + secrets.token_urlsafe(length).replace("-", "").replace("_", "")[:length]


async def create_invite_code(
    session: AsyncSession,
    *,
    created_by: int,
    days: int,
    max_uses: int = 1,
    ttl_days: int = 30,
) -> InviteCode:
    code = _gen_code(length=8).upper()
    invite = InviteCode(
        code=code,
        created_by=created_by,
        max_uses=max_uses,
        access_duration_days=days,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite


async def create_deep_link(
    session: AsyncSession, *, created_by: int, days: int, ttl_days: int = 7
) -> DeepLinkInvite:
    token = "inv_" + _gen_code(length=16)
    invite = DeepLinkInvite(
        token=token,
        created_by=created_by,
        access_duration_days=days,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite


async def use_deep_link_invite(session: AsyncSession, token: str, user: User) -> bool:
    now = datetime.now(timezone.utc)
    result = await session.execute(select(DeepLinkInvite).where(DeepLinkInvite.token == token))
    invite = result.scalar_one_or_none()
    if (
        invite is None
        or invite.used_by is not None
        or (invite.expires_at and invite.expires_at < now)
    ):
        return False
    invite.used_by = user.telegram_id
    invite.used_at = now

    user.status = "active"
    user.access_type = "invite"
    user.activated_at = now
    user.access_expires_at = now + timedelta(days=invite.access_duration_days)

    session.add(
        ActivationLog(
            user_id=user.id, deep_link_invite_id=invite.id, activation_type="deep_link"
        )
    )
    await session.commit()
    await sync_user_expire(user)
    return True
