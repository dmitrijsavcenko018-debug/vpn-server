import asyncio
import os
import traceback
import logging
from datetime import datetime, timezone

from aiohttp import ClientSession, TCPConnector
import aiohttp
import httpx
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardRemove,
    Update,
)
from aiogram import BaseMiddleware
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards import (
    main_menu_keyboard,
    back_to_main_keyboard,
    manual_payment_kb,
    vpn_main_kb,
)
from texts import (
    TEXT_START,
    TEXT_MAIN_MENU,
    TEXT_VPN_READY,
    TEXT_CONFIGS,
    TEXT_PHONE_CONFIG,
    TEXT_LAPTOP_CONFIG,
    TEXT_ADD_DEVICE,
    TEXT_CONFIG_NO_ACCESS,
    TEXT_SUPPORT,
    TEXT_HELP,
)
from config import VPN_TARIFFS, format_tariffs

from api_client import ApiClient
from vpn_config_sender import set_api_client

# Импортируем routers для ручной оплаты
try:
    from handlers.manual_payment import router as manual_payment_router
except ImportError as e:
    manual_payment_router = None
    print(f"[bot_main] ⚠️ Ошибка импорта manual_payment router: {e}")

try:
    from handlers.tariffs import router as tariffs_router
except ImportError as e:
    tariffs_router = None
    print(f"[bot_main] ⚠️ Ошибка импорта tariffs router: {e}")

try:
    from handlers.admin_confirm import router as admin_confirm_router
except ImportError as e:
    admin_confirm_router = None
    print(f"[bot_main] ⚠️ Ошибка импорта admin_confirm router: {e}")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Реквизиты для ручной оплаты
MANUAL_PAY_PHONE = os.getenv("MANUAL_PAY_PHONE", "89287699799")
MANUAL_PAY_BANK = os.getenv("MANUAL_PAY_BANK", "Ozon Банк")
MANUAL_PAY_CARD = os.getenv("MANUAL_PAY_CARD", "")  # Опционально: номер карты

router = Router()

api_client = ApiClient(base_url=BACKEND_URL)
logger = logging.getLogger(__name__)

# Устанавливаем api_client для модуля vpn_config_sender
set_api_client(api_client)

# Middleware для логирования всех апдейтов
class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            text = getattr(event, 'text', None) or getattr(event, 'caption', None) or ''
            logger.info("IN_MSG from=%s text=%s", user_id, text[:100])
            print(f"IN_MSG from={user_id} text={text[:100]}")
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            data_val = getattr(event, 'data', None) or ''
            logger.info("IN_CB from=%s data=%s", user_id, data_val[:100])
            print(f"IN_CB from={user_id} data={data_val[:100]}")
        return await handler(event, data)

def is_admin(chat_id: int) -> bool:
    admin_id_str = os.getenv("ADMIN_CHAT_ID")
    if not admin_id_str:
        return False
    try:
        return chat_id == int(admin_id_str)
    except Exception:
        return False



def is_subscription_active(expires_at_str: str | None) -> bool:
    """
    Возвращает True, если подписка активна (дата в будущем),
    False — если истекла или даты нет / не удалось распарсить.
    """
    if not expires_at_str:
        return False

    try:
        # Убираем возможный 'Z' и таймзону, оставляем только основную часть даты
        cleaned = expires_at_str.replace("Z", "")
        if "+" in cleaned:
            cleaned = cleaned.split("+", 1)[0]

        # Парсим как naive datetime (без таймзоны)
        expires_at = datetime.fromisoformat(cleaned)

        # Сравниваем с текущим временем UTC (также naive)
        now = datetime.now(timezone.utc)
        return expires_at > now
    except Exception as e:
        # Если что-то пошло не так — считаем, что подписка неактивна,
        # но логируем ошибку в консоль
        print(f"[is_subscription_active] parse error for {expires_at_str}: {e}")
        return False


