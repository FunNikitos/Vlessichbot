"""Connection (config) domain operations.

Создание конфига = ensure пользователь существует в Marzban, ensure у
него выпущен наш ``sub_token``, и записать в Connection НАШ
subscription URL (``https://<server_domain>/sub/<token>``). На клиенте
живёт только наш URL — Marzban-сабскрипшн остаётся внутренним.
"""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Connection, Server, User
from app.services.marzban.service import (
    delete_marzban_user,
    ensure_marzban_user,
)
from app.services.subscription.builder import public_sub_url
from app.services.subscription.tokens import ensure_sub_token

log = logging.getLogger(__name__)


async def _ensure_default_server(session: AsyncSession) -> Server:
    result = await session.execute(select(Server).order_by(Server.id).limit(1))
    server = result.scalar_one_or_none()
    if server is None:
        server = Server(
            name="primary",
            host=settings.server_domain,
            marzban_api_url=settings.marzban_api_url,
        )
        session.add(server)
        await session.commit()
        await session.refresh(server)
    return server


def _resolve_marzban_sub(payload: dict) -> str:
    sub_url = payload.get("subscription_url") or ""
    if sub_url:
        return sub_url
    token_path = payload.get("subscription_token") or payload.get("subscription") or ""
    if token_path:
        return f"https://{settings.server_domain}{token_path}"
    return ""


async def create_connection(session: AsyncSession, user: User) -> Connection:
    server = await _ensure_default_server(session)
    payload = await ensure_marzban_user(user)
    marzban_sub = _resolve_marzban_sub(payload)
    if not marzban_sub:
        raise RuntimeError("Marzban не вернул subscription_url")
    token = await ensure_sub_token(session, user)
    our_sub = public_sub_url(token)

    name = f"vlessich-{secrets.token_hex(2)}"
    conn = Connection(
        user_id=user.id,
        server_id=server.id,
        name=name,
        profile_type="standard",
        routing_mode="smart",
        # ВАЖНО: subscription_url хранит исходный Marzban-URL — это
        # внутренний источник для нашего sub-сервера. Клиент видит
        # только public_sub_url(token).
        subscription_url=marzban_sub,
        qr_payload=our_sub,
        marzban_username=user.marzban_username,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return conn


async def list_connections(session: AsyncSession, user_id: int) -> list[Connection]:
    result = await session.execute(
        select(Connection).where(Connection.user_id == user_id).order_by(Connection.id)
    )
    return list(result.scalars().all())


async def get_connection(
    session: AsyncSession, conn_id: int, user_id: int
) -> Connection | None:
    result = await session.execute(
        select(Connection).where(Connection.id == conn_id, Connection.user_id == user_id)
    )
    return result.scalar_one_or_none()


def public_url_for(conn: Connection, user: User) -> str:
    """Что показывать пользователю — наш ``/sub/<token>``."""
    if conn.qr_payload and conn.qr_payload.startswith("http"):
        return conn.qr_payload
    if user.sub_token:
        return public_sub_url(user.sub_token)
    return conn.subscription_url


async def set_routing_mode(
    session: AsyncSession, conn: Connection, mode: str
) -> Connection:
    if mode not in ("smart", "full"):
        raise ValueError(f"unknown routing_mode: {mode}")
    conn.routing_mode = mode
    await session.commit()
    await session.refresh(conn)
    return conn


async def delete_connection(session: AsyncSession, conn_id: int, user_id: int) -> bool:
    conn = await get_connection(session, conn_id, user_id)
    if conn is None:
        return False
    await session.delete(conn)
    # Если это был последний конфиг — удаляем Marzban-юзера целиком.
    remaining = await session.execute(
        select(Connection).where(Connection.user_id == user_id)
    )
    if remaining.first() is None:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is not None:
            await delete_marzban_user(user)
            user.marzban_username = None
    await session.commit()
    return True
