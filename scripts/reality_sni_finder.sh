#!/usr/bin/env bash
# Reality SNI Finder: ищет «соседей» по AS нашего хостера, у которых
# поднят TLS 1.3 + HTTP/2, чтобы маскироваться под их домен.
# Использует официальный инструмент XTLS.
set -euo pipefail

if ! command -v go >/dev/null 2>&1; then
  echo "==> Installing Go"
  sudo apt install -y golang-go
fi

WORKDIR="${WORKDIR:-/tmp/reality-sni-finder}"
rm -rf "${WORKDIR}"
git clone https://github.com/XTLS/RealityScanner.git "${WORKDIR}" || \
  git clone https://github.com/XTLS/Xray-examples.git "${WORKDIR}"

echo "==> Build & run"
cd "${WORKDIR}"
go build -o reality-finder ./... || true

SERVER_IP="${1:-}"
if [ -z "${SERVER_IP}" ]; then
  echo "Usage: $0 <server_ip>"
  exit 1
fi
./reality-finder "${SERVER_IP}" 443 | tee /tmp/sni_candidates.txt
echo "==> Кандидаты сохранены в /tmp/sni_candidates.txt"