async def get_subscription_status(telegram_id: int) -> tuple[str, str | None]:
    """
    Получает статус подписки через новый API endpoint.
    Возвращает:
    - status: "active" / "expired" / "none"
    - expires_at_str: строка даты окончания или None
    """
    try:
        subscription_data = await api_client.get_subscription(telegram_id=telegram_id)
        
        expires_at_str = subscription_data.get("expires_at")
        
        # Основная истина - только expires_at, не полагаемся на has_subscription
        if not expires_at_str:
            return "none", None
        
        if is_subscription_active(expires_at_str):
            return "active", expires_at_str
        
        return "expired", expires_at_str
    except Exception as e:
        print(f"[get_subscription_status] backend error: {e}")
        traceback.print_exc()
        return "none", None


async def get_subscription_status_detailed(telegram_id: int) -> tuple[bool, datetime | None, dict]:
    """
    Получает детальный статус подписки через API endpoint.
    Использует тот же endpoint, что и другие хендлеры.
    
    Возвращает:
    - is_active: True если подписка активна (expires_at > now), иначе False
    - expires_at: datetime объект или None
    - sub_data: полные данные подписки из API
    """
    try:
        sub_data = await api_client.get_subscription(telegram_id=telegram_id)
        
        if not sub_data:
            return False, None, {}
        
        expires_at_str = sub_data.get("expires_at") or getattr(sub_data, "expires_at", None)
        
        if not expires_at_str:
            return False, None, sub_data
        
        # Парсим строку в datetime
        if isinstance(expires_at_str, str):
            # Обрабатываем разные форматы даты
            cleaned = expires_at_str.replace("Z", "+00:00")
            if "+" not in cleaned and "-" in cleaned:
                # Если нет таймзоны, добавляем UTC
                cleaned = cleaned + "+00:00"
            try:
                expires_at = datetime.fromisoformat(cleaned)
            except ValueError:
                # Пробуем без таймзоны
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", ""))
        else:
            expires_at = expires_at_str
        
        # Проверяем активность: expires_at > now
        now = datetime.now(timezone.utc)
        # Если expires_at без таймзоны, сравниваем с naive datetime
        if expires_at.tzinfo is None:
            now = datetime.now(timezone.utc)
        
        expires_at = to_utc(expires_at)
        is_active = bool(expires_at and expires_at > now)
        
        return is_active, expires_at, sub_data
        
    except Exception as e:
        print(f"[get_subscription_status_detailed] backend error: {e}")
        traceback.print_exc()
        return False, None, {}


def format_date_ddmmyyyy(dt_str: str | None) -> str:
    """
    Превращаем "2025-12-12T00:00:00Z" → "12.12.2025"
    Если что-то не так – вернём исходную строку.
    """
    if not dt_str:
        return "—"
    try:
        date_part = dt_str.split("T")[0]  # "2025-12-12"
        y, m, d = date_part.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return dt_str




# Импортируем единую функцию отправки конфига из отдельного модуля
from vpn_config_sender import send_vpn_config


async def send_main_menu(message: Message) -> None:
    """
    Отправляет главное меню в чат.
    """
    await message.answer(
        TEXT_MAIN_MENU,
        reply_markup=main_menu_keyboard
    )


