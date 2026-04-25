"""Reality inbound rotator: SNI / port / short_id.

Меняет параметры VLESS+Reality inbound прямо в Xray-config через
Marzban /api/core/config + /api/core/restart. Обновляет InboundState.

Все три ротации идемпотентны и атомарны на уровне одного PUT'а конфига.
"""
from __future__ import annotations

import logging
import random
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import InboundState, Server, SniDonor
from app.services.marzban.client import MarzbanError, get_marzban
from app.utils.errors import log_error

log = logging.getLogger(__name__)


# ---------- helpers ----------


def _gen_short_id() -> str:
    """Reality short_id — hex длиной от 0 до 16. Берём 8 байт = 16 hex-символов."""
    return secrets.token_hex(8)


def _pick_port(current: int | None) -> int:
    """Случайный TCP-порт в диапазоне 10000-65000, отличный от текущего."""
    while True:
        candidate = random.randint(10000, 65000)
        if candidate != current:
            return candidate


async def _pick_sni(session: AsyncSession, current: str | None) -> str:
    """Выбрать SNI: сначала из sni_donors-таблицы (top score), fallback — из settings."""
    result = await session.execute(
        select(SniDonor).order_by(SniDonor.score.desc(), SniDonor.id.desc()).limit(20)
    )
    donors = [d.domain for d in result.scalars().all()]
    if not donors:
        donors = list(settings.sni_donors)
    candidates = [d for d in donors if d != current]
    if not candidates:
        candidates = donors
    return random.choice(candidates)


def _find_inbound(config: dict[str, Any], tag: str) -> dict[str, Any] | None:
    for inb in config.get("inbounds", []):
        if inb.get("tag") == tag:
            return inb
    return None


# ---------- core ----------


async def _get_primary_server(session: AsyncSession) -> Server:
    result = await session.execute(select(Server).order_by(Server.id).limit(1))
    server = result.scalar_one_or_none()
    if server is None:
        server = Server(name="primary", host=settings.server_domain)
        session.add(server)
        await session.commit()
        await session.refresh(server)
    return server


async def _get_state(session: AsyncSession, server_id: int, tag: str) -> InboundState:
    result = await session.execute(
        select(InboundState).where(
            InboundState.server_id == server_id, InboundState.inbound_tag == tag
        )
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = InboundState(server_id=server_id, inbound_tag=tag)
        session.add(state)
        await session.flush()
    return state


async def _apply(
    session: AsyncSession, *, mutate, kind: str
) -> tuple[bool, str | int | None, str | None]:
    """Generic wrapper: load core config, mutate Reality inbound, push back, restart.
    Returns (ok, new_value, error_msg)."""
    client = get_marzban()
    server = await _get_primary_server(session)
    tag = server.marzban_inbound_tag
    try:
        cfg = await client.get_core_config()
        inb = _find_inbound(cfg, tag)
        if inb is None:
            return False, None, f"inbound '{tag}' не найден в core config"
        new_value = await mutate(inb, session)
        await client.put_core_config(cfg)
        await client.restart_core()
    except MarzbanError as e:
        await log_error(source=f"rotation.{kind}", message=str(e), exc=e, session=session)
        return False, None, str(e)

    state = await _get_state(session, server.id, tag)
    if kind == "sni":
        state.current_sni = new_value
    elif kind == "port":
        state.current_port = int(new_value)
    elif kind == "short_id":
        state.current_short_id = new_value
    state.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True, new_value, None


# ---------- public ops ----------


async def rotate_sni(session: AsyncSession) -> tuple[bool, str | int | None, str | None]:
    async def mutate(inb: dict[str, Any], s: AsyncSession) -> str:
        ss = inb.setdefault("streamSettings", {})
        rs = ss.setdefault("realitySettings", {})
        current = (rs.get("serverNames") or [None])[0]
        new_sni = await _pick_sni(s, current)
        rs["serverNames"] = [new_sni]
        rs["dest"] = f"{new_sni}:443"
        return new_sni

    return await _apply(session, mutate=mutate, kind="sni")


async def rotate_port(session: AsyncSession) -> tuple[bool, str | int | None, str | None]:
    async def mutate(inb: dict[str, Any], s: AsyncSession) -> int:
        current = inb.get("port")
        new_port = _pick_port(current if isinstance(current, int) else None)
        inb["port"] = new_port
        return new_port

    return await _apply(session, mutate=mutate, kind="port")


async def rotate_short_id(session: AsyncSession) -> tuple[bool, str | int | None, str | None]:
    async def mutate(inb: dict[str, Any], s: AsyncSession) -> str:
        ss = inb.setdefault("streamSettings", {})
        rs = ss.setdefault("realitySettings", {})
        new_sid = _gen_short_id()
        rs["shortIds"] = [new_sid]
        return new_sid

    return await _apply(session, mutate=mutate, kind="short_id")
