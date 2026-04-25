"""Probe VPN protocols: TCP/TLS reachability per inbound.

Каждые MONITOR_INTERVAL_MIN мин дёргаем Marzban /api/inbounds, для
каждого inbound'а пробуем установить TCP-соединение на host:port.
Пишем результат в ProbeMetric. Если 3 последних замера failed —
открываем BlockEvent (если ещё не открыт) и шлём alert владельцу.
При успехе после fail-стрика — закрываем BlockEvent и шлём recovered.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import desc, select

from app.bot.texts.admin import SERVER_DOWN, SERVER_RECOVERED
from app.config import settings
from app.db.models import BlockEvent, ProbeMetric, Server
from app.db.session import SessionLocal
from app.services.marzban.client import MarzbanError, get_marzban
from app.utils.errors import log_error

log = logging.getLogger(__name__)

CONSECUTIVE_FAIL_THRESHOLD = 3


async def _tcp_probe(host: str, port: int, timeout: float = 5.0) -> tuple[bool, int | None]:
    """TCP-handshake + быстрый close. Возвращает (success, latency_ms)."""
    start = time.perf_counter()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        latency = int((time.perf_counter() - start) * 1000)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return True, latency
    except (asyncio.TimeoutError, OSError):
        return False, None


def _classify(tag: str, network: str | None, security: str | None) -> str:
    """Привести inbound к нашему protocol-tag (см. PROTO_LABELS)."""
    t = (tag or "").lower()
    n = (network or "").lower()
    s = (security or "").lower()
    if "reality" in t or s == "reality":
        return "vless_reality"
    if "xhttp" in t or n == "xhttp":
        return "vless_xhttp"
    if "grpc" in t or n == "grpc":
        return "vless_grpc_cf"
    return "vless_reality"


async def run(bot: Bot) -> None:
    client = get_marzban()
    try:
        inbounds = await client.get_inbounds()
    except MarzbanError as e:
        await log_error(source="job.probe_protocols", message=str(e), exc=e)
        return

    targets: list[tuple[str, str, int]] = []
    for proto, items in inbounds.items():
        for it in items:
            port = it.get("port")
            if not port:
                continue
            tag = it.get("tag") or proto
            network = it.get("network")
            security = it.get("security")
            classified = _classify(tag, network, security)
            targets.append((classified, settings.server_domain, int(port)))

    if not targets:
        log.warning("probe_protocols: no inbounds returned by Marzban")
        return

    async with SessionLocal() as session:
        # primary server (для FK в ProbeMetric/BlockEvent)
        srv_row = await session.execute(select(Server).order_by(Server.id).limit(1))
        server = srv_row.scalar_one_or_none()
        server_id = server.id if server else None

        for protocol, host, port in targets:
            ok, latency = await _tcp_probe(host, port)
            session.add(
                ProbeMetric(
                    server_id=server_id,
                    protocol=protocol,
                    latency_ms=latency,
                    success=ok,
                )
            )
            await session.flush()

            # streak check (последние N замеров по этому протоколу)
            recent = await session.execute(
                select(ProbeMetric.success)
                .where(ProbeMetric.protocol == protocol)
                .order_by(desc(ProbeMetric.probed_at))
                .limit(CONSECUTIVE_FAIL_THRESHOLD)
            )
            recent_vals = [r[0] for r in recent.all()]

            open_event_q = await session.execute(
                select(BlockEvent)
                .where(BlockEvent.protocol == protocol, BlockEvent.resolved_at.is_(None))
                .order_by(desc(BlockEvent.detected_at))
                .limit(1)
            )
            open_event = open_event_q.scalar_one_or_none()

            now = datetime.now(timezone.utc)
            ts = now.strftime("%Y-%m-%d %H:%M UTC")

            if (
                len(recent_vals) >= CONSECUTIVE_FAIL_THRESHOLD
                and not any(recent_vals)
                and open_event is None
            ):
                ev = BlockEvent(server_id=server_id, protocol=protocol)
                session.add(ev)
                try:
                    await bot.send_message(
                        settings.owner_id,
                        SERVER_DOWN.format(name=protocol, host=host, datetime=ts),
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("alert SERVER_DOWN failed: %s", e)

            if ok and open_event is not None:
                open_event.resolved_at = now
                open_event.action = "auto-recovered"
                try:
                    await bot.send_message(
                        settings.owner_id,
                        SERVER_RECOVERED.format(name=protocol, host=host, datetime=ts),
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("alert SERVER_RECOVERED failed: %s", e)

        await session.commit()
