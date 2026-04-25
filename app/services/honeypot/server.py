"""Honeypot TCP server.

Слушает HONEYPOT_PORT, на любое подключение:
  1. Закрывает сокет сразу (никаких ответов — no banner = no fingerprint).
  2. Сохраняет HoneypotHit (с GeoIP enrichment в фоне).
  3. Пытается забанить IP через ufw, обновляет blocked-флаг.
  4. Шлёт алерт владельцу.
  5. Пишет AuditLog (action=honeypot.block).

Пропускаем локальные IP (probe_protocols пробует свой же домен → может
прилететь от LB). Дедупликация: один IP блокируем один раз в час.
"""
from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot
from sqlalchemy import desc, select

from app.bot.texts.admin import HONEYPOT_BLOCK_FAIL, HONEYPOT_BLOCKED, HONEYPOT_HIT
from app.config import settings
from app.db.models import HoneypotHit
from app.db.session import SessionLocal
from app.services.honeypot.ufw import ufw_block
from app.utils.audit import audit
from app.utils.geoip import lookup_country

log = logging.getLogger(__name__)

# in-memory дедуп: ip -> last_block_ts
_recent_block: dict[str, float] = {}
_DEDUP_WINDOW_SEC = 3600


def _is_local(ip: str) -> bool:
    return (
        ip.startswith("10.")
        or ip.startswith("127.")
        or ip.startswith("192.168.")
        or ip == "::1"
        or ip.startswith("fe80:")
    )


class HoneypotServer:
    def __init__(self, bot: Bot, host: str = "0.0.0.0", port: int | None = None) -> None:
        self._bot = bot
        self._host = host
        self._port = port or settings.honeypot_port
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> None:
        if not settings.honeypot_enabled:
            log.info("Honeypot disabled (HONEYPOT_ENABLED=false)")
            return
        try:
            self._server = await asyncio.start_server(
                self._on_connect, host=self._host, port=self._port
            )
        except OSError as e:
            log.warning("Honeypot bind %s:%d failed: %s", self._host, self._port, e)
            return
        sockets = [s.getsockname() for s in (self._server.sockets or [])]
        log.info("Honeypot listening on %s", sockets)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        log.info("Honeypot stopped")
        self._server = None

    async def _on_connect(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername") or ("?", 0)
        ip = peer[0] if peer else "?"
        # closed immediately — no banner, no probe-data leak
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass
        # обработка в отдельной таске, чтобы соединения не висли
        asyncio.create_task(self._handle_hit(ip))

    async def _handle_hit(self, ip: str) -> None:
        if _is_local(ip):
            return
        now = time.time()
        last = _recent_block.get(ip)
        if last and now - last < _DEDUP_WINDOW_SEC:
            return
        _recent_block[ip] = now

        country = await lookup_country(ip)

        # ban via ufw
        ok, info = await ufw_block(ip)

        async with SessionLocal() as session:
            hit = HoneypotHit(
                ip=ip,
                country=country,
                port=self._port,
                blocked=ok,
            )
            session.add(hit)
            await session.commit()

            await audit(
                actor_type="system",
                actor_id=0,
                action="honeypot.block" if ok else "honeypot.hit",
                payload={"ip": ip, "country": country, "port": self._port, "info": info},
                session=session,
            )

        country_line = f"Страна: {country}\n" if country else ""
        try:
            await self._bot.send_message(
                settings.owner_id,
                HONEYPOT_HIT.format(ip=ip, country_line=country_line, port=self._port),
            )
            if ok:
                await self._bot.send_message(
                    settings.owner_id, HONEYPOT_BLOCKED.format(ip=ip)
                )
            else:
                await self._bot.send_message(
                    settings.owner_id,
                    HONEYPOT_BLOCK_FAIL.format(ip=ip, info=info),
                )
        except Exception as e:  # noqa: BLE001
            log.warning("honeypot owner alert failed: %s", e)
