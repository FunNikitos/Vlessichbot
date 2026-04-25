#!/usr/bin/env bash
# Daily backup: Marzban DB+xray, vlessich Postgres dump, Caddy data, .env files.
# Установка через scripts/deploy.sh (cron 03:00).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
APP_DIR="${APP_DIR:-/opt/vlessich}"
MARZBAN_DIR="${MARZBAN_DIR:-/opt/marzban}"

mkdir -p "${BACKUP_DIR}"
DATE="$(date +%Y%m%d-%H%M)"

# 1) Marzban: SQLite + xray_config.json + .env
if [[ -d /var/lib/marzban ]]; then
  tar czf "${BACKUP_DIR}/marzban-${DATE}.tgz" \
    /var/lib/marzban/db.sqlite3 \
    /var/lib/marzban/xray_config.json \
    "${MARZBAN_DIR}/.env" \
    "${MARZBAN_DIR}/docker-compose.yml" 2>/dev/null || true
fi

# 2) Vlessich Postgres dump
if [[ -f "${APP_DIR}/docker-compose.yml" ]]; then
  docker compose -f "${APP_DIR}/docker-compose.yml" exec -T postgres \
    pg_dump -U vlessich vlessich 2>/dev/null \
    | gzip > "${BACKUP_DIR}/vlessich-db-${DATE}.sql.gz" || true
fi

# 3) .env файлы
[[ -f "${APP_DIR}/.env" ]] && cp "${APP_DIR}/.env" "${BACKUP_DIR}/vlessich-env-${DATE}"

# 4) Caddy data — TLS-сертификаты
if [[ -d "${APP_DIR}/caddy-data" ]]; then
  tar czf "${BACKUP_DIR}/caddy-${DATE}.tgz" \
    "${APP_DIR}/caddy-data" \
    "${APP_DIR}/caddy-config" 2>/dev/null || true
fi

# 5) Ротация: храним только последние ${KEEP_DAYS} дней
find "${BACKUP_DIR}" -mtime "+${KEEP_DAYS}" -delete

echo "[$(date)] Backup OK: ${BACKUP_DIR}/*-${DATE}.*"
