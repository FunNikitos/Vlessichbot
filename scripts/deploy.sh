#!/usr/bin/env bash
# Production deploy on Ubuntu 22.04. Idempotent — гонять можно многократно.
# 1. Базовые пакеты + Docker
# 2. UFW: 22, 80, 443, HONEYPOT_PORT — открыты, остальное закрыто
# 3. Sync ./ → /opt/vlessich
# 4. .env (создаём из .env.example, если ещё нет)
# 5. docker compose up postgres + redis + bot
# 6. alembic upgrade head (сюда же входит backfill sub_token)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"
HONEYPOT_PORT="${HONEYPOT_PORT:-8080}"

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Запусти под root или через sudo." >&2
    exit 1
  fi
}
require_root

echo "==> [1/6] apt + базовые пакеты"
apt update
apt install -y curl git rsync ufw ca-certificates gnupg lsb-release jq

echo "==> [2/6] Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> [3/6] UFW (22, 80, 443, ${HONEYPOT_PORT})"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "${HONEYPOT_PORT}/tcp"
ufw --force enable

echo "==> [4/6] sync ./ → ${APP_DIR}"
mkdir -p "${APP_DIR}"
rsync -a --delete \
  --exclude='.git' --exclude='postgres-data' --exclude='redis-data' \
  --exclude='caddy-data' --exclude='caddy-config' --exclude='__pycache__' \
  ./ "${APP_DIR}/"

echo "==> [5/6] .env"
if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  echo "!! Заполни ${APP_DIR}/.env: BOT_TOKEN, OWNER_ID, SERVER_DOMAIN, MARZBAN_PASSWORD"
  echo "!! После этого перезапусти: cd ${APP_DIR} && docker compose up -d --build bot"
fi

echo "==> [6/6] docker compose up -d (postgres + redis + bot) + alembic upgrade"
cd "${APP_DIR}"
docker compose up -d --build postgres redis
# wait for postgres healthcheck
for i in {1..30}; do
  state=$(docker compose ps --format json postgres 2>/dev/null | jq -r '.[0].Health' || echo "")
  [[ "${state}" == "healthy" ]] && break
  sleep 2
done
docker compose up -d --build bot
sleep 4
docker compose exec -T bot alembic upgrade head || {
  echo "!! alembic upgrade не прошёл. Проверь логи: docker compose logs bot"
  exit 1
}

echo
echo "==> ГОТОВО. Дальше:"
echo "    sudo bash scripts/setup_marzban.sh   # ставит Marzban на хост"
echo "    sudo bash scripts/setup_caddy.sh     # поднимает Caddy с auto-TLS"
echo "    sudo bash scripts/setup_adguard.sh   # (опционально) AdGuard Home"
echo
echo "После этого:"
echo "    1. Создай в Marzban inbound 'VLESS Reality' (порт 443, SNI = SERVER_DOMAIN)"
echo "    2. Заполни MARZBAN_PASSWORD в /opt/vlessich/.env"
echo "    3. docker compose restart bot"
