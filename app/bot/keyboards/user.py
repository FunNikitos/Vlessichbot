"""User keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆕 Новый конфиг", callback_data="conn:new")],
            [InlineKeyboardButton(text="📋 Мои конфиги", callback_data="conn:list")],
            [InlineKeyboardButton(text="📲 Инструкция", callback_data="instructions")],
            [InlineKeyboardButton(text="📡 Статус сервиса", callback_data="status")],
        ]
    )


def platforms() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 iOS", callback_data="instr:ios"),
                InlineKeyboardButton(text="🤖 Android", callback_data="instr:android"),
            ],
            [
                InlineKeyboardButton(text="🪟 Windows", callback_data="instr:windows"),
                InlineKeyboardButton(text="🍎 macOS", callback_data="instr:macos"),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")],
        ]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="menu")]]
    )


def connection_actions(conn_id: int, mode: str = "smart") -> InlineKeyboardMarkup:
    smart_label = "✅ Smart" if mode == "smart" else "⚪ Smart"
    full_label = "✅ Full" if mode == "full" else "⚪ Full"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 QR", callback_data=f"conn:qr:{conn_id}"),
                InlineKeyboardButton(text="📋 Скопировать", callback_data=f"conn:copy:{conn_id}"),
            ],
            [
                InlineKeyboardButton(text=smart_label, callback_data=f"conn:mode:{conn_id}:smart"),
                InlineKeyboardButton(text=full_label, callback_data=f"conn:mode:{conn_id}:full"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"conn:del:{conn_id}")],
            [
                InlineKeyboardButton(text="◀️ К списку", callback_data="conn:list"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
            ],
        ]
    )


def connection_list(rows) -> InlineKeyboardMarkup:
    """Список конфигов: каждый — отдельная кликабельная кнопка."""
    keyboard = []
    for c in rows:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"#{c.id} {c.name} ({c.routing_mode})",
                    callback_data=f"conn:show:{c.id}",
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton(text="🆕 Новый конфиг", callback_data="conn:new")]
    )
    keyboard.append(
        [InlineKeyboardButton(text="◀️ Меню", callback_data="menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def confirm_delete(conn_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Да, удалить",
                    callback_data=f"conn:del:confirm:{conn_id}",
                ),
                InlineKeyboardButton(
                    text="◀️ Отмена",
                    callback_data=f"conn:show:{conn_id}",
                ),
            ]
        ]
    )
