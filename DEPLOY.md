# Vlessich-1 — деплой на боевой сервер

Кратко: один VPS на Ubuntu 22.04, домен с A-записью на этот VPS, токен от @BotFather и твой Telegram ID.

## Шаг 0 — на локалке (этот компьютер)

Залить код на VPS можно двумя способами:

### Вариант A: через Git (рекомендую)

На сервере мы будем делать `git clone` — ничего вручную тащить не надо.

### Вариант B: rsync с локалки

```bash
rsync -a --delete --exclude='.git' --exclude='postgres-data' \
  --exclude='redis-data' --exclude='caddy-data' --exclude='caddy-config' \
  ./ root@SERVER_IP:/root/vlessich-1/
```

---

## Шаг 1 — Подключиться к серверу

```bash
ssh root@SERVER_IP
```

(если нет root — `ssh user@SERVER_IP`, а команды ниже запускай под `sudo`)

## Шаг 2 — Получить код

```bash
cd /root
git clone https://github.com/FunNikitos/Vlessichbot.git vlessich-1
cd vlessich-1
```

## Шаг 3 — Запустить deploy.sh

Он:
1. Поставит curl/git/rsync/jq/ufw + Docker.
2. Настроит UFW (открыто только 22, 80, 443, 8080).
3. Скопирует репозиторий в `/opt/vlessich`.
4. Создаст `.env` из `.env.example`, если его ещё нет.
5. Поднимет postgres + redis + bot.
6. Применит миграции (включая backfill `sub_token`).

```bash
sudo bash scripts/deploy.sh
```

После первого прогона он остановится на сообщении про `.env`. Это нормально.

## Шаг 4 — Заполнить `.env`

```bash
sudo nano /opt/vlessich/.env
```

Минимум, что нужно поправить:

```env
BOT_TOKEN=123456:AAA...           # от @BotFather
OWNER_ID=123456789                # твой Telegram ID (узнай у @userinfobot)
SERVER_DOMAIN=vpn.example.com     # домен с A-записью на этот VPS
MARZBAN_PASSWORD=                 # оставь пустым — заполнишь после Шага 5
```

## Шаг 5 — Поставить Marzban

```bash
sudo bash /opt/vlessich/scripts/setup_marzban.sh
```

Создать админа Marzban:

```bash
sudo marzban cli admin create --sudo
# username: admin
# password: <свой пароль>
```

Прописать этот пароль в `.env`:

```bash
sudo nano /opt/vlessich/.env
# MARZBAN_PASSWORD=...
```

Открыть Marzban-дашборд и **создать inbound `VLESS Reality`**:
- открой `https://SERVER_DOMAIN/dashboard/` (после Шага 6) **или** временно `http://SERVER_IP:8000/dashboard`
- Inbounds → New → VLESS + Reality
- Tag: `VLESS Reality` (важно — именно так, бот ищет по этому тегу)
- Port: `443` или любой 10000-65000 (бот всё равно ротирует)
- SNI / Dest: `www.microsoft.com:443` (ротатор перепишет)
- Сохрани.

## Шаг 6 — Поднять Caddy (TLS + reverse proxy)

```bash
sudo bash /opt/vlessich/scripts/setup_caddy.sh
```

Caddy сам выпустит Let's Encrypt сертификат на `SERVER_DOMAIN`. Проверка:

```bash
curl -I https://SERVER_DOMAIN
# HTTP/2 200
```

## Шаг 7 — Перезапустить бот с заполненным `.env`

```bash
cd /opt/vlessich
sudo docker compose restart bot
sudo docker compose logs -f bot
```

Должно появиться:
```
Subscription server on 0.0.0.0:8081
Honeypot listening on [...]:8080
Scheduler started: expire/5m, probe/10m, ...
```

## Шаг 8 — Проверка

В Telegram:
- Открой свой бот → `/start` (как owner ты получаешь админ-доступ автоматически)
- `/admin` → 📊 Трафик → должен ответить (даже если 0 пользователей)
- `/newconfig` — должен сгенерироваться `https://SERVER_DOMAIN/sub/<token>`

Открой эту ссылку в браузере — увидишь `vless://...` строку. ✅

---

## Что куда смотрит на сервере

```
/opt/vlessich/                  ← код + docker-compose
/opt/vlessich/.env              ← секреты
/opt/vlessich/postgres-data/    ← БД (NOT IN BACKUPS by default)
/var/lib/marzban/               ← Marzban + Xray
~/.caddy → /opt/vlessich/caddy-data ← TLS сертификаты
```

Порты на VPS:
- `22` (ssh)
- `80, 443` — Caddy (TLS-редирект и reverse proxy)
- `8080` — Honeypot (намеренно открыт, ловит сканеры)
- `8000` — Marzban API (только localhost, проксируется через Caddy на `/api/*` `/dashboard/*`)
- `8081` — наш subscription-сервер (только localhost, проксируется через Caddy на `/sub/*`)

## Если что-то сломалось

```bash
# Логи бота
sudo docker compose -f /opt/vlessich/docker-compose.yml logs --tail=200 bot

# Логи Caddy
sudo docker compose -f /opt/vlessich/docker-compose.yml --profile caddy logs --tail=100 caddy

# Логи Marzban
sudo journalctl -u marzban -n 200

# Перезапустить всё
cd /opt/vlessich
sudo docker compose restart bot
sudo docker compose --profile caddy restart caddy
sudo systemctl restart marzban
```

## Обновление кода

```bash
cd /root/vlessich-1
git pull
sudo bash scripts/deploy.sh   # idempotent, пересоберёт только bot
```
