"""Token issuance for our subscription endpoint."""
from __future__ import annotations

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def ensure_sub_token(session: AsyncSession, user: User) -> str:
    """Idempotent: generate a 32-char URL-safe token if user has none.
    Caller must commit."""
    if user.sub_token:
        return user.sub_token
    user.sub_token = secrets.token_urlsafe(24)
    await session.flush()
    return user.sub_token
