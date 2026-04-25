#!/usr/bin/env bash
# AdGuard Home: блокирует рекламу/трекеры на стороне VPN-сервера.
# Используем официальный установщик.
set -euo pipefail

echo "==> Installing AdGuard Home"
curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sudo sh -s -- -v

echo "==> AdGuard установлен. Открой http://<server>:3000 для первичной настройки."
echo "В Marzban inbound добавь dns=127.0.0.1 после настройки AdGuard."
