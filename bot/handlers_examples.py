"""
Примеры использования клавиатур и текстов в обработчиках бота.

Этот файл содержит примеры обработчиков для aiogram 3.x,
которые используют клавиатуры из keyboards.py и тексты из texts.py.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from keyboards import (
    main_menu_keyboard,
    connect_vpn_keyboard,
    profile_keyboard,
    configs_keyboard,
    config_delivery_keyboard,
    renew_keyboard,
    pay_keyboard,
    back_to_main_keyboard,
)
from texts import (
    TEXT_START,
    TEXT_VPN_NO_SUB,
    TEXT_VPN_EXPIRED,
    TEXT_VPN_READY,
    TEXT_PROFILE_ACTIVE,
    TEXT_PROFILE_NO_SUB,
    TEXT_CONFIGS,
    TEXT_PHONE_CONFIG,
    TEXT_LAPTOP_CONFIG,
    TEXT_CONFIG_NO_ACCESS,
    TEXT_CONFIG_LINK,
    TEXT_RENEW,
    TEXT_PAY,
    TEXT_HELP,
)

# Предполагаем, что у вас уже есть функция get_subscription_status
# из bot_main.py
from bot_main import get_subscription_status, BACKEND_URL
from aiohttp import ClientSession

router = Router()


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def build_config_url(user_id: int, device: str = "default") -> str:
    """
    Строим ссылку на конфиг для конкретного устройства.
    TODO: Замените на реальную ссылку вашего бекенда.
    """
    base_url = "https://your-domain.example/api/wg"  # TODO: подставьте свой домен
    return f"{base_url}/{user_id}?device={device}"


# ============================================
# /start – одно приветствие + главное меню
# ============================================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Регистрация пользователя в backend (если нужно)
    async with ClientSession() as session:
        payload = {
            "telegram_id": message.from_user.id,
            "username": message.from_user.username or "",
        }
        try:
            await session.post(f"{BACKEND_URL}/api/users/by-telegram", json=payload)
        except Exception as e:
            print(f"[start] backend error: {e}")

    # ОДИН раз отправляем приветствие и сразу показываем главное меню
    await message.answer(TEXT_START, reply_markup=main_menu_keyboard)


# ============================================
# Кнопка "🔐 Подключить VPN" (reply-клавиатура)
# ============================================

@router.message(F.text == "🔐 Подключить VPN")
async def on_connect_vpn(message: Message):
    """Обработчик кнопки 'Подключить VPN' из reply-клавиатуры"""
    user_id = message.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status == "active":
        text = TEXT_VPN_READY
    elif sub_status == "expired":
        text = TEXT_VPN_EXPIRED
    else:
        text = TEXT_VPN_NO_SUB

    await message.answer(text, reply_markup=connect_vpn_keyboard)


# ============================================
# Кнопка "👤 Личный кабинет" (reply-клавиатура)
# ============================================

@router.message(F.text == "👤 Личный кабинет")
async def on_profile(message: Message):
    """Обработчик кнопки 'Личный кабинет' из reply-клавиатуры"""
    user_id = message.from_user.id
    sub_status, expires_at_str = await get_subscription_status(user_id)

    if sub_status == "active":
        # TODO: здесь подставьте реальную дату окончания подписки
        # например, возьмите subscription.expires_at из вашей модели
        try:
            if expires_at_str:
                cleaned = expires_at_str.replace("Z", "")
                if "+" in cleaned:
                    cleaned = cleaned.split("+", 1)[0]
                expires_at = datetime.fromisoformat(cleaned)
                date_str = expires_at.strftime("%d.%m.%Y")
            else:
                date_str = "—"
        except Exception:
            date_str = expires_at_str or "—"

        text = TEXT_PROFILE_ACTIVE.format(date=date_str)
    else:
        text = TEXT_PROFILE_NO_SUB

    await message.answer(text, reply_markup=profile_keyboard)


# ============================================
# Кнопка "❓ Помощь" (reply-клавиатура)
# ============================================

@router.message(F.text == "❓ Помощь")
async def on_help(message: Message):
    """Обработчик кнопки 'Помощь' из reply-клавиатуры"""
    await message.answer(TEXT_HELP)


# ============================================
# INLINE CALLBACK-ХЕНДЛЕРЫ
# ============================================

# ---- Мои конфиги (из личного кабинета) ----

@router.callback_query(F.data == "my_configs")
async def cb_my_configs(callback: CallbackQuery):
    """Обработчик кнопки 'Мои конфиги'"""
    await callback.message.answer(TEXT_CONFIGS, reply_markup=configs_keyboard)
    await callback.answer()


# ---- Выбор устройства: Телефон / Ноутбук ----

@router.callback_query(F.data == "config_phone")
async def cb_config_phone(callback: CallbackQuery):
    """Обработчик выбора конфига для телефона"""
    user_id = callback.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status != "active":
        await callback.message.answer(TEXT_CONFIG_NO_ACCESS)
        await callback.answer()
        return

    await callback.message.answer(TEXT_PHONE_CONFIG, reply_markup=config_delivery_keyboard)
    await callback.answer()


@router.callback_query(F.data == "config_laptop")
async def cb_config_laptop(callback: CallbackQuery):
    """Обработчик выбора конфига для ноутбука"""
    user_id = callback.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status != "active":
        await callback.message.answer(TEXT_CONFIG_NO_ACCESS)
        await callback.answer()
        return

    await callback.message.answer(TEXT_LAPTOP_CONFIG, reply_markup=config_delivery_keyboard)
    await callback.answer()


# ---- Доставка конфига: QR / файл / ссылка ----

@router.callback_query(F.data == "config_qr")
async def cb_config_qr(callback: CallbackQuery):
    """Обработчик запроса QR-кода конфига"""
    user_id = callback.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status != "active":
        await callback.message.answer(TEXT_CONFIG_NO_ACCESS)
        await callback.answer()
        return

    # TODO: здесь вызывайте свой существующий код, который отправляет QR-код
    # пример:
    # async with ClientSession() as session:
    #     async with session.get(f"{BACKEND_URL}/api/vpn/qr/{user_id}") as r:
    #         qr_bytes = await r.read()
    #         await callback.message.answer_photo(qr_bytes)

    await callback.answer()


@router.callback_query(F.data == "config_file")
async def cb_config_file(callback: CallbackQuery):
    """Обработчик запроса файла конфига"""
    user_id = callback.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status != "active":
        await callback.message.answer(TEXT_CONFIG_NO_ACCESS)
        await callback.answer()
        return

    # TODO: здесь вызывайте свой существующий код, который отправляет .conf файл
    # пример:
    # async with ClientSession() as session:
    #     async with session.get(f"{BACKEND_URL}/api/vpn/config/{user_id}") as r:
    #         cfg_data = await r.json()
    #         config_text = cfg_data.get("config")
    #         # Отправка файла...

    await callback.answer()


@router.callback_query(F.data == "config_link")
async def cb_config_link(callback: CallbackQuery):
    """Обработчик запроса ссылки на конфиг"""
    user_id = callback.from_user.id
    sub_status, _ = await get_subscription_status(user_id)

    if sub_status != "active":
        await callback.message.answer(TEXT_CONFIG_NO_ACCESS)
        await callback.answer()
        return

    # Формируем ссылку на конфиг
    config_url = build_config_url(user_id=user_id, device="default")

    await callback.message.answer(TEXT_CONFIG_LINK.format(config_url=config_url))
    await callback.answer()


# ============================================
# Продление подписки
# ============================================

@router.callback_query(F.data == "renew_subscription")
async def cb_renew_subscription(callback: CallbackQuery):
    """Обработчик кнопки 'Продлить подписку'"""
    await callback.message.answer(TEXT_RENEW, reply_markup=renew_keyboard)
    await callback.answer()


# Выбор тарифа
@router.callback_query(F.data.in_(["renew_1m", "renew_3m", "renew_6m", "renew_12m"]))
async def cb_choose_tariff(callback: CallbackQuery):
    """Обработчик выбора тарифа продления"""
    # Здесь можете сохранить выбранный тариф в БД или FSM
    # TODO: реализуйте логику сохранения выбранного тарифа

    await callback.message.answer(TEXT_PAY, reply_markup=pay_keyboard)
    await callback.answer()


# Нажатие "Оплатить"
@router.callback_query(F.data == "pay")
async def cb_pay(callback: CallbackQuery):
    """Обработчик кнопки 'Оплатить'"""
    user_id = callback.from_user.id

    # TODO: здесь вызывайте свой код, который создаёт ссылку/инвойс на оплату
    # Например, создаёте платёж в ЮKassa / Crypto / Stripe и отправляете ссылку
    # пример:
    # async with ClientSession() as session:
    #     async with session.post(f"{BACKEND_URL}/api/payments/create", json={"user_id": user_id}) as r:
    #         payment_data = await r.json()
    #         payment_url = payment_data.get("payment_url")
    #         await callback.message.answer(f"Ссылка на оплату: {payment_url}")

    await callback.answer()


# ============================================
# Поддержка
# ============================================

@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    """Обработчик кнопки 'Поддержка'"""
    from texts import TEXT_SUPPORT
    await callback.message.answer(TEXT_SUPPORT)
    await callback.answer()


# ============================================
# Назад в главное меню
# ============================================

@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    """Обработчик кнопки 'Назад в меню'"""
    await callback.message.answer(TEXT_START, reply_markup=main_menu_keyboard)
    await callback.answer()

