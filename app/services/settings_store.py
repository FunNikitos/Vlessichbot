"""Runtime settings override (DB-backed Setting table).
ENV — defaults на старте; Setting — runtime override, который меняется
из админки без рестарта. Лёгкий cache-aside через SessionLocal."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.models import Setting
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


async def get_setting(key: str, default: str | None = None) -> str | None:
    async with SessionLocal() as s:
        result = await s.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(key: str, value: str) -> None:
    async with SessionLocal() as s:
        result = await s.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            s.add(Setting(key=key, value=value))
        else:
            row.value = value
        await s.commit()


async def get_bool(key: str, default: bool) -> bool:
    raw = await get_setting(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def set_bool(key: str, value: bool) -> None:
    await set_setting(key, "true" if value else "false")
