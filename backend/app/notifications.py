import logging
import os
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """
    Отправляет сообщение пользователю в Telegram через Bot API.
    
    Args:
        chat_id: Telegram chat_id пользователя
        text: Текст сообщения для отправки
    
    Returns:
        True если сообщение успешно отправлено, False в противном случае
    """
    if not settings.bot_token:
        logger.warning("[send_telegram_message] BOT_TOKEN не установлен, пропускаю отправку уведомления chat_id={chat_id}")
        return False
    
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"  # Поддержка базового форматирования
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"[send_telegram_message] Сообщение успешно отправлено chat_id={chat_id}")
                return True
            else:
                error_description = result.get("description", "Unknown error")
                logger.error(
                    f"[send_telegram_message] Ошибка при отправке сообщения chat_id={chat_id}: {error_description}"
                )
                # Не выбрасываем исключение, чтобы не ломать весь процесс
                return False
                
    except httpx.HTTPStatusError as e:
        logger.error(
            f"[send_telegram_message] HTTP ошибка при отправке сообщения chat_id={chat_id}: {e.response.status_code} - {e.response.text}",
            exc_info=True
        )
    except httpx.RequestError as e:
        logger.error(
            f"[send_telegram_message] Ошибка сети при отправке сообщения chat_id={chat_id}: {e}",
            exc_info=True
        )
    except Exception as e:
        logger.error(
            f"[send_telegram_message] Неожиданная ошибка при отправке сообщения chat_id={chat_id}: {e}",
            exc_info=True
        )
    return False


    return False

async def send_admin_message(text: str, reply_markup: dict | None = None) -> bool:
    """Отправляет сообщение администратору через Telegram Bot API.
    
    Args:
        text: Текст сообщения для отправки
        reply_markup: Optional dictionary for inline keyboard or other reply markup
    
    Returns:
        True если сообщение успешно отправлено, False в противном случае
    """
    admin_id_str = os.getenv("ADMIN_CHAT_ID")
    if not admin_id_str:
        logger.warning("[send_admin_message] ADMIN_CHAT_ID не установлен, пропускаю отправку")
        return False
    
    try:
        admin_chat_id = int(admin_id_str)
    except (ValueError, TypeError):
        logger.warning(f"[send_admin_message] ADMIN_CHAT_ID некорректный: {admin_id_str}")
        return False
    
    return await send_telegram_message(admin_chat_id, text, reply_markup=reply_markup)

async def send_admin_alert(message: str) -> None:
    """
    Отправляет алерт администратору в Telegram через Bot API.
    Если токен или chat_id не настроены - тихо выходит без ошибок.
    
    Args:
        message: Текст сообщения-алерта для отправки администратору
    """
    if not settings.bot_token or not settings.admin_chat_id:
        # Тихо выходим, если настройки не заданы
        return
    
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    
    payload: dict[str, Any] = {
        "chat_id": settings.admin_chat_id,
        "text": message,
        "parse_mode": "HTML"  # Поддержка базового форматирования
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"[send_admin_alert] Алерт успешно отправлен администратору chat_id={settings.admin_chat_id}")
            else:
                error_description = result.get("description", "Unknown error")
                logger.error(
                    f"[send_admin_alert] Ошибка при отправке алерта администратору: {error_description}"
                )
                # Не выбрасываем исключение, чтобы не ломать весь процесс
                return False
                
    except httpx.HTTPStatusError as e:
        logger.error(
            f"[send_admin_alert] HTTP ошибка при отправке алерта администратору: {e.response.status_code} - {e.response.text}",
            exc_info=True
        )
    except httpx.RequestError as e:
        logger.error(
            f"[send_admin_alert] Ошибка сети при отправке алерта администратору: {e}",
            exc_info=True
        )
    except Exception as e:
        logger.error(
            f"[send_admin_alert] Неожиданная ошибка при отправке алерта администратору: {e}",
            exc_info=True
        )

