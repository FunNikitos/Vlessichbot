# Vlessich-1 — деплой на боевой сервер

VPS на Ubuntu 22.04, домен с A-записью на этот VPS, токен от @BotFather и твой Telegram ID.

## Шаг 1 — DNS

В панели регистратора (или Cloudflare):

1. **Главный домен** (`vpn.example.com`) — A-запись на IP сервера, **CF proxy OFF** (серое облако).
   Reality требует прямого доступа, без CF между.
2. **CF subdomain** (`cf.vpn.example.com`) — A-запись на тот же IP, **CF proxy ON** (оранжевое облако).
   Используется для VLESS+gRPC fallback через Cloudflare CDN.

## Шаг 2 — Получить код

```bash
ssh root@SERVER_IP
cd /root
git clone https://github.com/FunNikitos/Vlessichbot.git vlessich-1
cd vlessich-1
```

## Шаг 3 — Запустить deploy.sh

Idempotent: можно гонять много раз. Что делает:

1. apt + Docker + socat + cron
2. UFW: открыто 22/80/443/8443/2087/8080; 8000 разрешён только с docker subnets
3. Sync `./` → `/opt/vlessich`
4. `.env` (создаёт из шаблона, если нет)
5. postgres + redis + bot + alembic upgrade
6. socat-форвардер `docker0:8000 → 127.0.0.1:8000` (Marzban API доступен боту)
7. cron — ежедневный бэкап в 03:00 (`/opt/backups`, retention 14 дней)

```bash
sudo bash scripts/deploy.sh
```

После первого прогона он остановится на сообщении про `.env`.

## Шаг 4 — Заполнить .env

```bash
sudo nano /opt/vlessich/.env
```

Минимум:

```env
BOT_TOKEN=123456:AAA...
OWNER_ID=123456789
SERVER_DOMAIN=vpn.example.com         # главный домен (CF proxy OFF)
CF_SUBDOMAIN=cf.vpn.example.com       # для gRPC fallback (CF proxy ON)
MARZBAN_PASSWORD=                     # заполнишь после Шага 5
```

## Шаг 5 — Поставить Marzban

```bash
sudo bash /opt/vlessich/scripts/setup_marzban.sh
sudo marzban cli admin create --sudo
```

Прописать пароль в `/opt/vlessich/.env` (`MARZBAN_PASSWORD=...`).

Включить абсолютный subscription URL в Marzban:

```bash
echo 'XRAY_SUBSCRIPTION_URL_PREFIX="http://host.docker.internal:8000"' >> /opt/marzban/.env
cd /opt/marzban && sudo docker compose down && sudo docker compose up -d
```

## Шаг 6 — Создать inbounds (Reality + XHTTP + gRPC)

```bash
sudo bash /opt/vlessich/scripts/setup_inbounds.sh
```

Скрипт:
- сгенерирует Reality keypair (один раз, сохранит в `/var/lib/marzban/reality.keys`)
- добавит в `xray_config.json` три inbound: `VLESS Reality` (8443), `VLESS XHTTP` (127.0.0.1:2087), `VLESS gRPC CF` (127.0.0.1:2096)
- рестартит Marzban
- выведет Public Key и Short ID

Запомни public key и short_id — будут нужны при создании Hosts в дашборде.

## Шаг 7 — Поднять Caddy

```bash
sudo bash /opt/vlessich/scripts/setup_caddy.sh
```

Caddy получает TLS на `SERVER_DOMAIN` (без CF) и `CF_SUBDOMAIN` (с CF — для gRPC он использует Origin Cert, см. ниже).

Если `CF_SUBDOMAIN` не задан — gRPC inbound будет работать, но без CF-проксирования.

## Шаг 8 — Создать Hosts в Marzban-дашборде

Открой дашборд через SSH-туннель:

```bash
# на твоей локалке
ssh -L 8000:localhost:8000 root@SERVER_IP
# открой http://127.0.0.1:8000/dashboard/
```

В разделе **Hosts** создай 3 хоста (по одному на каждый inbound):

### 1. VLESS Reality
| Поле | Значение |
|---|---|
| Inbound | `VLESS Reality` |
| Remark | `Vlessich Reality` |
| Address | `SERVER_DOMAIN` |
| Port | `8443` |
| SNI | `www.microsoft.com` |
| Public Key | _из вывода setup_inbounds.sh_ |
| Short ID | _из вывода setup_inbounds.sh_ |
| Fingerprint | `chrome` |
| ALPN | `h2,http/1.1` |
| Flow | `xtls-rprx-vision` |

