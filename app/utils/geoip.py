"""Best-effort country lookup for an IP via ip-api.com (no key, free).
Failures are silent — country is just enrichment data, not critical."""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

_TIMEOUT = 4.0


async def lookup_country(ip: str) -> str | None:
    if _is_local(ip):
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}", params={"fields": "country,countryCode,status"})
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("status") != "success":
            return None
        cc = data.get("countryCode") or ""
        country = data.get("country") or ""
        if cc and country:
            return f"{country} ({cc})"
        return country or cc or None
    except Exception as e:  # noqa: BLE001
        log.debug("geoip lookup failed for %s: %s", ip, e)
        return None


def _is_local(ip: str) -> bool:
    return (
        ip.startswith("10.")
        or ip.startswith("127.")
        or ip.startswith("192.168.")
        or ip.startswith("172.")  # rough — сетевой диапазон 172.16-172.31
        or ip == "::1"
        or ip.startswith("fe80:")
    )
