from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# =========================
# ГЛАВНОЕ МЕНЮ (reply-клава)
# =========================

main_menu_keyboard = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [
            KeyboardButton(text="🎁 Подключить VPN"),
        ],
        [
            KeyboardButton(text="👤 Личный кабинет"),
        ],
        [
            KeyboardButton(text="🧪 Пробный доступ (1 день)"),
        ],
    ],
)


# =====================================
# КНОПКИ ПОД "ПОДКЛЮЧИТЬ VPN" (inline)
# =====================================

# Показываем, когда пользователь нажал "Подключить VPN"
# (и в зависимости от статуса подписки меняем только текст, а клавиатура одна и та же)

connect_vpn_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📥 Получить конфиг",
                callback_data="get_config",   # обработчик: выдача конфига
            )
        ],
        [
            InlineKeyboardButton(
                text="♻️ Продлить подписку",
                callback_data="renew_subscription",  # обработчик: показать тарифы
            )
        ],
        [
            InlineKeyboardButton(
                text="🆘 Поддержка",
                callback_data="support",  # обработчик: переход в поддержку
            )
        ],
    ]
)


# =====================================
# КНОПКИ ЛИЧНОГО КАБИНЕТА (inline)
# =====================================

profile_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📥 Мои конфиги",
                callback_data="my_configs",   # обработчик: список устройств
            )
        ],
        [
            InlineKeyboardButton(
                text="♻️ Продлить подписку",
                callback_data="renew_subscription",
            )
        ],
        [
            InlineKeyboardButton(
                text="🆘 Поддержка",
                callback_data="support",
            )
        ],
    ]
)


# =====================================
# КНОПКИ "МОИ КОНФИГИ" (inline)
# =====================================

configs_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Телефон",
                callback_data="config_phone",
            )
        ],
        [
            InlineKeyboardButton(
                text="💻 Ноутбук",
                callback_data="config_laptop",
            )
        ],
        [
            InlineKeyboardButton(
                text="➕ Добавить устройство",
                callback_data="add_device",
            )
        ],
    ]
)


# =====================================
# КНОПКИ "КОНФИГ ДЛЯ ТЕЛЕФОНА/НОУТБУКА" (inline)
# =====================================

config_delivery_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📷 QR-код",
                callback_data="config_qr",
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 Файл (.conf)",
                callback_data="config_file",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Ссылка",
                callback_data="config_link",
            )
        ],
    ]
)


# =====================================
# КНОПКА "НАЗАД В ГЛАВНОЕ МЕНЮ" (по желанию)
# =====================================

back_to_main_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬅️ Назад в меню",
                callback_data="back_to_main",
            )
        ],
    ]
)


# =====================================
# КНОПКА "✅ ОПЛАТИЛ" (inline)
# =====================================

# Клавиатура manual_payment_kb больше не используется напрямую
# Вместо неё используется динамическая клавиатура с months в callback_data
# Оставлена для совместимости, но лучше использовать choose_tariff
manual_payment_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Я оплатил",
                callback_data="manual_paid:0"  # 0 означает "не выбран тариф"
            )
        ]
    ]
)


# =====================================
# КЛАВИАТУРА ДЛЯ АКТИВНОЙ ПОДПИСКИ VPN
# =====================================

vpn_main_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📁 Получить конфиг",
                callback_data="get_config"
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 Мои подписки",
                callback_data="my_subscriptions"
            )
        ]
    ]
)

