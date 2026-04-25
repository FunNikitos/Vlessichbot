"""Multi-protocol prober — labels and constants.

Реальный прозвон будет в фазе мониторинга. Здесь — единый источник
названий протоколов и иконок для /status."""
from __future__ import annotations

# tag → human-readable label
PROTO_LABELS: dict[str, str] = {
    "vless_reality": "🟢 VLESS+Reality",
    "vless_xhttp": "🟡 VLESS+XHTTP",
    "vless_grpc_cf": "🔵 VLESS+gRPC (CF)",
}
