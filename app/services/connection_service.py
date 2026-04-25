"""Connection (config) domain operations.

Создание конфига = ensure пользователь существует в Marzban и взять
его subscription_url. Несколько Connection на одного пользователя —
это просто разные «именованные виды» одного и того же sub-URL
(Marzban-юзер один на Telegram-юзера, но имена/режимы routing разные).
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


async def create_connection(session: AsyncSession, user: User) -> Connection:
    server = await _ensure_default_server(session)
    payload = await ensure_marzban_user(user)
    sub_url = payload.get("subscription_url") or ""
    if not sub_url:
        # старые версии Marzban иногда отдают только ключ без хоста
        token_path = payload.get("subscription_token") or payload.get("subscription") or ""
        if token_path:
            sub_url = f"https://{settings.server_domain}{token_path}"
    if not sub_url:
        raise RuntimeError("Marzban не вернул subscription_url")

    name = f"vlessich-{secrets.token_hex(2)}"
    conn = Connection(
        user_id=user.id,
        server_id=server.id,
        name=name,
        profile_type="standard",
        routing_mode="smart",
        subscription_url=sub_url,
        qr_payload=sub_url,
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