### 2. VLESS XHTTP
| Поле | Значение |
|---|---|
| Inbound | `VLESS XHTTP` |
| Remark | `Vlessich XHTTP` |
| Address | `SERVER_DOMAIN` |
| Port | `443` |
| SNI | `SERVER_DOMAIN` |
| Path | `/xhttp` |
| Network | `xhttp` |
| Security | `tls` |
| Fingerprint | `chrome` |
| ALPN | `h2` |

### 3. VLESS gRPC (CF)
| Поле | Значение |
|---|---|
| Inbound | `VLESS gRPC CF` |
| Remark | `Vlessich gRPC CF` |
| Address | `CF_SUBDOMAIN` |
| Port | `443` |
| SNI | `CF_SUBDOMAIN` |
| gRPC service | `vlessich-grpc` |
| Network | `grpc` |
| Security | `tls` |
| Fingerprint | `chrome` |

## Шаг 9 — Перезапуск бота и проверка

```bash
cd /opt/vlessich
sudo docker compose restart bot
```

В Telegram:
- `/start` → должен ответить
- `/admin` → админ-меню (как owner)
- `/newconfig` → подписка `https://SERVER_DOMAIN/sub/<token>`
- открой ссылку в браузере → должно вернуть `vless://...` строки (по одной на каждый Host)

---

## Что куда смотрит

```
/opt/vlessich/                       — код + docker-compose
/opt/vlessich/.env                   — секреты
/opt/vlessich/postgres-data/         — БД бота
/opt/vlessich/caddy-data/            — TLS сертификаты Caddy
/var/lib/marzban/                    — Marzban DB + xray_config.json
/var/lib/marzban/reality.keys        — Reality keypair (private + public + short_id)
/opt/marzban/                        — Marzban docker-compose + .env
/etc/systemd/system/marzban-proxy.service — socat docker0:8000→127.0.0.1:8000
/usr/local/bin/vlessich-backup.sh    — daily backup
/opt/backups/                        — бэкапы (14 дней)
```

Порты на VPS:
- `22` ssh
- `80, 443` Caddy (TLS)
- `8443` xray VLESS+Reality
- `8080` honeypot
- `2087, 2096` xray xhttp/grpc (только localhost, через Caddy)
- `8000` Marzban API (только docker subnets через UFW + socat-форвардер)
- `8081` subscription server (только localhost, через Caddy)

## Бэкапы

Скрипт `scripts/backup.sh` запускается ежедневно cron'ом в 03:00:
- Marzban DB + xray_config + .env
- Postgres dump
- Caddy data (TLS-сертификаты)
- `.env` бота

Хранится 14 дней. Чтобы перенести бэкап на другой VPS, скопируй `/opt/backups/*` целиком.

Ручной запуск:
```bash
sudo /usr/local/bin/vlessich-backup.sh
ls -lh /opt/backups/
```

## Восстановление из бэкапа

```bash
# Marzban DB
sudo systemctl stop marzban || true
sudo cd /opt/marzban && sudo docker compose down
sudo tar xzf /opt/backups/marzban-YYYYMMDD-HHMM.tgz -C /
sudo cd /opt/marzban && sudo docker compose up -d

# Postgres
sudo cd /opt/vlessich && sudo docker compose stop bot
gunzip -c /opt/backups/vlessich-db-YYYYMMDD-HHMM.sql.gz \
  | sudo docker compose exec -T postgres psql -U vlessich vlessich
sudo docker compose start bot

# Caddy data (TLS-сертификаты — чтобы Let's Encrypt не выпускал заново)
sudo tar xzf /opt/backups/caddy-YYYYMMDD-HHMM.tgz -C /
```

## Обновление кода

```bash
cd /root/vlessich-1
git pull
sudo bash scripts/deploy.sh
```

## Если что-то сломалось

```bash
# Логи
sudo docker compose -f /opt/vlessich/docker-compose.yml logs --tail=200 bot
sudo docker compose -f /opt/vlessich/docker-compose.yml logs --tail=100 caddy
sudo docker compose -f /opt/marzban/docker-compose.yml logs --tail=100 marzban
sudo journalctl -u marzban-proxy -n 50

# Перезапуск
sudo systemctl restart marzban-proxy
sudo docker compose -f /opt/vlessich/docker-compose.yml restart bot
sudo docker compose -f /opt/marzban/docker-compose.yml restart marzban

# Marzban API доступен из бота?
sudo docker compose -f /opt/vlessich/docker-compose.yml exec -T bot \
  curl -sI --max-time 5 http://host.docker.internal:8000/api/system
# 401 = всё ок (нет токена). Timeout/000 = чини socat / UFW.
```
