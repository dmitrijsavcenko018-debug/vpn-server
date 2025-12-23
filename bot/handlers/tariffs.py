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
    # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ В САМОМ НАЧАЛЕ
    logger.info("🔥 HANDLER choose_tariff ВЫЗВАН user_id=%s data=%s", call.from_user.id, call.data)
    print(f"🔥 HANDLER choose_tariff ВЫЗВАН user_id={call.from_user.id} data={call.data}")
    
    try:
        # Сразу отвечаем на callback, чтобы убрать "крутилку" и "ok"
        await call.answer()
        logger.info("✅ HANDLER choose_tariff: call.answer() выполнен")
        print("✅ HANDLER choose_tariff: call.answer() выполнен")
    except Exception as e:
        logger.exception("❌ HANDLER choose_tariff: ошибка в call.answer(): %s", e)
        print(f"❌ HANDLER choose_tariff: ошибка в call.answer(): {e}")
        return
    
    try:
        # Парсим months из callback_data
        _, months_str = call.data.split(":")
        months = int(months_str)
        logger.info("HANDLER choose_tariff: распарсили months=%d", months)
        print(f"HANDLER choose_tariff: распарсили months={months}")
    except (ValueError, IndexError) as e:
        logger.error("HANDLER choose_tariff: ошибка парсинга callback_data: %s", e)
        print(f"HANDLER choose_tariff: ошибка парсинга callback_data: {e}")
        await call.message.answer("❌ Ошибка: некорректный тариф. Попробуйте выбрать тариф снова.")
        return
    
    # Найти тариф по months
    tariff = next((t for t in VPN_TARIFFS if t["months"] == months), None)
    if not tariff:
        logger.error("HANDLER choose_tariff: тариф с months=%d не найден", months)
        print(f"HANDLER choose_tariff: тариф с months={months} не найден")
        await call.message.answer("❌ Ошибка: тариф не найден. Попробуйте выбрать тариф снова.")
        return
    
    price = tariff["price"]
    title = tariff["title"]
    logger.info("HANDLER choose_tariff: найден тариф title=%s price=%d", title, price)
    print(f"HANDLER choose_tariff: найден тариф title={title} price={price}")
    
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
    
    try:
        # Пытаемся отредактировать сообщение
        logger.info("HANDLER choose_tariff: пытаемся отредактировать сообщение")
        print("HANDLER choose_tariff: пытаемся отредактировать сообщение")
        await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        logger.info("HANDLER choose_tariff: сообщение успешно отредактировано")
        print("HANDLER choose_tariff: сообщение успешно отредактировано")
    except Exception as e:
        # Если редактирование не удалось (сообщение уже удалено/отредактировано), отправляем новое
        logger.warning("HANDLER choose_tariff: не удалось отредактировать сообщение: %s, отправляем новое", e)
        print(f"HANDLER choose_tariff: не удалось отредактировать сообщение: {e}, отправляем новое")
        try:
            await call.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            logger.info("HANDLER choose_tariff: новое сообщение успешно отправлено")
            print("HANDLER choose_tariff: новое сообщение успешно отправлено")
        except Exception as e2:
            logger.exception("HANDLER choose_tariff: критическая ошибка при отправке сообщения")
            print(f"HANDLER choose_tariff: критическая ошибка при отправке сообщения: {e2}")
            # Пытаемся хотя бы отправить простое сообщение
            try:
                await call.message.answer(f"Вы выбрали тариф: {title} — {price} ₽. Оплатите по реквизитам и нажмите «✅ Я оплатил».")
            except:
                pass