# ===== Команды =====

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    logger.info("CMD_START user_id=%s", message.from_user.id)
    print(f"CMD_START user_id={message.from_user.id}")
    await api_client.ensure_user(telegram_id=message.from_user.id)
    await message.answer(TEXT_START, reply_markup=main_menu_keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(TEXT_HELP)


# ===== Главное меню =====
def to_utc(dt):
    """Приводит datetime к UTC aware. Если None - вернуть None."""
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.replace(tzinfo=timezone.utc)

@router.message(F.text == "🛠 Техническая поддержка")
async def cmd_support(message: Message):
    """Кнопка: Техническая поддержка"""
    await message.answer(TEXT_SUPPORT, reply_markup=main_menu_keyboard)

@router.message(F.text == "🎁 Подключить VPN")
async def cmd_connect_vpn(message: Message):
    """Обработчик кнопки 'Подключить VPN'"""
    logger.info("CMD_CONNECT_VPN user_id=%s", message.from_user.id)
    print(f"CMD_CONNECT_VPN user_id={message.from_user.id}")
    user_id = message.from_user.id
    now = datetime.now(timezone.utc)
    
    # Получаем данные подписки
    try:
        sub_data = await api_client.get_subscription(telegram_id=user_id)
        expires_at_str = sub_data.get("expires_at")
    except Exception as e:
        print(f"[cmd_connect_vpn] Ошибка получения подписки: {e}")
        traceback.print_exc()
        expires_at_str = None
    
    tariffs_text = format_tariffs()
    
    # Маппинг месяцев на callback_data
    months_to_callback = {1: "sub_1m", 3: "sub_3m", 6: "sub_6m", 12: "sub_12m"}
    
    # Создаем кнопки выбора тарифа ОДИН раз ДО проверки is_active
    tariff_buttons = []
    for t in VPN_TARIFFS:
        callback_data = months_to_callback.get(t['months'], f"sub_{t['months']}m")
        logger.info("Creating tariff button: months=%d, callback_data=%s, title=%s, price=%d", 
                   t['months'], callback_data, t['title'], t['price'])
        print(f"Creating tariff button: months={t['months']}, callback_data={callback_data}, title={t['title']}, price={t['price']}")
        tariff_buttons.append([
            InlineKeyboardButton(
                text=f"{t['title']} — {t['price']} ₽",
                callback_data=callback_data
            )
        ])
    
    # Проверяем активность подписки только по expires_at
    is_active = False
    expires_at = None
    
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            expires_at = to_utc(expires_at)
            is_active = bool(expires_at and expires_at > now)
        except Exception as e:
            print(f"[cmd_connect_vpn] Ошибка парсинга даты: {e}")
            traceback.print_exc()
    
    # Если подписки нет или истекла - показываем выбор тарифа
    if not is_active:
        text = (
            "У вас пока нет активной подписки.\n\n"
            f"{tariffs_text}\n\n"
            "Выберите нужный тариф ниже."
        )
        
        tariffs_kb = InlineKeyboardMarkup(inline_keyboard=tariff_buttons)
        logger.info("CMD_CONNECT_VPN: отправка сообщения (неактивная подписка) с %d тарифными кнопками", len(tariff_buttons))
        print(f"CMD_CONNECT_VPN: отправка сообщения (неактивная подписка) с {len(tariff_buttons)} тарифными кнопками")
        try:
            await message.answer(text, reply_markup=tariffs_kb)
            logger.info("CMD_CONNECT_VPN: сообщение отправлено успешно (неактивная подписка)")
            print("CMD_CONNECT_VPN: сообщение отправлено успешно (неактивная подписка)")
        except Exception as e:
            logger.exception("CMD_CONNECT_VPN: ошибка отправки сообщения (неактивная подписка)")
            print(f"CMD_CONNECT_VPN: ошибка отправки сообщения (неактивная подписка): {e}")
            traceback.print_exc()
        return
    
    # Подписка активна - показываем конфиг + подписки + тарифы
    expires_at_str_formatted = expires_at.strftime("%d.%m.%Y")
    
    text = (
        "Ваш VPN:\n\n"
        "• Статус: Активен\n"
        "• Тариф: Платная подписка\n"
        f"• Оплачено до: {expires_at_str_formatted}\n"
        "• Сервер: 🇳🇱 Нидерланды\n\n"
        "Нажмите «Получить конфиг», чтобы подключить устройство.\n\n"
        f"{tariffs_text}\n\n"
        "Выберите тариф ниже для продления."
    )
    
    # Формируем комбинированную клавиатуру: конфиг + подписки + тарифы
    combined = []
    combined.append([InlineKeyboardButton(text="📁 Получить конфиг", callback_data="get_config")])
    combined.append([InlineKeyboardButton(text="📄 Мои подписки", callback_data="my_subscriptions")])
    combined.extend(tariff_buttons)
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=combined)
    logger.info("CMD_CONNECT_VPN: отправка сообщения (активная подписка) с %d кнопками (2 основных + %d тарифных)", len(combined), len(tariff_buttons))
    print(f"CMD_CONNECT_VPN: отправка сообщения (активная подписка) с {len(combined)} кнопками (2 основных + {len(tariff_buttons)} тарифных)")
    try:
        await message.answer(text, reply_markup=reply_markup)
        logger.info("CMD_CONNECT_VPN: сообщение отправлено успешно (активная подписка)")
        print("CMD_CONNECT_VPN: сообщение отправлено успешно (активная подписка)")
    except Exception as e:
        logger.exception("CMD_CONNECT_VPN: ошибка отправки сообщения (активная подписка)")
        print(f"CMD_CONNECT_VPN: ошибка отправки сообщения (активная подписка): {e}")
        traceback.print_exc()


