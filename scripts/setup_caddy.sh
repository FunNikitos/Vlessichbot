#!/usr/bin/env bash
# Caddy: auto-TLS + fallback site + reverse proxy для подписки/Marzban API/XHTTP.
# Опционально — gRPC over Cloudflare на CF_SUBDOMAIN (генерируем Caddyfile.cf).
#
# Запускать ПОСЛЕ scripts/deploy.sh и scripts/setup_marzban.sh
# (или хотя бы после того, как DNS A-запись SERVER_DOMAIN указывает на этот VPS).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"
cd "${APP_DIR}"

# Sanity: SERVER_DOMAIN должен быть выставлен в .env
if ! grep -q '^SERVER_DOMAIN=' .env || grep -q '^SERVER_DOMAIN=$' .env || grep -q 'vpn.example.com' .env; then
  echo "!! SERVER_DOMAIN в .env не задан или указывает на пример. Поправь и перезапусти." >&2
  exit 1
fi

# CF_SUBDOMAIN опционален. Caddyfile делает import /etc/caddy/Caddyfile.cf.
# Создаём пустой файл если CF_SUBDOMAIN не задан — пустой import = no-op.
CF_SUBDOMAIN="$(grep -E '^CF_SUBDOMAIN=' .env | cut -d= -f2- | tr -d '"' || true)"
mkdir -p caddy
CF_FILE="caddy/Caddyfile.cf"
if [[ -n "${CF_SUBDOMAIN}" ]]; then
  echo "==> Generating ${CF_FILE} for CF_SUBDOMAIN=${CF_SUBDOMAIN}"
  cat > "${CF_FILE}" <<EOF
# CF subdomain (A-запись с CF proxy ON) — VLESS+gRPC через Cloudflare CDN.
${CF_SUBDOMAIN} {
    encode gzip

    @grpc path /vlessich-grpc/* /grpc/*
    handle @grpc {
        reverse_proxy h2c://127.0.0.1:2096
    }

    handle {
        root * /srv
        file_server
        try_files {path} /index.html
    }
}
EOF
else
  echo "==> CF_SUBDOMAIN пуст — gRPC over CF не включаем (пустой ${CF_FILE})"
  : > "${CF_FILE}"
fi

echo "==> docker compose up -d caddy"
docker compose --profile caddy up -d caddy

echo
echo "Caddy запущен. Проверь:"
echo "    curl -I https://\$SERVER_DOMAIN"
echo "    docker compose --profile caddy logs --tail=50 caddy"
