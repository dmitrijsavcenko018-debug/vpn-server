"""
Обработчик подтверждения оплаты админом
"""
import os
import logging
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from api_client import ApiClient

logger = logging.getLogger(__name__)

router = Router()

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
api_client = ApiClient(base_url=BACKEND_URL)


def format_date_ddmmyyyy(date_str: str) -> str:
    """Форматирует дату из ISO формата в DD.MM.YYYY"""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return date_str


@router.callback_query(F.data.startswith("confirm_paid:"))
async def handle_confirm_paid(call: CallbackQuery):
    """
    Обработчик подтверждения оплаты админом
    """
    try:
        _, tg_id_str, months_str = call.data.split(":")
        user_telegram_id = int(tg_id_str)
        months = int(months_str)
    except (ValueError, IndexError) as e:
        logger.error(f"[handle_confirm_paid] Ошибка парсинга данных: {e}")
        await call.answer("Некорректные данные.", show_alert=True)
        return
    
    await call.answer("Обрабатываю...")
    
    try:
        # 1) Вызвать backend для активации/продления подписки
        result = await api_client.activate_subscription(
            telegram_id=user_telegram_id,
            months=months
        )
        
        if not result:
            raise Exception("Backend вернул пустой результат")
        
        expires_at_str = result.get("expires_at", "")
        
        # Форматируем дату для отображения
        try:
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            expires_at_formatted = expires_at.strftime("%d.%m.%Y")
        except Exception:
            expires_at_formatted = expires_at_str
        
        # 2) Обновить сообщение админу
        base_text = call.message.text or ""
        updated_text = (
            f"{base_text}\n\n"
            f"✅ Подписка подтверждена.\n"
            f"Срок действия до: {expires_at_formatted}"
        )
        await call.message.edit_text(updated_text)
        await call.answer("Подписка активирована.")
        
        logger.info(f"[handle_confirm_paid] Подписка активирована для user_id={user_telegram_id}, months={months}, expires_at={expires_at_formatted}")
        
        # 3) Получить конфиг и отправить пользователю используя единую функцию
        try:
            # Импортируем единую функцию отправки конфига
            from vpn_config_sender import send_vpn_config
            
            # Устанавливаем api_client для модуля (если еще не установлен)
            from vpn_config_sender import set_api_client
            set_api_client(api_client)
            
            # Отправляем конфиг (всегда получаем с backend)
            await send_vpn_config(call.bot, user_telegram_id)
            
            logger.info(f"[handle_confirm_paid] Конфиг отправлен пользователю {user_telegram_id}")
            
        except Exception as e:
            logger.error(f"[handle_confirm_paid] Ошибка при отправке конфига пользователю {user_telegram_id}: {e}")
            logger.exception(f"[handle_confirm_paid] Детали ошибки:")
            # Отправляем хотя бы уведомление об активации
            try:
                await call.bot.send_message(
                    chat_id=user_telegram_id,
                    text=(
                        "✅ Ваша подписка активирована/продлена.\n"
                        f"Она будет действовать до: {expires_at_formatted}.\n\n"
                        "Нажмите «🎁 Подключить VPN», чтобы получить конфиг."
                    )
                )
            except Exception as send_error:
                logger.error(f"[handle_confirm_paid] Не удалось отправить уведомление пользователю {user_telegram_id}: {send_error}")
        
    except Exception as e:
        logger.exception(f"[handle_confirm_paid] Ошибка при активации подписки: {e}")
        await call.answer("Ошибка при активации подписки. Проверьте логи.", show_alert=True)
        try:
            await call.message.edit_text(
                f"{call.message.text or ''}\n\n"
                "❌ Ошибка при активации подписки. Проверьте логи."
            )
        except Exception:
            pass



