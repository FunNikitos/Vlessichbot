#!/usr/bin/env bash
# Marzban install via официальный install-скрипт.
# Подробности: https://github.com/Gozargah/Marzban
set -euo pipefail

echo "==> Installing Marzban via official script"
sudo bash -c "$(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install

echo "==> Marzban installed. Создай sudo-админа:"
echo "    sudo marzban cli admin create --sudo"
echo
echo "Затем впиши MARZBAN_USERNAME / MARZBAN_PASSWORD в .env."
