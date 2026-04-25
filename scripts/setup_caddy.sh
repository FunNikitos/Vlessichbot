#!/usr/bin/env bash
# Caddy: TLS + fallback site + /sub/ proxy.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"
cd "${APP_DIR}"

echo "==> docker compose up -d caddy (profile=caddy)"
sudo docker compose --profile caddy up -d caddy
echo "Caddy запущен. Убедись, что DNS A-запись SERVER_DOMAIN указывает на этот VPS."
