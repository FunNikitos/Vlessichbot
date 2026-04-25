"""aiohttp subscription server.

Endpoints:

- ``GET /healthz``                   — for Caddy/uptime checks.
- ``GET /sub/<token>``               — plain VLESS lines (Marzban passthrough).
- ``GET /sub/<token>/singbox``       — sing-box JSON with our split-tunnel.
- ``GET /sub/<token>?mode=full``     — disable smart routing for this poll.

Design notes:

- Token = ``users.sub_token`` (per-user, 24-byte url-safe). Never expose
  Marzban's own subscription URL to clients — we proxy & rewrite.
- We pull fresh content from Marzban on every request (no cache). That's
  fine: rotations should propagate within client poll interval anyway.
- Errors return ``404`` for unknown token, ``502`` for Marzban failures.
"""
from __future__ import annotations

import logging

from aiohttp import web
from sqlalchemy import select

from app.config import settings
from app.db.models import Connection, User
from app.db.session import SessionLocal
from app.services.subscription.builder import (
    build_singbox_profile,
    fetch_marzban_subscription,
    normalize_plain_sub,
)

log = logging.getLogger(__name__)


async def _resolve_user_sub(token: str) -> tuple[User, str, str] | None:
    """Look up the user by token and return (user, marzban_sub_url, routing_mode).

    Picks any of the user's connections to source the Marzban URL from
    (they all share the same Marzban username = same sub URL). The
    routing_mode comes from the first connection.
    """
    async with SessionLocal() as session:
        u = await session.execute(select(User).where(User.sub_token == token))
        user = u.scalar_one_or_none()
        if user is None:
            return None
        c = await session.execute(
            select(Connection)
            .where(Connection.user_id == user.id)
            .order_by(Connection.id)
            .limit(1)
        )
        conn = c.scalar_one_or_none()
        if conn is None or not conn.subscription_url:
            return None
        return user, conn.subscription_url, conn.routing_mode


async def healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def sub_plain(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    resolved = await _resolve_user_sub(token)
    if resolved is None:
        return web.Response(status=404, text="not found")
    _user, sub_url, _mode = resolved
    try:
        body = await fetch_marzban_subscription(sub_url)
    except Exception as e:  # noqa: BLE001
        log.warning("sub fetch failed for %s: %s", token[:6], e)
        return web.Response(status=502, text="upstream error")
    return web.Response(
        text=normalize_plain_sub(body),
        content_type="text/plain",
        headers={
            "Profile-Update-Interval": "12",
            "Subscription-Userinfo": "upload=0; download=0; total=0; expire=0",
        },
    )


async def sub_singbox(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    resolved = await _resolve_user_sub(token)
    if resolved is None:
        return web.Response(status=404, text="not found")
    _user, sub_url, default_mode = resolved
    mode = request.query.get("mode", default_mode)
    if mode not in ("smart", "full"):
        mode = default_mode
    try:
        body = await fetch_marzban_subscription(sub_url)
        profile = await build_singbox_profile(body, mode=mode)
    except Exception as e:  # noqa: BLE001
        log.warning("sub singbox build failed for %s: %s", token[:6], e)
        return web.Response(status=502, text="upstream error")
    return web.json_response(
        profile,
        headers={"Profile-Update-Interval": "12"},
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/sub/{token}", sub_plain)
    app.router.add_get("/sub/{token}/singbox", sub_singbox)
    return app


# ---------- lifecycle ----------


_runner: web.AppRunner | None = None


async def start_subscription_server() -> None:
    global _runner
    if _runner is not None:
        return
    app = build_app()
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.sub_host, port=settings.sub_port)
    await site.start()
    _runner = runner
    log.info("Subscription server on %s:%d", settings.sub_host, settings.sub_port)


async def stop_subscription_server() -> None:
    global _runner
    if _runner is None:
        return
    await _runner.cleanup()
    _runner = None
    log.info("Subscription server stopped")
