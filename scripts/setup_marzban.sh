#!/usr/bin/env bash
# Marzban install via официальный install-скрипт + production-патчи.
# Подробности: https://github.com/Gozargah/Marzban
set -euo pipefail

MARZBAN_DIR="${MARZBAN_DIR:-/opt/marzban}"

echo "==> Installing Marzban via official script (если ещё не установлен)"
if [[ ! -f "${MARZBAN_DIR}/.env" ]]; then
  sudo bash -c "$(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install
fi

echo "==> Patching ${MARZBAN_DIR}/.env"
ENV_FILE="${MARZBAN_DIR}/.env"

# 1) XRAY_SUBSCRIPTION_URL_PREFIX — нужен боту, чтобы links возвращались с
#    абсолютным URL (subscription proxy в нашем aiohttp-сервере подменит host).
if ! grep -qE '^XRAY_SUBSCRIPTION_URL_PREFIX=' "${ENV_FILE}"; then
  echo 'XRAY_SUBSCRIPTION_URL_PREFIX="http://host.docker.internal:8000"' >> "${ENV_FILE}"
fi

# 2) UVICORN_HOST=0.0.0.0 — Marzban всё равно даунгрейдит до 127.0.0.1 без SSL,
#    но для будущей поддержки SSL пишем заранее. Реальный доступ из docker —
#    через socat-форвардер (см. scripts/marzban-proxy.service).
if ! grep -qE '^UVICORN_HOST=' "${ENV_FILE}"; then
  echo 'UVICORN_HOST=0.0.0.0' >> "${ENV_FILE}"
fi

echo "==> Restart Marzban (применяем .env-патчи)"
( cd "${MARZBAN_DIR}" && sudo docker compose down && sudo docker compose up -d )

echo
echo "==> Marzban установлен. Дальше:"
echo "    sudo marzban cli admin create --sudo  # создать sudo-админа"
echo "    sudo nano /opt/vlessich/.env          # вписать MARZBAN_USERNAME / MARZBAN_PASSWORD"
echo "    sudo bash scripts/setup_inbounds.sh   # добавить VLESS Reality + XHTTP + gRPC"
