"""Build Hiddify-/Sing-box-compatible client profiles.

We don't reinvent VLESS link parsing. Instead, we fetch Marzban's raw
subscription content (which already contains a working ``vless://`` link
for the user) and wrap it in two outputs:

1. **Plain** (``GET /sub/<token>``): newline-separated ``vless://`` links
   exactly as Marzban returns them. Hiddify and other v2ray-style clients
   poll this URL directly.

2. **Sing-box JSON** (``GET /sub/<token>/singbox``): a full sing-box
   profile with our ``routing.rules`` injected (RU subnets + RU domains
   direct, world via the proxy outbound). Hiddify Next can import this
   to get split-tunnel out of the box.

The design rationale: we *own* the subscription URL distributed to users.
That means we can rotate Reality SNI / port / shortId on the Marzban side
without ever touching the user's client — the next poll picks the new
``vless://`` automatically.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.config import settings
from app.services.routing.split_tunnel import build_routing_rules

log = logging.getLogger(__name__)


def _decode_marzban_body(body: str) -> str:
    """Marzban serves either plain ``vless://`` lines or base64 of the same.
    Detect and return the plain form."""
    text = body.strip()
    if "vless://" in text or "vmess://" in text or "trojan://" in text:
        return text
    # base64 form: pad and decode
    try:
        padded = text + "=" * (-len(text) % 4)
        return base64.b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return text


async def fetch_marzban_subscription(sub_url: str) -> str:
    """GET the raw Marzban subscription body. Returns plain (decoded) text.

    The Marzban subscription URL embeds the user token, so no auth header
    is needed.
    """
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        r = await client.get(sub_url)
        r.raise_for_status()
        return _decode_marzban_body(r.text)


# ---------- Sing-box conversion ----------


def _parse_vless_link(link: str) -> dict[str, Any] | None:
    """Parse a single ``vless://uuid@host:port?params#name`` link into a
    sing-box ``vless`` outbound dict. Returns None on parse failure.

    Supports Reality (``security=reality`` + pbk/sid/sni) and TLS variants;
    unknown stream-settings are passed through best-effort.
    """
    if not link.startswith("vless://"):
        return None
    try:
        parsed = urlparse(link)
        uuid = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or 443
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        name = unquote(parsed.fragment) or "vlessich"
    except Exception:  # noqa: BLE001
        return None
    if not uuid or not host:
        return None

    out: dict[str, Any] = {
        "type": "vless",
        "tag": "proxy",
        "server": host,
        "server_port": int(port),
        "uuid": uuid,
        "flow": params.get("flow", ""),
        "packet_encoding": "xudp",
    }
    security = params.get("security", "").lower()
    sni = params.get("sni") or params.get("host") or host
    fp = params.get("fp", "chrome")
    alpn_raw = params.get("alpn", "")
    alpn = [a for a in alpn_raw.split(",") if a]

    if security == "reality":
        out["tls"] = {
            "enabled": True,
            "server_name": sni,
            "utls": {"enabled": True, "fingerprint": fp},
            "reality": {
                "enabled": True,
                "public_key": params.get("pbk", ""),
                "short_id": params.get("sid", ""),
            },
        }
    elif security == "tls":
        tls: dict[str, Any] = {
            "enabled": True,
            "server_name": sni,
            "utls": {"enabled": True, "fingerprint": fp},
        }
        if alpn:
            tls["alpn"] = alpn
        out["tls"] = tls

    transport_type = params.get("type", "tcp").lower()
    if transport_type == "ws":
        out["transport"] = {
            "type": "ws",
            "path": params.get("path", "/"),
            "headers": {"Host": params.get("host", sni)},
        }
    elif transport_type == "grpc":
        out["transport"] = {
            "type": "grpc",
            "service_name": params.get("serviceName", ""),
        }
    elif transport_type in ("xhttp", "splithttp"):
        out["transport"] = {
            "type": "http",
            "path": params.get("path", "/"),
            "host": [params.get("host", sni)],
        }

    out["_display_name"] = name
    return out


def _singbox_routing(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate Xray-style rules to sing-box rules (best-effort).

    We only emit the constructs we actually generate in
    ``split_tunnel.build_routing_rules``: ``ip`` lists, ``domain`` lists,
    ``geoip:private``, ``geosite:*``, and the catch-all proxy rule.
    """
    out: list[dict[str, Any]] = []
    for r in rules:
        outbound = r.get("outboundTag", "proxy")
        if "ip" in r:
            ips = r["ip"]
            geo = [x.split(":", 1)[1] for x in ips if isinstance(x, str) and x.startswith("geoip:")]
            cidrs = [x for x in ips if isinstance(x, str) and not x.startswith("geoip:")]
            if geo:
                out.append({"geoip": geo, "outbound": outbound})
            if cidrs:
                out.append({"ip_cidr": cidrs, "outbound": outbound})
        elif "domain" in r:
            doms = r["domain"]
            geosites = [x.split(":", 1)[1] for x in doms if isinstance(x, str) and x.startswith("geosite:")]
            plain_dom = [x.split(":", 1)[1] if ":" in x else x for x in doms if isinstance(x, str) and not x.startswith("geosite:")]
            if geosites:
                out.append({"geosite": geosites, "outbound": outbound})
            if plain_dom:
                out.append({"domain_suffix": plain_dom, "outbound": outbound})
        elif r.get("network"):
            out.append({"network": r["network"].split(","), "outbound": outbound})
    return out


