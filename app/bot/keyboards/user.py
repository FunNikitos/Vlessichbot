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


def connection_actions(conn_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 QR", callback_data=f"conn:qr:{conn_id}"),
                InlineKeyboardButton(text="📋 Скопировать", callback_data=f"conn:copy:{conn_id}"),
            ],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"conn:del:{conn_id}")],
            [InlineKeyboardButton(text="◀️ Меню", callback_data="menu")],
        ]
    )
