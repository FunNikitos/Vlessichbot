"""Traffic accounting — read-only views over Marzban counters.

Marzban returns per-user counters in bytes:
- ``used_traffic``           : current period (since last reset).
- ``lifetime_used_traffic``  : cumulative since user creation.
- ``online_at``              : ISO timestamp of last seen connection.

System-wide stats come from ``GET /api/system``:
- ``total_user``, ``users_active``, ``incoming_bandwidth``,
  ``outgoing_bandwidth``, ``incoming_bandwidth_speed``,
  ``outgoing_bandwidth_speed``, ``mem_used``, ``cpu_usage``.

We don't persist these — every call hits Marzban fresh. For a few
hundred users this is fine; if it ever becomes hot, add Redis cache
(60s TTL) here.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.marzban.client import MarzbanError, get_marzban

log = logging.getLogger(__name__)


def humanize_bytes(n: int | float | None) -> str:
    """Format bytes count as human-readable string (KB/MB/GB/TB)."""
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PB"


async def get_system_summary() -> dict[str, Any]:
    """Aggregate system counters. Returns empty dict on failure (caller must format)."""
    client = get_marzban()
    try:
        return await client.get_system_stats()
    except MarzbanError as e:
        log.warning("traffic.system: %s", e)
        return {}


async def list_top_users(limit: int = 10) -> list[dict[str, Any]]:
    """Return top users by current-period ``used_traffic``."""
    client = get_marzban()
    try:
        # Pull all in pages of 200 — Marzban caps page size around 1000.
        users: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = await client.get_users(offset=offset, limit=200)
            chunk = page.get("users") or []
            if not chunk:
                break
            users.extend(chunk)
            if len(chunk) < 200:
                break
            offset += 200
            if offset >= 2000:  # safety cap
                break
    except MarzbanError as e:
        log.warning("traffic.list: %s", e)
        return []
    users.sort(key=lambda u: int(u.get("used_traffic") or 0), reverse=True)
    return users[:limit]


async def get_user_traffic(marzban_username: str) -> dict[str, Any] | None:
    """Per-user counters. Returns None if user not found in Marzban."""
    client = get_marzban()
    try:
        return await client.get_user(marzban_username)
    except MarzbanError as e:
        log.warning("traffic.user(%s): %s", marzban_username, e)
        return None


async def resolve_marzban_username(
    session: AsyncSession, telegram_id: int
) -> str | None:
    result = await session.execute(
        select(User.marzban_username).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


# ---------- presentation ----------


def format_system_summary(stats: dict[str, Any]) -> str:
    if not stats:
        return "📊 <b>Трафик системы</b>\n❌ Marzban недоступен"
    lines = [
        "📊 <b>Трафик системы</b>",
        f"Всего пользователей: <b>{stats.get('total_user', 0)}</b>",
        f"Активных: <b>{stats.get('users_active', 0)}</b>",
        f"Онлайн (24h): <b>{stats.get('online_users', stats.get('users_online', '—'))}</b>",
        "",
        f"⬇️ Входящий: <b>{humanize_bytes(stats.get('incoming_bandwidth'))}</b> "
        f"({humanize_bytes(stats.get('incoming_bandwidth_speed'))}/s)",
        f"⬆️ Исходящий: <b>{humanize_bytes(stats.get('outgoing_bandwidth'))}</b> "
        f"({humanize_bytes(stats.get('outgoing_bandwidth_speed'))}/s)",
        "",
        f"CPU: <b>{stats.get('cpu_usage', '—')}%</b>  "
        f"RAM: <b>{humanize_bytes(stats.get('mem_used'))}</b> / "
        f"<b>{humanize_bytes(stats.get('mem_total'))}</b>",
    ]
    return "\n".join(lines)


def format_top_users(users: list[dict[str, Any]]) -> str:
    if not users:
        return "<i>Нет пользователей с активным трафиком.</i>"
    lines = ["", "<b>Топ потребителей (за период):</b>"]
    for i, u in enumerate(users, 1):
        lines.append(
            f"{i}. <code>{u.get('username', '?')}</code> — "
            f"{humanize_bytes(u.get('used_traffic'))} "
            f"(всего {humanize_bytes(u.get('lifetime_used_traffic'))})"
        )
    return "\n".join(lines)


def format_user_card(user: dict[str, Any]) -> str:
    status = user.get("status", "?")
    expire = user.get("expire") or 0
    online = user.get("online_at") or "—"
    return (
        f"👤 <b>{user.get('username', '?')}</b>\n"
        f"Статус: <code>{status}</code>\n"
        f"Последний онлайн: {online}\n"
        f"Истекает (unix): {expire}\n\n"
        f"⬇️/⬆️ Период: <b>{humanize_bytes(user.get('used_traffic'))}</b>\n"
        f"📦 Лимит: <b>{humanize_bytes(user.get('data_limit') or 0)}</b>\n"
        f"♾️ За всё время: <b>{humanize_bytes(user.get('lifetime_used_traffic'))}</b>"
    )