async def build_singbox_profile(plain_sub_body: str, mode: str = "smart") -> dict[str, Any]:
    """Compose a complete sing-box config from Marzban's plain sub body."""
    proxies: list[dict[str, Any]] = []
    for line in plain_sub_body.splitlines():
        link = line.strip()
        if not link:
            continue
        parsed = _parse_vless_link(link)
        if parsed:
            proxies.append(parsed)
    if not proxies:
        raise RuntimeError("no parseable vless:// links in subscription")

    primary = proxies[0]
    primary.pop("_display_name", None)

    xray_routing = await build_routing_rules(mode)
    sb_rules = _singbox_routing(xray_routing.get("rules", []))

    profile: dict[str, Any] = {
        "log": {"level": "warn"},
        "dns": {
            "servers": [
                {"tag": "google", "address": "tls://8.8.8.8"},
                {"tag": "ru-direct", "address": "https://77.88.8.8/dns-query", "detour": "direct"},
            ],
            "rules": [
                {"geosite": ["category-ru"], "server": "ru-direct"},
            ],
        },
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "vlessich",
                "inet4_address": "172.19.0.1/30",
                "auto_route": True,
                "strict_route": True,
                "stack": "system",
                "sniff": True,
            }
        ],
        "outbounds": [
            primary,
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
            {"type": "dns", "tag": "dns-out"},
        ],
        "route": {
            "rules": [
                {"protocol": "dns", "outbound": "dns-out"},
                *sb_rules,
            ],
            "auto_detect_interface": True,
            "final": "proxy",
        },
    }
    return profile


# ---------- Plain (Hiddify default) ----------


def normalize_plain_sub(plain_body: str) -> str:
    """Pass-through, but rename links to friendlier display names so users
    see ``vlessich`` instead of Marzban's auto-name in their client."""
    out_lines: list[str] = []
    for line in plain_body.splitlines():
        link = line.strip()
        if not link:
            continue
        if "#" in link:
            base, _ = link.rsplit("#", 1)
            link = f"{base}#vlessich"
        else:
            link = f"{link}#vlessich"
        out_lines.append(link)
    return "\n".join(out_lines) + "\n"


def public_sub_url(token: str) -> str:
    """The URL we hand to the user (lives behind Caddy on server_domain)."""
    port = settings.subscription_public_port
    host = settings.server_domain
    if port == 443:
        return f"https://{host}/sub/{token}"
    return f"https://{host}:{port}/sub/{token}"
