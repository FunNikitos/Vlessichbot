"""High-level Marzban operations — used by bot handlers."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from app.db.models import User
from app.services.marzban.client import MarzbanError, get_marzban

log = logging.getLogger(__name__)


def make_marzban_username(user: User) -> str:
    """Стабильный, уникальный per-user идентификатор для Marzban."""
    if user.marzban_username:
        return user.marzban_username
    # ограничение Marzban: 3..32 символа, [a-zA-Z0-9_]
    suffix = secrets.token_hex(4)
    return f"u{user.telegram_id}_{suffix}"


def _expire_ts(user: User) -> int | None:
    if user.access_expires_at is None:
        return None
    return int(user.access_expires_at.replace(tzinfo=timezone.utc).timestamp())


async def ensure_marzban_user(user: User) -> dict[str, Any]:
    """Idempotent: создаёт Marzban-юзера или возвращает существующего.
    Возвращает payload с subscription_url. Side-effect: проставляет
    user.marzban_username (caller должен сделать commit)."""
    client = get_marzban()
    username = make_marzban_username(user)
    payload = await client.get_user(username)
    if payload is None:
        payload = await client.create_user(
            username,
            expire=_expire_ts(user),
            note=f"tg:{user.telegram_id}",
        )
    user.marzban_username = username
    return payload


async def deactivate_marzban_user(user: User) -> None:
    if not user.marzban_username:
        return
    client = get_marzban()
    try:
        await client.set_status(user.marzban_username, "disabled")
    except MarzbanError as e:
        log.warning("set_status disabled failed for %s: %s", user.marzban_username, e)


async def delete_marzban_user(user: User) -> None:
    if not user.marzban_username:
        return
    client = get_marzban()
    try:
        await client.delete_user(user.marzban_username)
    except MarzbanError as e:
        log.warning("delete_user failed for %s: %s", user.marzban_username, e)
