"""Split-tunnel routing rules.

Generates Hiddify-/Xray-compatible JSON ``routing.rules`` arrays:

- ``smart`` mode (default): RU subnets + RU domains -> direct,
  everything else -> proxy. Ensures Tinkoff/Sber/госуслуги stay on the
  home ISP IP (banks geofence VPN exits).
- ``full`` mode: everything via proxy (no exceptions).

The output is consumed by the subscription HTTP endpoint that wraps
Marzban's raw VLESS link with a Hiddify-compatible profile envelope.
"""
from __future__ import annotations

from typing import Any

from app.services.routing.antifilter import get_cached_subnets

# Hardcoded RU domain shortlist for direct routing. CIDR list comes from
# antifilter; domains are kept here because antifilter is IP-only.
RU_DIRECT_DOMAINS: tuple[str, ...] = (
    "geosite:category-ru",
    "domain:ru",
    "domain:рф",
    "domain:tinkoff.ru",
    "domain:sberbank.ru",
    "domain:vtb.ru",
    "domain:alfabank.ru",
    "domain:gosuslugi.ru",
    "domain:nalog.ru",
    "domain:mos.ru",
    "domain:yandex.ru",
    "domain:vk.com",
    "domain:ok.ru",
    "domain:mail.ru",
    "domain:rt.ru",
    "domain:mts.ru",
    "domain:beeline.ru",
    "domain:megafon.ru",
    "domain:tele2.ru",
    "domain:wildberries.ru",
    "domain:ozon.ru",
    "domain:avito.ru",
    "domain:dns-shop.ru",
    "domain:rambler.ru",
    "domain:lenta.ru",
    "domain:rbc.ru",
    "domain:kinopoisk.ru",
    "domain:ivi.ru",
    "domain:2gis.ru",
)


async def build_routing_rules(mode: str = "smart") -> dict[str, Any]:
    """Return Xray-style ``routing`` block ready to embed in client config."""
    if mode == "full":
        return {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "outboundTag": "proxy", "network": "tcp,udp"},
            ],
        }

    # smart: RU stays direct, world goes through proxy
    subnets = await get_cached_subnets()
    rules: list[dict[str, Any]] = [
        # Private/loopback always direct
        {
            "type": "field",
            "outboundTag": "direct",
            "ip": ["geoip:private"],
        },
    ]
    if subnets:
        rules.append(
            {"type": "field", "outboundTag": "direct", "ip": subnets}
        )
    rules.append(
        {
            "type": "field",
            "outboundTag": "direct",
            "domain": list(RU_DIRECT_DOMAINS),
        }
    )
    rules.append(
        {"type": "field", "outboundTag": "proxy", "network": "tcp,udp"}
    )
    return {"domainStrategy": "IPIfNonMatch", "rules": rules}
