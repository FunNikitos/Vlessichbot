"""Admin: rotation (SNI / port / short_id) — stub for step 1.
Реальная ротация будет в фазе ротаций (вызовы к Marzban API)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.filters.admin import IsAdmin
from app.bot.keyboards.admin import admin_menu, rotate_menu

router = Router(name="admin.rotation")
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "adm:rotate")
async def cb_rotate_menu(cb: CallbackQuery) -> None:
    await cb.message.edit_text("Что ротируем?", reply_markup=rotate_menu())
    await cb.answer()


@router.callback_query(F.data.startswith("rot:"))
async def cb_rotate(cb: CallbackQuery) -> None:
    kind = cb.data.split(":")[1]
    await cb.message.edit_text(
        f"⚙️ Ротация ({kind}) будет реализована в фазе 3.",
        reply_markup=admin_menu(),
    )
    await cb.answer()
