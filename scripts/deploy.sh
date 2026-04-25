#!/usr/bin/env bash
# Production deploy on Ubuntu 22.04. Idempotent — гонять можно многократно.
#
#  1. Базовые пакеты + Docker
#  2. UFW: 22, 80, 443, 8443 (Reality), 2087 (XHTTP), HONEYPOT_PORT — открыты;
#     8000 (Marzban API) разрешён только с docker subnets.
#  3. Sync ./ → /opt/vlessich
#  4. .env (создаём из .env.example, если ещё нет)
#  5. docker compose up postgres + redis + bot
#  6. alembic upgrade head
#  7. socat-форвардер docker0:8000 → 127.0.0.1:8000 (Marzban API доступен из контейнеров)
#  8. cron: ежедневный бэкап в 03:00
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vlessich}"
HONEYPOT_PORT="${HONEYPOT_PORT:-8080}"
REALITY_PORT="${REALITY_PORT:-8443}"
XHTTP_PORT="${XHTTP_PORT:-2087}"

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Запусти под root или через sudo." >&2
    exit 1
  fi
}
require_root

echo "==> [1/8] apt + базовые пакеты"
apt update
apt install -y curl git rsync ufw ca-certificates gnupg lsb-release jq nano cron socat

echo "==> [2/8] Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> [3/8] UFW (22, 80, 443, ${REALITY_PORT}, ${XHTTP_PORT}, ${HONEYPOT_PORT})"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "${REALITY_PORT}/tcp"      # VLESS+Reality
ufw allow "${XHTTP_PORT}/tcp"        # VLESS+XHTTP fallback
ufw allow "${HONEYPOT_PORT}/tcp"     # honeypot

# Marzban API на :8000 — НЕ публичный, открываем только для docker subnets,
# чтобы бот в bridge-сети мог достучаться через host.docker.internal:8000.
ufw allow from 172.17.0.0/16 to any port 8000 proto tcp
ufw allow from 172.18.0.0/16 to any port 8000 proto tcp
ufw allow from 172.19.0.0/16 to any port 8000 proto tcp

ufw --force enable

echo "==> [4/8] sync ./ → ${APP_DIR}"
mkdir -p "${APP_DIR}"
# CRITICAL: --exclude='.env' — иначе rsync --delete сотрёт боевой .env,
# потому что в репо его нет (есть только .env.example).
rsync -a --delete \
  --exclude='.git' --exclude='.env' \
  --exclude='postgres-data' --exclude='redis-data' \
  --exclude='caddy-data' --exclude='caddy-config' --exclude='__pycache__' \
  ./ "${APP_DIR}/"

echo "==> [5/8] .env"
if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  echo "!! Заполни ${APP_DIR}/.env: BOT_TOKEN, OWNER_ID, SERVER_DOMAIN, MARZBAN_PASSWORD"
  echo "!! После этого перезапусти этот скрипт."
fi

echo "==> [6/8] docker compose up -d (postgres + redis + bot) + alembic upgrade"
cd "${APP_DIR}"
docker compose up -d --build postgres redis
# Ждём healthcheck postgres. Docker 25+ возвращает NDJSON — используем docker inspect.
for i in {1..30}; do
  state=$(docker inspect --format '{{.State.Health.Status}}' vlessich-postgres-1 2>/dev/null || echo "")
  [[ "${state}" == "healthy" ]] && break
  sleep 2
done

# Миграции в одноразовом контейнере (бот может быть в crash-loop если БД пуста).
docker compose run --rm --no-deps bot alembic upgrade head

docker compose up -d --build bot

echo "==> [7/8] socat-форвардер docker0:8000 → 127.0.0.1:8000 (Marzban API)"
# Marzban принудительно слушает 127.0.0.1:8000 если нет SSL. Чтобы бот в
# bridge-сети мог обращаться на host.docker.internal:8000 (= docker0 = 172.17.0.1),
# поднимаем socat-форвардер. UFW уже разрешает только docker subnets.
install -m 0644 scripts/marzban-proxy.service /etc/systemd/system/marzban-proxy.service
systemctl daemon-reload
systemctl enable --now marzban-proxy
systemctl reset-failed marzban-proxy 2>/dev/null || true
systemctl restart marzban-proxy

echo "==> [8/8] cron — ежедневный бэкап в 03:00 (/opt/backups, retention 14d)"
systemctl enable --now cron
install -m 0755 scripts/backup.sh /usr/local/bin/vlessich-backup.sh
# Идемпотентно: убираем старую запись, добавляем актуальную.
( crontab -l 2>/dev/null | grep -v 'vlessich-backup.sh' ; \
  echo "0 3 * * * /usr/local/bin/vlessich-backup.sh >> /var/log/vlessich-backup.log 2>&1" \
) | crontab -

echo
echo "==> ГОТОВО."
echo
echo "Дальше:"
echo "    sudo bash scripts/setup_marzban.sh   # ставит Marzban на хост"
echo "    sudo bash scripts/setup_caddy.sh     # поднимает Caddy с auto-TLS"
echo
echo "После Marzban:"
echo "    1. sudo marzban cli admin create --sudo  # запомни пароль"
echo "    2. Заполни MARZBAN_PASSWORD в /opt/vlessich/.env"
echo "    3. sudo bash scripts/setup_inbounds.sh  # добавит VLESS Reality + XHTTP + gRPC"
echo "    4. cd /opt/vlessich && docker compose restart bot"