@router.message(F.text == "👤 Личный кабинет")
async def cmd_profile(message: Message):
    """Обработчик кнопки 'Личный кабинет'"""
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Мои подписки", callback_data="my_subscriptions")
    kb.button(text="📥 Мои конфиги", callback_data="my_configs")
    kb.adjust(1)
    
    await message.answer("👤 Личный кабинет", reply_markup=kb.as_markup())


# ===== Callback handlers =====

@router.callback_query(F.data == "get_config")
async def cb_get_config(callback: CallbackQuery):
    """Обработчик получения конфига"""
    logger.info("HANDLER get_config user_id=%s", callback.from_user.id)
    print(f"HANDLER get_config user_id={callback.from_user.id}")
    await callback.answer()
    telegram_id = callback.from_user.id
    
    # Отправляем конфиг (backend сам проверит подписку)
    await send_vpn_config(callback.bot, telegram_id)


@router.callback_query(F.data == "my_subscriptions")
async def cb_my_subscriptions(callback: CallbackQuery):
    """Обработчик раздела 'Мои подписки'"""
    logger.info("HANDLER my_subscriptions user_id=%s", callback.from_user.id)
    print(f"HANDLER my_subscriptions user_id={callback.from_user.id}")
    await callback.answer()
    telegram_id = callback.from_user.id
    
    # Используем единую функцию для получения статуса подписки
    # (тот же endpoint, что и в других хендлерах)
    is_active, expires_at, sub_data = await get_subscription_status_detailed(telegram_id)
    
    tariffs_text = format_tariffs()
    
    # Маппинг месяцев на callback_data
    months_to_callback = {1: "sub_1m", 3: "sub_3m", 6: "sub_6m", 12: "sub_12m"}
    
    # Создаем кнопки для тарифов (кликабельные)
    tariff_buttons = []
    for t in VPN_TARIFFS:
        callback_data = months_to_callback.get(t['months'], f"sub_{t['months']}m")
        logger.info("Creating tariff button in my_subscriptions: months=%d, callback_data=%s, title=%s, price=%d", 
                   t['months'], callback_data, t['title'], t['price'])
        print(f"Creating tariff button in my_subscriptions: months={t['months']}, callback_data={callback_data}, title={t['title']}, price={t['price']}")
        tariff_buttons.append([
            InlineKeyboardButton(
                text=f"{t['title']} — {t['price']} ₽",
                callback_data=callback_data
            )
        ])
    
    # Если подписки нет или истекла
    if not is_active:
        text = (
            "У вас нет активной подписки.\n\n"
            f"{tariffs_text}\n\n"
            "Выберите тариф ниже для оплаты."
        )
        
        kb = InlineKeyboardBuilder()
        # Добавляем кнопки тарифов
        for tariff_row in tariff_buttons:
            kb.row(*tariff_row)
        # Кнопка "Назад"
        kb.button(text="🔙 Назад", callback_data="back_to_main")
        kb.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        return
    
    # Если подписка активна
    expires_at_str = expires_at.strftime("%d.%m.%Y")
    plan_name = sub_data.get("plan_name") or "Платная подписка"
    
    text = (
        "Ваши подписки:\n\n"
        "• Статус: Активна\n"
        f"• Тариф: {plan_name}\n"
        f"• Оплачено до: {expires_at_str}\n"
        "• Сервер: 🇳🇱 Нидерланды\n\n"
        f"{tariffs_text}\n\n"
        "Выберите тариф ниже для продления подписки."
    )
    
    kb = InlineKeyboardBuilder()
    # Добавляем кнопки тарифов
    for tariff_row in tariff_buttons:
        kb.row(*tariff_row)
    # Кнопка "Назад"
    kb.button(text="🔙 Назад", callback_data="back_to_main")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "my_configs")
