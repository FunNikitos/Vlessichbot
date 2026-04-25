"""Admin-facing texts."""

ADMIN_PANEL = "🛠 <b>Админ-панель</b>"
ADMIN_NOT_OWNER = "Доступно только владельцу."

CODE_GENERATED = "✅ Код создан: <code>{code}</code>\nСрок: {days} дн.  Использований: {max_uses}"
INVITE_GENERATED = "✅ Инвайт-ссылка:\n{link}\nИстекает через {days} дн."

ROTATE_OK_SNI = "✅ SNI ротирован: <code>{value}</code>"
ROTATE_OK_PORT = "✅ Порт ротирован: <code>{value}</code>"
ROTATE_OK_SHORT_ID = "✅ Short ID ротирован: <code>{value}</code>"
ROTATE_FAIL = "❌ Не удалось выполнить ротацию (детали в /errors)."

SERVER_DOWN = "🔴 <b>{name}</b> ({host}) — недоступен.\n{datetime}"
SERVER_RECOVERED = "🟢 <b>{name}</b> ({host}) — снова работает.\n{datetime}"

HONEYPOT_HIT = (
    "👁 Сканирование сервера\n"
    "IP: <code>{ip}</code>\n"
    "{country_line}"
    "Порт-ловушка: {port}"
)
HONEYPOT_BLOCKED = "🚫 <code>{ip}</code> заблокирован в ufw."
HONEYPOT_BLOCK_FAIL = "❌ Не удалось заблокировать <code>{ip}</code>: {info}"

USER_EXPIRED_NOTIFY = "⏳ Срок твоего доступа истёк. Подключения деактивированы."
USER_EXPIRED_OWNER = "⏳ Истёк доступ: {name} (id {telegram_id}). Деактивировано: {connections_count}."

OWNER_GENERIC_ALERT = "⚠️ <b>{title}</b>\n{body}"

SNI_FINDER_RESULT = (
    "🔍 <b>SNI Finder</b>\n"
    "Проверено: {total}\n"
    "Прошло TLS1.3+h2: {eligible}\n\n"
    "{top}"
)
