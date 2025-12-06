"""
Обработчик ручной оплаты
"""
import os
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

router = Router()

# Получаем ADMIN_CHAT_ID из переменных окружения
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID.strip())
    except ValueError:
        ADMIN_CHAT_ID = None
        logger.warning("[manual_payment] ADMIN_CHAT_ID не является числом, уведомления админу отключены")
else:
    logger.warning("[manual_payment] ADMIN_CHAT_ID не установлен, уведомления админу отключены")


@router.callback_query(F.data.startswith("manual_paid:"))
async def handle_manual_paid(call: CallbackQuery):
    """
    Обработчик нажатия кнопки "✅ Я оплатил" с выбранным тарифом
    """
    user = call.from_user
    
    try:
        _, months_str = call.data.split(":")
        months = int(months_str)
    except (ValueError, IndexError):
        await call.answer("Ошибка: некорректные данные тарифа.", show_alert=True)
        return
    
    # 1) Закрыть крутилку на кнопке
    await call.answer()
    
    # 2) Ответ пользователю
    await call.message.answer(
        "Спасибо! Мы проверим оплату в ближайшее время.\n"
        "Если вы ещё не отправили чек, отправьте его администратору."
    )
    
    # 3) Уведомление админу
    if ADMIN_CHAT_ID:
        try:
            username = f"@{user.username}" if user.username else "(без username)"
            text = (
                "💸 Пользователь сообщил об оплате.\n\n"
                f"Имя: {user.full_name}\n"
                f"Username: {username}\n"
                f"Telegram ID: {user.id}\n"
                f"Выбранный тариф: {months} мес.\n\n"
                "Нужно проверить оплату и подтвердить её."
            )
            
            # Кнопка «Подтвердить оплату» с кодированными telegram_id и months
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить оплату",
                            callback_data=f"confirm_paid:{user.id}:{months}"
                        )
                    ]
                ]
            )
            
            await call.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, reply_markup=kb)
            logger.info(f"[handle_manual_paid] Уведомление отправлено админу {ADMIN_CHAT_ID} о пользователе {user.id}, тариф {months} мес.")
        except Exception as e:
            logger.error(f"[handle_manual_paid] Ошибка при отправке уведомления админу: {e}")
    else:
        logger.warning("[handle_manual_paid] ADMIN_CHAT_ID не установлен, уведомление админу не отправлено")

