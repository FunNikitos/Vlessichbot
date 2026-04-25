"""ufw helper — добавляет deny rule для IP. Возвращает (ok, info)."""
from __future__ import annotations

import asyncio
import ipaddress
import logging

log = logging.getLogger(__name__)


def _valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


async def ufw_block(ip: str) -> tuple[bool, str]:
    """ufw deny from <ip>. Требует sudo (или root внутри контейнера с CAP_NET_ADMIN).
    Если ufw недоступен (Windows-разработка) — возвращает (False, info)."""
    if not _valid_ip(ip):
        return False, f"invalid ip: {ip}"
    cmd = ["ufw", "deny", "from", ip]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        info = (stdout or b"").decode(errors="replace").strip()
        if proc.returncode == 0:
            return True, info or "ok"
        return False, f"rc={proc.returncode}: {info}"
    except FileNotFoundError:
        return False, "ufw not found"
    except Exception as e:  # noqa: BLE001
        return False, f"exc: {e}"
