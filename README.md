# vlessich-1

Production-grade Telegram VPN-бот поверх **Marzban + Xray** (VLESS+Reality / XHTTP / gRPC-CF).
Пользователь нажал одну кнопку — Subscription URL в Hiddify, и всё работает.
Российские сайты идут напрямую (split-tunnel), остальное — через VPN.

## Стек

- **Telegram bot**: aiogram 3 (async)
- **Backend**: FastAPI + APScheduler
- **DB**: PostgreSQL 16 (asyncpg) + Alembic
- **Cache / rate-limit**: Redis 7
- **VPN-панель**: Marzban (Xray-core)
- **TLS reverse-proxy**: Caddy 2 (auto-TLS, /sub/ proxy)
- **DNS-фильтр**: AdGuard Home (опционально)
- **Dashboard трафика**: traffic-ui (опционально)

## Архитектура (кратко)

```
Telegram ──► aiogram bot ──► Marzban API ──► Xray (VLESS+Reality / XHTTP / gRPC-CF)
                │                                   ▲
                ├── aiohttp /sub/<token> ◄── Caddy 443 (/sub/* + fallback site)
                ├── APScheduler: monitor / rotation / expiration
                ├── Honeypot :8080 → ufw block
                └── Reality-SNI-Finder → sni_donors
```

## Быстрый старт

```bash
git clone https://github.com/FunNikitos/Vlessichbot.git /opt/vlessich
cd /opt/vlessich
cp .env.example .env
# Заполни BOT_TOKEN, OWNER_ID, SERVER_DOMAIN, MARZBAN_PASSWORD
sudo bash scripts/deploy.sh           # postgres + redis + bot
sudo bash scripts/setup_marzban.sh    # панель Marzban
sudo bash scripts/setup_caddy.sh      # TLS + /sub proxy
sudo bash scripts/setup_adguard.sh    # (опционально) DNS-фильтр
```

## Команды бота

| Команда         | Описание                       |
|-----------------|--------------------------------|
| `/start`        | Приветствие, deep-link инвайты |
| `/activate`     | Ввод инвайт-кода               |
| `/menu`         | Главное меню                   |
| `/newconfig`    | Создать конфиг                 |
| `/myconfigs`    | Список конфигов                |
| `/status`       | Heatmap доступности протоколов |
| `/help`         | Инструкции                     |

## Админ-команды (только OWNER_ID)

| Команда                       | Описание                        |
|-------------------------------|---------------------------------|
| `/admin`                      | Админ-панель (inline-меню)      |
| `/gencode <дней> [max_uses]`  | Создать инвайт-код              |
| `/geninvite <дней>`           | Создать deep-link инвайт        |
| `/errors`                     | Последние ошибки                |

## Roadmap

- **Шаг 1 (текущий)**: каркас, БД, миграции, скелет хэндлеров, deploy-скрипты.
- **Шаг 2**: интеграция с Marzban API (создание/удаление пользователей, выдача sub-URL).
- **Шаг 3**: APScheduler — мониторинг протоколов, авто-ротация SNI/port/short_id, экспирация.
- **Шаг 4**: honeypot :8080 + автобан в ufw, аудит-лог.
- **Шаг 5**: Reality-SNI-Finder, antifilter cache, split-tunnel routing.

## Лицензия

Private project.
