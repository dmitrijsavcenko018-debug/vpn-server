"""
Конфигурация тарифов VPN-сервиса
"""

VPN_TARIFFS = [
    {"months": 1, "title": "1 месяц", "price": 249},
    {"months": 3, "title": "3 месяца", "price": 599},
    {"months": 6, "title": "6 месяцев", "price": 1049},
    {"months": 12, "title": "12 месяцев", "price": 1989},
]


def format_tariffs() -> str:
    """Формирует текст со списком тарифов"""
    lines = ["💳 Тарифы:"]
    for t in VPN_TARIFFS:
        lines.append(f"• {t['title']} — {t['price']} ₽")
    return "\n".join(lines)

