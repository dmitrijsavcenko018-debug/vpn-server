"""
Единая функция для отправки VPN-конфига пользователю.
Всегда получает конфиг с backend, ничего не генерирует в боте.
"""
import traceback
from datetime import datetime
from html import escape
import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.enums import ParseMode

from api_client import ApiClient
from keyboards import vpn_apps_kb

# Создаем глобальный экземпляр api_client (будет переопределен в bot_main)
api_client = None


def set_api_client(client: ApiClient):
    """Устанавливает api_client для использования в этой функции"""
    global api_client
    api_client = client


async def send_vpn_config(bot: Bot, telegram_id: int, filename: str = "vpn.conf") -> bool:
    """
    Единая функция для отправки VPN-конфига пользователю.
    Всегда получает конфиг с backend, ничего не генерирует в боте.
    
    Args:
        bot: Экземпляр Bot для отправки сообщений
        telegram_id: Telegram ID пользователя
        filename: Имя файла для отправки (по умолчанию "vpn.conf")
    
    Returns:
        True если конфиг успешно отправлен, False в случае ошибки
    """
    if api_client is None:
        raise RuntimeError("api_client не установлен. Вызовите set_api_client() перед использованием.")
    
    try:
        # Получаем конфиг с backend (backend сам проверит подписку)
        vpn_config = await api_client.get_vpn_config(telegram_id=telegram_id)
        config_text = vpn_config.get("config")
        expires_at_str = vpn_config.get("expires_at")  # Если backend отдаёт
        
        if not config_text:
            print(f"[send_vpn_config] ERROR: Empty config_text for telegram_id={telegram_id}")
            await bot.send_message(
                chat_id=telegram_id,
                text="❌ Конфиг недоступен. Попробуйте позже."
            )
            return False
        
        # Логирование для проверки
        print(f"[send_vpn_config] DEBUG: Sending config file, length = {len(config_text)}")
        
        # Формируем дату окончания подписки
        expire_date = ""
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                expire_date = expires_at.strftime("%d.%m.%Y")
            except Exception:
                expire_date = expires_at_str
        
        # Формируем текст сообщения с конфигом
        message_text = ""
        
        if expire_date:
            message_text += f"Подписка активна до: {expire_date}\n\n"
        
        message_text += "🗝 Ваш VPN-конфиг (вставьте в приложение):\n\n"
        # Экранируем специальные символы для HTML
        message_text += f"<code>{escape(config_text)}</code>"
        
        # Отправляем сообщение с конфигом и inline-клавиатурой
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=vpn_apps_kb
        )
        
        # Отправляем файл vpn.conf
        file = BufferedInputFile(
            config_text.encode("utf-8"),
            filename=filename
        )
        
        await bot.send_document(
            chat_id=telegram_id,
            document=file,
            caption="📄 Файл конфига для импорта в приложение WireGuard"
        )
        
        return True
        
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        print(f"[send_vpn_config] HTTP ошибка {status_code} при получении конфига для telegram_id={telegram_id}:")
        traceback.print_exc()
        
        if status_code == 403:
            await bot.send_message(
                chat_id=telegram_id,
                text="❌ У вас нет активной подписки.\nСначала оформите подписку, чтобы получить конфиг."
            )
        elif status_code == 404:
            await bot.send_message(
                chat_id=telegram_id,
                text="❌ Пользователь не найден в системе.\nПожалуйста, свяжитесь с поддержкой."
            )
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text="❌ Временная техническая ошибка при получении конфига.\nПопробуйте позже или обратитесь в поддержку."
            )
        return False
        
    except httpx.ConnectError as e:
        import logging
        logging.exception(f"[send_vpn_config] Ошибка подключения к backend для telegram_id={telegram_id}")
        print(f"[send_vpn_config] Ошибка подключения к backend для telegram_id={telegram_id}: {e}")
        traceback.print_exc()
        await bot.send_message(
            chat_id=telegram_id,
            text="❌ Не удаётся получить конфиг VPN. Попробуйте позже."
        )
        return False
    except Exception as e:
        import logging
        logging.exception(f"[send_vpn_config] Ошибка при получении/отправке конфига для telegram_id={telegram_id}")
        print(f"[send_vpn_config] Ошибка при получении/отправке конфига для telegram_id={telegram_id}:")
        traceback.print_exc()
        await bot.send_message(
            chat_id=telegram_id,
            text="❌ Не удаётся получить конфиг VPN. Попробуйте позже."
        )
        return False