async def cb_my_configs(callback: CallbackQuery):
    """Обработчик раздела 'Мои конфиги'"""
    await callback.answer()
    user_id = callback.from_user.id
    
    # Проверяем подписку
    status, _ = await get_subscription_status(user_id)
    if status != "active":
        await callback.message.answer(
            "❌ У вас нет активной подписки.\n"
            "Сначала оформите подписку, чтобы получить конфиг."
        )
        return
    
    text = TEXT_CONFIGS
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Телефон", callback_data="config_phone")
    kb.button(text="💻 Ноутбук", callback_data="config_laptop")
    kb.button(text="🔙 Назад", callback_data="back_to_main")
    kb.adjust(1)
    
    await callback.message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.in_(("config_phone", "config_laptop")))
async def cb_config_device(callback: CallbackQuery):
    """Обработчик выбора устройства для конфига"""
    await callback.answer()
    user_id = callback.from_user.id
    device_type = "phone" if callback.data == "config_phone" else "laptop"
    device_name = "Телефон" if device_type == "phone" else "Ноутбук"
    
    # Проверяем подписку
    status, _ = await get_subscription_status(user_id)
    if status != "active":
        await callback.message.answer(
            f"❌ У вас нет активной подписки.\n"
            "Сначала оформите подписку, чтобы получить конфиг."
        )
        return
    
    # Показываем меню выбора способа получения конфига
    if device_type == "phone":
        text = TEXT_PHONE_CONFIG
    else:
        text = TEXT_LAPTOP_CONFIG
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Файл (.conf)", callback_data=f"config_file_{device_type}")
    kb.button(text="🔙 Назад", callback_data="my_configs")
    kb.adjust(1)
    
    await callback.message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("config_file_"))
async def cb_config_file(callback: CallbackQuery):
    """Обработчик получения конфига как файла"""
    await callback.answer()
    device_type = callback.data.replace("config_file_", "")
    telegram_id = callback.from_user.id
    device_name = "Телефон" if device_type == "phone" else "Ноутбук"
    
    # Отправляем конфиг (backend сам проверит подписку)
    await send_vpn_config(callback.bot, telegram_id, filename=f"vpn_{device_name.lower()}.conf")


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    """Обработчик кнопки 'Назад в главное меню'"""
    await callback.answer()
    # Убираем inline-клавиатуру, если сообщение было с ней
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await send_main_menu(callback.message)


