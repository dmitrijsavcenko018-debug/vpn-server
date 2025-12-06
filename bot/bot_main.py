import asyncio
import os
import traceback
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
)
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
    TEXT_CONFIG_LINK,
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

# Устанавливаем api_client для модуля vpn_config_sender
set_api_client(api_client)


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
        now = datetime.utcnow()
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
            now = datetime.utcnow()
        
        is_active = expires_at > now
        
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
    await api_client.ensure_user(telegram_id=message.from_user.id)
    await message.answer(TEXT_START, reply_markup=main_menu_keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(TEXT_HELP)


# ===== Главное меню =====

@router.message(F.text == "🎁 Подключить VPN")
async def cmd_connect_vpn(message: Message):
    """Обработчик кнопки 'Подключить VPN'"""
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
    
    # Проверяем активность подписки только по expires_at
    is_active = False
    expires_at = None
    
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            is_active = expires_at > now
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
        
        # Создаем кнопки выбора тарифа
        tariff_buttons = [
            [
                InlineKeyboardButton(
                    text=f"{t['title']} — {t['price']} ₽",
                    callback_data=f"choose_tariff:{t['months']}"
                )
            ]
            for t in VPN_TARIFFS
        ]
        tariffs_kb = InlineKeyboardMarkup(inline_keyboard=tariff_buttons)
        
        await message.answer(text, reply_markup=tariffs_kb)
        return
    
    # Подписка активна
    expires_at_str_formatted = expires_at.strftime("%d.%m.%Y")
    
    text = (
        "Ваш VPN:\n\n"
        "• Статус: Активен\n"
        "• Тариф: Платная подписка\n"
        f"• Оплачено до: {expires_at_str_formatted}\n"
        "• Сервер: 🇳🇱 Нидерланды\n\n"
        "Нажмите «Получить конфиг», чтобы подключить устройство.\n\n"
        f"{tariffs_text}\n\n"
        "Чтобы продлить, оплатите нужный тариф по номеру телефона и после оплаты нажмите «✅ Я оплатил»."
    )
    
    await message.answer(text, reply_markup=vpn_main_kb)


@router.message(F.text == "👤 Личный кабинет")
async def cmd_profile(message: Message):
    """Обработчик кнопки 'Личный кабинет'"""
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Мои подписки", callback_data="my_subscriptions")
    kb.button(text="📥 Мои конфиги", callback_data="my_configs")
    kb.adjust(1)
    
    await message.answer("👤 Личный кабинет", reply_markup=kb.as_markup())


@router.message(F.text == "🧪 Пробный доступ (1 день)")
async def handle_trial_access(message: Message):
    """Обработчик пробного доступа на 1 день"""
    telegram_id = message.from_user.id
    
    try:
        # Активируем тестовую подписку через backend
        result = await api_client.activate_test_subscription(telegram_id=telegram_id)
        
        if result:
            # После успешной активации отправляем конфиг
            await send_vpn_config(message.bot, telegram_id)
        else:
            await message.answer(
                "❌ Ошибка при активации пробного доступа.\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
    except Exception as e:
        print(f"[handle_trial_access] Ошибка: {e}")
        traceback.print_exc()
        await message.answer(
            "❌ Ошибка при активации пробного доступа.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )


# ===== Callback handlers =====

@router.callback_query(F.data == "get_config")
async def cb_get_config(callback: CallbackQuery):
    """Обработчик получения конфига"""
    await callback.answer()
    telegram_id = callback.from_user.id
    
    # Отправляем конфиг (backend сам проверит подписку)
    await send_vpn_config(callback.bot, telegram_id)


@router.callback_query(F.data == "my_subscriptions")
async def cb_my_subscriptions(callback: CallbackQuery):
    """Обработчик раздела 'Мои подписки'"""
    await callback.answer()
    telegram_id = callback.from_user.id
    
    # Используем единую функцию для получения статуса подписки
    # (тот же endpoint, что и в других хендлерах)
    is_active, expires_at, sub_data = await get_subscription_status_detailed(telegram_id)
    
    tariffs_text = format_tariffs()
    
    # Создаем кнопки для тарифов (кликабельные)
    tariff_buttons = [
        [
            InlineKeyboardButton(
                text=f"{t['title']} — {t['price']} ₽",
                callback_data=f"choose_tariff:{t['months']}"
            )
        ]
        for t in VPN_TARIFFS
    ]
    
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
    kb.button(text="🔗 Ссылка", callback_data=f"config_link_{device_type}")
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


@router.callback_query(F.data.startswith("config_link_"))
async def cb_config_link(callback: CallbackQuery):
    """Обработчик получения ссылки на конфиг"""
    await callback.answer()
    device_type = callback.data.replace("config_link_", "")
    user_id = callback.from_user.id
    device_name = "Телефон" if device_type == "phone" else "Ноутбук"
    
    # Проверяем подписку
    status, _ = await get_subscription_status(user_id)
    if status != "active":
        await callback.message.answer(
            "❌ У вас нет активной подписки.\n"
            "Сначала оформите подписку, чтобы получить конфиг."
        )
        return
    
    # Получаем config_url из backend
    try:
        config_data = await api_client.get_vpn_config(telegram_id=user_id)
        config_url = config_data.get("config_url")
        
        if not config_url:
            await callback.message.answer(
                "❌ Ссылка на конфиг недоступна.\n"
                "Попробуйте получить конфиг как файл."
            )
            return
        
        text = f"📱 *Конфиг — {device_name}*\n\n{TEXT_CONFIG_LINK.format(config_url=config_url)}"
        
        kb = InlineKeyboardBuilder()
        kb.button(text="🔗 Открыть ссылку", url=config_url)
        kb.button(text="🔙 Назад", callback_data=f"config_{device_type}")
        kb.adjust(1)
        
        await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"[cb_config_link] Ошибка: {e}")
        await callback.message.answer(
            "❌ Ошибка при получении ссылки на конфиг.\n"
            "Попробуйте получить конфиг как файл."
        )


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    """Обработчик кнопки 'Назад в главное меню'"""
    await callback.answer()
    await send_main_menu(callback.message)


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
    
    try:
        await dp.start_polling(bot)
    finally:
        await session.close()
        await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
