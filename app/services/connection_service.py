"""Connection (config) domain operations.

Stub-версия для шага 1: реальная интеграция с Marzban будет в фазе 2.
Сейчас мы создаём запись в БД с псевдо-URL'ом, чтобы хэндлеры
работали end-to-end (можно посмотреть QR/список/удалить)."""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Connection, Server, User

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

    if user.sub_token is None:
        user.sub_token = secrets.token_urlsafe(24)

    sub_url = (
        f"https://{settings.server_domain}:{settings.subscription_public_port}"
        f"/sub/{user.sub_token}"
    )
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
    await session.commit()
    return True