@router.callback_query(F.data.in_(("sub_1m", "sub_3m", "sub_6m", "sub_12m")))
async def cb_subscription_tariff(callback: CallbackQuery):
    """Универсальный обработчик выбора тарифа подписки"""
    logger.info("🔥 HANDLER subscription_tariff ВЫЗВАН user_id=%s data=%s", callback.from_user.id, callback.data)
    print(f"🔥 HANDLER subscription_tariff ВЫЗВАН user_id={callback.from_user.id} data={callback.data}")
    
    try:
        # Сразу отвечаем на callback, чтобы убрать "крутилку"
        await callback.answer()
        logger.info("✅ HANDLER subscription_tariff: call.answer() выполнен")
        print("✅ HANDLER subscription_tariff: call.answer() выполнен")
    except Exception as e:
        logger.exception("❌ HANDLER subscription_tariff: ошибка в call.answer(): %s", e)
        print(f"❌ HANDLER subscription_tariff: ошибка в call.answer(): {e}")
        return
    
    # Маппинг callback_data на количество месяцев
    tariff_map = {
        "sub_1m": 1,
        "sub_3m": 3,
        "sub_6m": 6,
        "sub_12m": 12,
    }
    
    months = tariff_map.get(callback.data)
    if not months:
        logger.error("HANDLER subscription_tariff: некорректный callback_data=%s", callback.data)
        await callback.message.answer("❌ Ошибка: некорректный тариф.")
        return
    
    # Находим тариф в конфигурации
    tariff = next((t for t in VPN_TARIFFS if t["months"] == months), None)
    if not tariff:
        logger.error("HANDLER subscription_tariff: тариф с months=%d не найден", months)
        await callback.message.answer("❌ Ошибка: тариф не найден.")
        return
    
    price = tariff["price"]
    title = tariff["title"]
    logger.info("HANDLER subscription_tariff: найден тариф title=%s price=%d months=%d", title, price, months)
    print(f"HANDLER subscription_tariff: найден тариф title={title} price={price} months={months}")
    
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
        logger.info("HANDLER subscription_tariff: пытаемся отредактировать сообщение")
        print("HANDLER subscription_tariff: пытаемся отредактировать сообщение")
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        logger.info("HANDLER subscription_tariff: сообщение успешно отредактировано")
        print("HANDLER subscription_tariff: сообщение успешно отредактировано")
    except Exception as e:
        # Если редактирование не удалось (сообщение уже удалено/отредактировано), отправляем новое
        logger.warning("HANDLER subscription_tariff: не удалось отредактировать сообщение: %s, отправляем новое", e)
        print(f"HANDLER subscription_tariff: не удалось отредактировать сообщение: {e}, отправляем новое")
        try:
            await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            logger.info("HANDLER subscription_tariff: новое сообщение успешно отправлено")
            print("HANDLER subscription_tariff: новое сообщение успешно отправлено")
        except Exception as e2:
            logger.exception("HANDLER subscription_tariff: критическая ошибка при отправке сообщения")
            print(f"HANDLER subscription_tariff: критическая ошибка при отправке сообщения: {e2}")
            # Пытаемся хотя бы отправить простое сообщение
            try:
                await callback.message.answer(f"Вы выбрали тариф: {title} — {price} ₽. Оплатите по реквизитам и нажмите «✅ Я оплатил».")
            except:
                pass


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    logger.info("INCOMING MESSAGE: text=%s chat_id=%s", message.text, message.chat.id)
    if not is_admin(message.chat.id):
        await message.answer("❌ Нет доступа")
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin:stats")
    kb.button(text="⏳ Истекают ≤24ч", callback_data="admin:exp24")
    kb.button(text="⛔️ Отключены за 24ч", callback_data="admin:rev24")
    kb.button(text="🔎 Поиск по telegram_id", callback_data="admin:find")
    kb.button(text="👥 Пользователи", callback_data="admin:users:0")
    kb.adjust(1)
    await message.answer("🔐 Админ-панель", reply_markup=kb.as_markup())

@router.callback_query(F.data == "admin:stats")
async def admin_callback_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        data = await api_client.get_admin_stats()
        text = (
            "📊 Статистика\n\n"
            f"Активных подписок: {data.get('active_subs', 0)}\n"
            f"Истекло за 24ч: {data.get('expired_24h', 0)}\n"
            f"Отключено VPN за 24ч: {data.get('revoked_24h', 0)}\n"
            f"Истекают ≤24ч: {data.get('expiring_24h', 0)}"
        )
        await callback.message.edit_text(text)
        await callback.answer()
    except Exception as e:
        logger.exception("Ошибка получения статистики")
        await callback.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "admin:exp24")
async def admin_callback_exp24(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        data = await api_client.get_admin_expiring()
        items = data.get('items', [])
        if not items:
            text = "⏳ Нет подписок, истекающих в ближайшие 24 часа"
        else:
            lines = ["⏳ Истекают ≤24ч:"]
            for item in items[:20]:
                expires_at = item.get('expires_at', '')
                lines.append(
                    f"user_id={item.get('user_id')} tg={item.get('telegram_id')} "
                    f"sub_id={item.get('subscription_id')} expires={expires_at[:19]}"
                )
            text = "\n".join(lines)
        await callback.message.edit_text(text)
        await callback.answer()
    except Exception as e:
        logger.exception("Ошибка списка истекающих")
        await callback.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "admin:rev24")
