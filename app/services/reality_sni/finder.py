"""Reality SNI Finder.

Probes a list of candidate domains for two key Reality requirements:
1. Server speaks TLS 1.3 (Reality steals real CertificateVerify from it)
2. Server negotiates HTTP/2 via ALPN (h2)

Domains that pass both checks are persisted into ``sni_donors`` with a
freshness ``last_checked_at`` and integer ``score`` (currently boolean
sum, room to grow with latency-weighting).

Used by ``rotate_sni`` to pick a fresh masquerade target. Run on a
weekly schedule and on-demand via /findsni.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SniDonor

log = logging.getLogger(__name__)


# Curated default seed list: large CDN/edge fronts known to support TLS1.3 + h2.
# Real production should pull this from `scripts/reality_sni_finder.sh` cache.
DEFAULT_SEEDS: tuple[str, ...] = (
    "www.microsoft.com",
    "www.cloudflare.com",
    "www.amazon.com",
    "www.apple.com",
    "github.com",
    "www.bing.com",
    "yandex.ru",
    "habr.com",
    "vk.com",
    "www.tinkoff.ru",
    "ya.ru",
    "telegram.org",
    "www.icloud.com",
    "www.dropbox.com",
    "www.intel.com",
)


async def _probe_one(domain: str, *, timeout: float = 5.0) -> tuple[bool, bool]:
    """Return (has_tls13, has_h2) for ``domain`` over port 443.

    Failure on connect/handshake yields (False, False); never raises.
    """

    def _sync() -> tuple[bool, bool]:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        try:
            with socket.create_connection((domain, 443), timeout=timeout) as raw:
                with ctx.wrap_socket(raw, server_hostname=domain) as tls:
                    proto = (tls.version() or "").upper()
                    alpn = (tls.selected_alpn_protocol() or "").lower()
                    return (proto == "TLSV1.3", alpn == "h2")
        except (OSError, ssl.SSLError, socket.timeout):
            return (False, False)

    try:
        return await asyncio.wait_for(asyncio.to_thread(_sync), timeout=timeout + 2)
    except asyncio.TimeoutError:
        return (False, False)


async def probe_domains(
    session: AsyncSession,
    domains: Iterable[str] | None = None,
    *,
    concurrency: int = 8,
) -> dict[str, tuple[bool, bool, int]]:
    """Probe ``domains`` (or DEFAULT_SEEDS) and upsert results into ``sni_donors``.

    Returns mapping ``{domain: (has_tls13, has_h2, score)}``.
    """
    targets = list(dict.fromkeys(domains or DEFAULT_SEEDS))  # dedup, keep order
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(d: str) -> tuple[str, bool, bool]:
        async with sem:
            tls13, h2 = await _probe_one(d)
            return d, tls13, h2

    results = await asyncio.gather(*[_bounded(d) for d in targets])
    now = datetime.now(timezone.utc)
    out: dict[str, tuple[bool, bool, int]] = {}

    existing = await session.execute(
        select(SniDonor).where(SniDonor.domain.in_(targets))
    )
    by_domain = {row.domain: row for row in existing.scalars().all()}

    for domain, tls13, h2 in results:
        score = (1 if tls13 else 0) + (1 if h2 else 0)
        out[domain] = (tls13, h2, score)
        donor = by_domain.get(domain)
        if donor is None:
            donor = SniDonor(domain=domain)
            session.add(donor)
        donor.has_tls13 = tls13
        donor.has_h2 = h2
        donor.score = score
        donor.last_checked_at = now

    await session.commit()
    log.info(
        "SNI finder: probed=%d, eligible=%d (tls1.3+h2)",
        len(results),
        sum(1 for v in out.values() if v[2] >= 2),
    )
    return out


async def get_top_donors(session: AsyncSession, limit: int = 10) -> list[str]:
    """Top donors by score desc, then freshness desc — eligible only (score>=2)."""
    result = await session.execute(
        select(SniDonor)
        .where(SniDonor.score >= 2)
        .order_by(SniDonor.score.desc(), SniDonor.last_checked_at.desc())
        .limit(limit)
    )
    return [d.domain for d in result.scalars().all()]
