#!/usr/bin/env bash
# Production deploy on Ubuntu 22.04 — first phase: prerequisites + bot stack.
# Marzban / Caddy / AdGuard поднимаются отдельными скриптами.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"

echo "==> [1/5] apt update + base packages"
sudo apt update
sudo apt install -y curl git ufw ca-certificates gnupg lsb-release

echo "==> [2/5] Docker & compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker

echo "==> [3/5] sync project to ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"
sudo rsync -a --delete --exclude='.git' --exclude='postgres-data' \
  --exclude='redis-data' --exclude='caddy-data' --exclude='caddy-config' \
  ./ "${APP_DIR}/"

echo "==> [4/5] .env"
if [ ! -f "${APP_DIR}/.env" ]; then
  sudo cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  echo "!! ВНИМАНИЕ: заполни ${APP_DIR}/.env (BOT_TOKEN, OWNER_ID, SERVER_DOMAIN, MARZBAN_PASSWORD)"
fi

echo "==> [5/5] docker compose up -d (postgres + redis + bot)"
cd "${APP_DIR}"
sudo docker compose up -d --build postgres redis bot
sudo docker compose exec -T bot alembic upgrade head

echo "Done. Дальше:"
echo "  scripts/setup_marzban.sh"
echo "  scripts/setup_caddy.sh"
echo "  scripts/setup_adguard.sh"
