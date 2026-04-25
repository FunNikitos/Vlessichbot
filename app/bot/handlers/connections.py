"""Connection (config) lifecycle: create / list / delete / qr / mode."""
from __future__ import annotations

import io
import logging

import qrcode
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.user import (
    confirm_delete,
    connection_actions,
    connection_list,
    main_menu,
)
from app.bot.texts.messages import CONFIG_CREATED, NO_CONFIGS
from app.services.connection_service import (
    create_connection,
    delete_connection,
    get_connection,
    list_connections,
    public_url_for,
    set_routing_mode,
)
from app.services.user_service import get_or_create_user
from app.utils.errors import log_error

log = logging.getLogger(__name__)
router = Router(name="connections")


@router.message(Command("newconfig"))
@router.callback_query(F.data == "conn:new")
async def new_config(event: Message | CallbackQuery, session: AsyncSession) -> None:
    target = event.message if isinstance(event, CallbackQuery) else event
    user = await get_or_create_user(session, event.from_user)
    try:
        conn = await create_connection(session, user)
    except Exception as e:  # noqa: BLE001
        log.exception("create_connection failed")
        await log_error(
            source="bot.new_config",
            message=str(e),
            user_id=event.from_user.id,
            exc=e,
        )
        await target.answer(f"❌ Не удалось создать конфиг: {e}")
        if isinstance(event, CallbackQuery):
            await event.answer()
        return
    await target.answer(
        CONFIG_CREATED.format(url=public_url_for(conn, user)),
        reply_markup=connection_actions(conn.id, conn.routing_mode),
    )
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("myconfigs"))
@router.callback_query(F.data == "conn:list")
async def list_configs(event: Message | CallbackQuery, session: AsyncSession) -> None:
    target = event.message if isinstance(event, CallbackQuery) else event
    user = await get_or_create_user(session, event.from_user)
    rows = await list_connections(session, user.id)
    if not rows:
        await target.answer(NO_CONFIGS, reply_markup=main_menu())
        if isinstance(event, CallbackQuery):
            await event.answer()
        return
    text = (
        f"<b>Твои конфиги ({len(rows)}):</b>\n\n"
        "Нажми на конфиг чтобы открыть действия (QR, удалить, режим)."
    )
    await target.answer(text, reply_markup=connection_list(rows))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(F.data.startswith("conn:show:"))
async def cb_show(cb: CallbackQuery, session: AsyncSession) -> None:
    cid = int(cb.data.split(":")[2])
    user = await get_or_create_user(session, cb.from_user)
    conn = await get_connection(session, cid, user.id)
    if not conn:
        await cb.answer("Не найдено", show_alert=True)
        return
    text = (
        f"<b>Конфиг #{conn.id}</b>\n"
        f"Имя: <code>{conn.name}</code>\n"
        f"Режим: <b>{conn.routing_mode}</b>\n\n"
        f"<code>{public_url_for(conn, user)}</code>"
    )
    try:
        await cb.message.edit_text(
            text, reply_markup=connection_actions(conn.id, conn.routing_mode)
        )
    except Exception:  # noqa: BLE001
        await cb.message.answer(
            text, reply_markup=connection_actions(conn.id, conn.routing_mode)
        )
    await cb.answer()


@router.callback_query(F.data.startswith("conn:qr:"))
async def cb_qr(cb: CallbackQuery, session: AsyncSession) -> None:
    cid = int(cb.data.split(":")[2])
    user = await get_or_create_user(session, cb.from_user)
    conn = await get_connection(session, cid, user.id)
    if not conn:
        await cb.answer("Не найдено", show_alert=True)
        return
    payload = public_url_for(conn, user)
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await cb.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename=f"config-{cid}.png"),
        caption=f"QR-код конфига #{cid}",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("conn:copy:"))
async def cb_copy(cb: CallbackQuery, session: AsyncSession) -> None:
    cid = int(cb.data.split(":")[2])
    user = await get_or_create_user(session, cb.from_user)
    conn = await get_connection(session, cid, user.id)
    if not conn:
        await cb.answer("Не найдено", show_alert=True)
        return
    await cb.message.answer(f"<code>{public_url_for(conn, user)}</code>")
    await cb.answer("Ссылка отправлена")


@router.callback_query(F.data.startswith("conn:mode:"))
async def cb_mode(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer("bad cb", show_alert=True)
        return
    cid = int(parts[2])
    mode = parts[3]
    user = await get_or_create_user(session, cb.from_user)
    conn = await get_connection(session, cid, user.id)
    if not conn:
        await cb.answer("Не найдено", show_alert=True)
        return
    if conn.routing_mode == mode:
        await cb.answer(f"Уже {mode}")
        return
    conn = await set_routing_mode(session, conn, mode)
    label = "Smart (RU напрямую)" if mode == "smart" else "Full (всё через VPN)"
    await cb.answer(f"✅ {label}")
    try:
        await cb.message.edit_reply_markup(
            reply_markup=connection_actions(conn.id, conn.routing_mode)
        )
    except Exception:  # noqa: BLE001
        # message could be a photo with no inline kb attached — ignore
        pass


@router.callback_query(F.data.startswith("conn:del:confirm:"))
async def cb_del_confirm(cb: CallbackQuery, session: AsyncSession) -> None:
    cid = int(cb.data.split(":")[3])
    user = await get_or_create_user(session, cb.from_user)
    ok = await delete_connection(session, cid, user.id)
    if not ok:
        await cb.answer("Не найдено", show_alert=True)
        return
    # После удаления — показываем актуальный список (или пустое меню)
    rows = await list_connections(session, user.id)
    if rows:
        text = f"🗑 Конфиг #{cid} удалён.\n\n<b>Осталось ({len(rows)}):</b>"
        await cb.message.edit_text(text, reply_markup=connection_list(rows))
    else:
        await cb.message.edit_text(
            f"🗑 Конфиг #{cid} удалён. У тебя больше нет активных конфигов.",
            reply_markup=main_menu(),
        )
    await cb.answer("Удалено")


@router.callback_query(F.data.startswith("conn:del:"))
async def cb_del(cb: CallbackQuery, session: AsyncSession) -> None:
    # Подтверждение перед удалением (защита от случайного нажатия).
    cid = int(cb.data.split(":")[2])
    user = await get_or_create_user(session, cb.from_user)
    conn = await get_connection(session, cid, user.id)
    if not conn:
        await cb.answer("Не найдено", show_alert=True)
        return
    text = (
        f"⚠️ Удалить конфиг #{conn.id} ({conn.name})?\n\n"
        "Существующие подключения в Hiddify перестанут работать. "
        "Если это последний конфиг — твой Marzban-аккаунт также будет удалён."
    )
    try:
        await cb.message.edit_text(text, reply_markup=confirm_delete(conn.id))
    except Exception:  # noqa: BLE001
        await cb.message.answer(text, reply_markup=confirm_delete(conn.id))
    await cb.answer()
