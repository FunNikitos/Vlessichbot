#!/usr/bin/env bash
# Добавляет в Marzban xray_config.json три inbound:
#   1. VLESS+Reality   — порт ${REALITY_PORT} (default 8443), tag "VLESS Reality"
#   2. VLESS+XHTTP     — внутренний порт ${XHTTP_PORT} (default 2087),
#                        наружу через Caddy на 443 path=/xhttp/, tag "VLESS XHTTP"
#   3. VLESS+gRPC (CF) — внутренний порт ${GRPC_PORT} (default 2096),
#                        наружу через ${CF_SUBDOMAIN} (с CF proxy ON) path=/grpc,
#                        tag "VLESS gRPC CF"
#
# Идемпотентен — запускать можно повторно. Существующие inbound с теми же
# тегами обновляются (Private key / Public key — генерируются один раз
# и сохраняются в /var/lib/marzban/reality.keys).
set -euo pipefail

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Запусти под root или через sudo." >&2
    exit 1
  fi
}
require_root

XRAY_CFG="${XRAY_CFG:-/var/lib/marzban/xray_config.json}"
KEYS_FILE="${KEYS_FILE:-/var/lib/marzban/reality.keys}"

REALITY_PORT="${REALITY_PORT:-8443}"
XHTTP_PORT="${XHTTP_PORT:-2087}"
GRPC_PORT="${GRPC_PORT:-2096}"

REALITY_DEST="${REALITY_DEST:-www.microsoft.com:443}"
REALITY_SNI="${REALITY_SNI:-www.microsoft.com}"

if [[ ! -f "${XRAY_CFG}" ]]; then
  echo "!! ${XRAY_CFG} не найден. Сначала установи Marzban (scripts/setup_marzban.sh)." >&2
  exit 1
fi

echo "==> Генерация Reality keypair (только при первом запуске)"
if [[ ! -f "${KEYS_FILE}" ]]; then
  KEYS_RAW="$(docker exec marzban-marzban-1 xray x25519)"
  PRIV="$(echo "${KEYS_RAW}" | awk '/Private key:/ {print $3}')"
  PUB="$(echo "${KEYS_RAW}" | awk '/Public key:/ {print $3}')"
  SHORTID="$(openssl rand -hex 8)"
  cat > "${KEYS_FILE}" <<EOF
PRIV=${PRIV}
PUB=${PUB}
SHORTID=${SHORTID}
EOF
  chmod 600 "${KEYS_FILE}"
fi
# shellcheck disable=SC1090
source "${KEYS_FILE}"
echo "    Public key:  ${PUB}"
echo "    Short ID:    ${SHORTID}"

echo "==> Бэкап ${XRAY_CFG}"
cp "${XRAY_CFG}" "${XRAY_CFG}.bak.$(date +%s)"

echo "==> Патчим xray_config.json (3 inbound)"
TMP="$(mktemp)"
jq \
  --arg priv "${PRIV}" \
  --arg sid "${SHORTID}" \
  --arg sni "${REALITY_SNI}" \
  --arg dest "${REALITY_DEST}" \
  --argjson rport "${REALITY_PORT}" \
  --argjson xport "${XHTTP_PORT}" \
  --argjson gport "${GRPC_PORT}" \
'
  # Сохраняем все inbound, кроме наших трёх (мы их перезапишем)
  .inbounds = (
    [ .inbounds[] | select(.tag != "VLESS Reality" and .tag != "VLESS XHTTP" and .tag != "VLESS gRPC CF") ]
    + [
      {
        "tag": "VLESS Reality",
        "listen": "0.0.0.0",
        "port": $rport,
        "protocol": "vless",
        "settings": { "clients": [], "decryption": "none" },
        "streamSettings": {
          "network": "tcp",
          "security": "reality",
          "realitySettings": {
            "show": false,
            "dest": $dest,
            "xver": 0,
            "serverNames": [$sni],
            "privateKey": $priv,
            "shortIds": [$sid]
          }
        },
        "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
      },
      {
        "tag": "VLESS XHTTP",
        "listen": "127.0.0.1",
        "port": $xport,
        "protocol": "vless",
        "settings": { "clients": [], "decryption": "none" },
        "streamSettings": {
          "network": "xhttp",
          "security": "none",
          "xhttpSettings": {
            "host": "",
            "path": "/xhttp",
            "mode": "auto"
          }
        },
        "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
      },
      {
        "tag": "VLESS gRPC CF",
        "listen": "127.0.0.1",
        "port": $gport,
        "protocol": "vless",
        "settings": { "clients": [], "decryption": "none" },
        "streamSettings": {
          "network": "grpc",
          "security": "none",
          "grpcSettings": {
            "serviceName": "vlessich-grpc",
            "multiMode": true
          }
        },
        "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] }
      }
    ]
  )
' "${XRAY_CFG}" > "${TMP}"
mv "${TMP}" "${XRAY_CFG}"

echo "    Inbound теги:"
jq -r '.inbounds[].tag' "${XRAY_CFG}" | sed 's/^/      /'

echo "==> Рестарт Marzban"
( cd /opt/marzban && docker compose restart )

echo
echo "==> ГОТОВО."
echo
echo "Reality keys (для Marzban Hosts):"
echo "    Public key:  ${PUB}"
echo "    Short ID:    ${SHORTID}"
echo
echo "Дальше — открой http://127.0.0.1:8000/dashboard/ (через ssh -L) и создай 3 Host:"
echo
echo "  1) VLESS Reality"
echo "       Address  = \$SERVER_DOMAIN (или public IP)"
echo "       Port     = ${REALITY_PORT}"
echo "       SNI      = ${REALITY_SNI}"
echo "       Security = reality"
echo "       Public Key  = ${PUB}"
echo "       Short ID    = ${SHORTID}"
echo "       Fingerprint = chrome"
echo "       Flow        = xtls-rprx-vision"
echo
echo "  2) VLESS XHTTP"
echo "       Address     = \$SERVER_DOMAIN"
echo "       Port        = 443"
echo "       SNI         = \$SERVER_DOMAIN"
echo "       Path        = /xhttp"
echo "       Security    = tls"
echo "       Network     = xhttp"
echo "       ALPN        = h2"
echo "       Fingerprint = chrome"
echo
echo "  3) VLESS gRPC CF"
echo "       Address       = \$CF_SUBDOMAIN  (например cf.fi3.ctom.online, A-запись с CF proxy ON)"
echo "       Port          = 443"
echo "       SNI           = \$CF_SUBDOMAIN"
echo "       Network       = grpc"
echo "       gRPC service  = vlessich-grpc"
echo "       Security      = tls"
echo "       Fingerprint   = chrome"
