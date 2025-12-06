"""
Обработчик выбора тарифов пользователем
"""
import os
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import VPN_TARIFFS

logger = logging.getLogger(__name__)

router = Router()

# Реквизиты для ручной оплаты
MANUAL_PAY_PHONE = os.getenv("MANUAL_PAY_PHONE", "89287699799")
MANUAL_PAY_BANK = os.getenv("MANUAL_PAY_BANK", "Ozon Банк")
MANUAL_PAY_CARD = os.getenv("MANUAL_PAY_CARD", "")


@router.callback_query(F.data.startswith("choose_tariff:"))
async def handle_choose_tariff(call: CallbackQuery):
    """
    Обработчик выбора тарифа пользователем
    """
    try:
        _, months_str = call.data.split(":")
        months = int(months_str)
    except (ValueError, IndexError):
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    
    # Найти тариф по months
    tariff = next((t for t in VPN_TARIFFS if t["months"] == months), None)
    if not tariff:
        await call.answer("Некорректный тариф.", show_alert=True)
        return
    
    price = tariff["price"]
    title = tariff["title"]
    
    # Текст с реквизитами
    text = (
        f"Вы выбрали тариф: {title} — {price} ₽.\n\n"
        "Оплатите по реквизитам:\n"
        f"📱 Номер телефона: `{MANUAL_PAY_PHONE}`\n"
        f"🏦 Банк: {MANUAL_PAY_BANK}"
    )
    if MANUAL_PAY_CARD:
        text += f"\n💳 Номер карты: `{MANUAL_PAY_CARD}`"
    
    text += "\n\nПосле оплаты нажмите кнопку «✅ Я оплатил»."
    
    # Inline-кнопка «Я оплатил» с КОДИРОВАННЫМ months
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"manual_paid:{months}"
                )
            ]
        ]
    )
    
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

