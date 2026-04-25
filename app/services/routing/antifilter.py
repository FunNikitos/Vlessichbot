"""Antifilter RU subnet cache.

Downloads the line-separated CIDR list from antifilter.download once
per ``ANTIFILTER_REFRESH_HOURS`` and caches it in Redis under a single
key as JSON. This lets ``split_tunnel`` and the subscription endpoint
generate routing rules without hitting the upstream every request.

Cache shape:
- Key:  ``antifilter:ru_subnets``
- Type: STRING (JSON array of CIDRs)
- TTL:  ``ANTIFILTER_REFRESH_HOURS * 3600 * 2`` (double of refresh, soft expiry)

Failure to refresh is non-fatal: stale cache is preferred to no cache.
"""
from __future__ import annotations

import ipaddress
import json
import logging

import httpx

from app.config import settings
from app.redis import get_redis
from app.utils.errors import log_error

log = logging.getLogger(__name__)

REDIS_KEY = "antifilter:ru_subnets"


def _parse_subnets(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
        except ValueError:
            continue
        out.append(net.with_prefixlen)
    return out


async def refresh_cache() -> int:
    """Fetch upstream list and overwrite Redis cache. Returns subnet count."""
    url = settings.antifilter_url
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            text = r.text
    except Exception as e:  # noqa: BLE001
        await log_error(source="antifilter.refresh", message=str(e), exc=e)
        log.warning("antifilter refresh failed: %s", e)
        return 0

    subnets = _parse_subnets(text)
    if not subnets:
        log.warning("antifilter returned empty/unparseable list (%d bytes)", len(text))
        return 0

    redis = get_redis()
    ttl = max(settings.antifilter_refresh_hours, 1) * 3600 * 2
    await redis.set(REDIS_KEY, json.dumps(subnets), ex=ttl)
    log.info("antifilter cache: %d subnets stored (ttl=%ds)", len(subnets), ttl)
    return len(subnets)


async def get_cached_subnets() -> list[str]:
    """Return cached list, or refresh on miss. Empty list on total failure."""
    redis = get_redis()
    raw = await redis.get(REDIS_KEY)
    if raw:
        try:
            return list(json.loads(raw))
        except json.JSONDecodeError:
            log.warning("antifilter cache corrupted, refetching")
    await refresh_cache()
    raw = await redis.get(REDIS_KEY)
    if raw:
        try:
            return list(json.loads(raw))
        except json.JSONDecodeError:
            return []
    return []
