#!/usr/bin/env bash
# Caddy: TLS + fallback site + /sub/* proxy.
# Запускается ПОСЛЕ scripts/deploy.sh и ПОСЛЕ scripts/setup_marzban.sh
# (или хотя бы после того, как DNS A-запись SERVER_DOMAIN указывает на этот VPS).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"
cd "${APP_DIR}"

# Sanity: SERVER_DOMAIN должен быть выставлен в .env (Caddyfile его подставит)
if ! grep -q '^SERVER_DOMAIN=' .env || grep -q '^SERVER_DOMAIN=$' .env || grep -q 'vpn.example.com' .env; then
  echo "!! SERVER_DOMAIN в .env не задан или указывает на пример. Поправь и перезапусти." >&2
  exit 1
fi

echo "==> docker compose up -d caddy (profile=caddy, network=host)"
docker compose --profile caddy up -d caddy

echo
echo "Caddy запущен. Должен сам выпустить TLS-сертификат при первом обращении."
echo "Проверь:"
echo "    curl -I https://\$SERVER_DOMAIN"
echo "    docker compose logs --tail=50 caddy"