async def admin_callback_rev24(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        data = await api_client.get_admin_revoked()
        items = data.get('items', [])
        if not items:
            text = "⛔️ Нет отключенных peer за последние 24 часа"
        else:
            lines = ["⛔️ Отключены за 24ч:"]
            for item in items[:20]:
                revoked_at = item.get('revoked_at', '')
                expire_at = item.get('expire_at', '') or 'N/A'
                lines.append(
                    f"peer_id={item.get('peer_id')} user_id={item.get('user_id')} "
                    f"tg={item.get('telegram_id')} revoked={revoked_at[:19]} expire={expire_at[:19]}"
                )
            text = "\n".join(lines)
        await callback.message.edit_text(text)
        await callback.answer()
    except Exception as e:
        logger.exception("Ошибка списка отключенных")
        await callback.answer(f"Ошибка: {e}", show_alert=True)

_admin_search_state = set()

@router.callback_query(F.data == "admin:find")
async def admin_callback_find(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    _admin_search_state.add(callback.from_user.id)
    await callback.message.edit_text("🔎 Пришлите telegram_id числом")
    await callback.answer()

@router.message(F.text.regexp(r"^\d+$"))
async def admin_search_user(message: Message):
    if not is_admin(message.chat.id):
        return
    if message.from_user.id not in _admin_search_state:
        return
    _admin_search_state.discard(message.from_user.id)
    try:
        tg_id = int(message.text.strip())
        data = await api_client.get_admin_user_info(tg_id)
        lines = [f"👤 Пользователь:\nuser_id={data.get('user_id')} telegram_id={data.get('telegram_id')}"]
        if data.get('subscription'):
            sub = data['subscription']
            expires = sub.get('expires_at', '')[:19] if sub.get('expires_at') else 'N/A'
            lines.append(f"\n📅 Подписка: status={sub.get('status')} expires_at={expires}")
        else:
            lines.append("\n📅 Подписка: нет")
        if data.get('peer'):
            peer = data['peer']
            revoked = peer.get('revoked_at', '')[:19] if peer.get('revoked_at') else 'N/A'
            expire = peer.get('expire_at', '')[:19] if peer.get('expire_at') else 'N/A'
            lines.append(f"\n🔌 Peer: peer_id={peer.get('id')} is_active={peer.get('is_active')} revoked_at={revoked} expire_at={expire}")
        else:
            lines.append("\n🔌 Peer: нет")
        text_resp = "\n".join(lines)
        await message.answer(text_resp)
    except Exception as e:
        logger.exception("Ошибка поиска пользователя")
        await message.answer(f"Ошибка: {e}")

@router.callback_query(F.data.startswith("admin:users:"))
async def admin_callback_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    logger.info("ADMIN USERS CLICK: data=%s chat_id=%s", callback.data, callback.message.chat.id)
    try:
        offset = int(callback.data.split(":")[-1])
        limit = 15
        data = await api_client.admin_users(limit=limit, offset=offset)
        items = data.get("items", [])
        has_more = data.get("has_more", False)
        if not items:
            text = "👥 Пользователи\n\nПользователи не найдены"
        else:
            lines = [f"👥 Пользователи (offset={offset})"]
            for idx, item in enumerate(items, 1):
                user_id = item.get("user_id", "N/A")
                tg_id = item.get("telegram_id", "N/A")
                sub_status = item.get("sub_status", "none")
                sub_expires = item.get("sub_expires_at", "")
                peer_id = item.get("peer_id")
                peer_active = item.get("peer_active")
                peer_revoked = item.get("peer_revoked_at")
                if sub_status == "active":
                    if sub_expires:
                        from datetime import datetime
                        try:
                            expires_dt = datetime.fromisoformat(sub_expires.replace("Z", "+00:00"))
                            now = datetime.now(timezone.utc)
                            status_icon = "⏳" if (expires_dt - now).total_seconds() < 86400 else "✅"
                        except Exception:
                            status_icon = "✅"
                    else:
                        status_icon = "✅"
                    sub_text = f"sub до {sub_expires[:19] if sub_expires else 'N/A'}" if sub_expires else "sub активна"
                elif sub_status == "expired":
                    status_icon = "❌"
                    sub_text = f"sub истек {sub_expires[:19] if sub_expires else 'N/A'}" if sub_expires else "sub истекла"
                else:
                    status_icon = "—"
                    sub_text = "без подписки"
                if peer_id:
                    peer_text = "peer=active" if (peer_active and not peer_revoked) else "peer=revoked"
                else:
                    peer_text = "peer=-"
                lines.append(f"{idx}) user_id={user_id} tg={tg_id} {status_icon} {sub_text} | {peer_text}")
            text = "\n".join(lines)
        keyboard = InlineKeyboardBuilder()
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(("◀️ Назад", f"admin:users:{max(0, offset - limit)}"))
        if has_more:
            nav_buttons.append(("▶️ Вперёд", f"admin:users:{offset + limit}"))
        for btn_text, btn_data in nav_buttons:
            keyboard.button(text=btn_text, callback_data=btn_data)
        if nav_buttons:
            keyboard.adjust(len(nav_buttons))
        keyboard.button(text="🔎 Открыть", callback_data="admin:find")
        keyboard.button(text="⬅️ Меню", callback_data="admin:menu")
        keyboard.adjust(1)
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
        await callback.answer()
    except Exception as e:
        logger.exception("Ошибка списка пользователей")
        await callback.answer(f"Ошибка: {e}", show_alert=True)

# Удален общий обработчик _debug_all_callbacks, чтобы не перехватывать callback'и для тарифов
# Если нужен общий обработчик для отладки, его можно добавить с фильтром, исключающим тарифы

async def main() -> None:
    # Проверяем наличие BOT_TOKEN
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен в переменных окружения!")
        print("Установите BOT_TOKEN в файле .env или через переменные окружения")
        return
    
    # Создаем TCPConnector с настройками для стабильного подключения к Telegram API
    import socket
    connector = TCPConnector(
        force_close=True,
        enable_cleanup_closed=True,
        limit=100,
        limit_per_host=30,
        ttl_dns_cache=300,
        use_dns_cache=True,
        family=socket.AF_INET,  # Принудительно используем IPv4
    )
    
    # В aiogram 3.x создаем AiohttpSession с кастомным connector
    from aiogram.client.session.aiohttp import AiohttpSession
    
    # Создаем сессию aiohttp с настроенным connector
    session = ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
    )
    
    # Создаем AiohttpSession с кастомной сессией
    aiohttp_session = AiohttpSession()
    aiohttp_session._session = session
    
    # Создаем Bot с кастомной сессией для контроля подключения
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=aiohttp_session,
    )
    
    dp = Dispatcher()
    # Добавляем middleware для логирования всех апдейтов
    dp.message.middleware(UpdateLoggingMiddleware())
    dp.callback_query.middleware(UpdateLoggingMiddleware())
    dp.include_router(router)
    
    # Подключаем routers для ручной оплаты
    if manual_payment_router:
        dp.include_router(manual_payment_router)
        print(f"[bot_main] ✅ Manual payment router подключен к dispatcher")
    else:
        print(f"[bot_main] ⚠️ Manual payment router не подключен (manual_payment_router is None)")
    
    if tariffs_router:
        dp.include_router(tariffs_router)
        print(f"[bot_main] ✅ Tariffs router подключен к dispatcher")
    else:
        print(f"[bot_main] ⚠️ Tariffs router не подключен (tariffs_router is None)")
    
    if admin_confirm_router:
        dp.include_router(admin_confirm_router)
        print(f"[bot_main] ✅ Admin confirm router подключен к dispatcher")
    else:
        print(f"[bot_main] ⚠️ Admin confirm router не подключен (admin_confirm_router is None)")
    
    print("🚀 Bot started...")
    print(f"[bot_main] Используется кастомная сессия с оптимизированным connector для Telegram API")
    # Проверяем, что webhook удален перед стартом polling
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"[bot_main] ⚠️ Обнаружен активный webhook: {webhook_info.url}, удаляем...")
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("[bot_main] ✅ Webhook удален")
        else:
            logger.info("[bot_main] ✅ Webhook не установлен, можно запускать polling")
    except Exception as e:
        logger.warning(f"[bot_main] ⚠️ Ошибка при проверке webhook: {e}, продолжаем...")
    
    logger.info(f"[bot_main] 🚀 Запуск polling для бота (token: {BOT_TOKEN[:6]}...{BOT_TOKEN[-4:] if len(BOT_TOKEN) > 10 else '****'})")
    
    print("START_POLLING")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e:
        print("POLLING_CRASH")
        raise
    finally:
        print("POLLING_STOPPED")
        await session.close()
        await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
