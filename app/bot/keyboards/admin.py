"""Admin keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎟 Коды", callback_data="adm:codes"),
                InlineKeyboardButton(text="🔗 Инвайты", callback_data="adm:invites"),
            ],
            [
                InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users"),
                InlineKeyboardButton(text="🔌 Подключения", callback_data="adm:conns"),
            ],
            [
                InlineKeyboardButton(text="🔄 Ротация", callback_data="adm:rotate"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
            ],
            [
                InlineKeyboardButton(text="📜 История блоков", callback_data="adm:history"),
                InlineKeyboardButton(text="👁 Honeypot", callback_data="adm:honeypot"),
            ],
            [
                InlineKeyboardButton(text="📊 Трафик", callback_data="adm:traffic"),
                InlineKeyboardButton(text="🐞 Ошибки", callback_data="adm:errors"),
            ],
        ]
    )


def honeypot_menu(running: bool) -> InlineKeyboardMarkup:
    toggle = (
        InlineKeyboardButton(text="🔴 Выключить", callback_data="hp:off")
        if running
        else InlineKeyboardButton(text="🟢 Включить", callback_data="hp:on")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle],
            [InlineKeyboardButton(text="📋 Последние удары", callback_data="hp:list")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")],
        ]
    )


def rotate_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 SNI", callback_data="rot:sni")],
            [InlineKeyboardButton(text="🔄 Порт", callback_data="rot:port")],
            [InlineKeyboardButton(text="🔄 Short ID", callback_data="rot:sid")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")],
        ]
    )
