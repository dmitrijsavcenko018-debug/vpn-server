#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания инвойса через CryptoPay API.

Использование:
    python test_cryptopay.py

Или через Docker:
    docker compose exec bot python test_cryptopay.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к модулям бота
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptopay_client import CryptoPayClient
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_create_invoice():
    """Тестирует создание инвойса через CryptoPay API."""
    try:
        # Проверяем наличие токена
        api_token = os.getenv("CRYPTOPAY_API_TOKEN")
        if not api_token or api_token == "вставь_тут_твой_api_token_из_CryptoBot":
            print("❌ Ошибка: CRYPTOPAY_API_TOKEN не установлен в .env файле")
            print("Установите токен в формате: CRYPTOPAY_API_TOKEN=your_token_here")
            return False
        
        print(f"✅ Токен найден: {api_token[:10]}...")
        
        # Создаём клиент
        client = CryptoPayClient(api_token=api_token)
        print("✅ CryptoPayClient инициализирован")
        
        # Создаём тестовый инвойс
        print("\n📝 Создаю тестовый инвойс...")
        print("   Asset: TON")
        print("   Amount: 0.01")
        print("   Description: Тестовая оплата VPN подписки")
        
        invoice_response = await client.create_invoice(
            asset="TON",
            amount=0.01,
            description="Тестовая оплата VPN подписки",
            payload="test_invoice_12345"
        )
        
        # Проверяем ответ
        if not invoice_response.get("ok"):
            print("❌ Ошибка: CryptoPay API вернул ok=false")
            print(f"   Ответ: {invoice_response}")
            return False
        
        invoice_result = invoice_response.get("result", {})
        invoice_id = invoice_result.get("invoice_id")
        pay_url = invoice_result.get("pay_url")
        status = invoice_result.get("status")
        amount = invoice_result.get("amount")
        asset = invoice_result.get("asset")
        
        print("\n✅ Инвойс успешно создан!")
        print("=" * 60)
        print(f"Invoice ID: {invoice_id}")
        print(f"Status: {status}")
        print(f"Amount: {amount} {asset}")
        print(f"Pay URL: {pay_url}")
        print("=" * 60)
        
        if pay_url:
            print(f"\n🔗 Ссылка для оплаты: {pay_url}")
            print("\n💡 Откройте эту ссылку в браузере, чтобы увидеть страницу оплаты CryptoBot")
            print("   с корректным QR-кодом для банка.")
        else:
            print("\n⚠️  Внимание: pay_url отсутствует в ответе")
        
        return True
        
    except ValueError as e:
        print(f"❌ Ошибка валидации: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция."""
    print("🧪 Тест создания инвойса через CryptoPay API\n")
    
    success = await test_create_invoice()
    
    if success:
        print("\n✅ Тест пройден успешно!")
        sys.exit(0)
    else:
        print("\n❌ Тест не пройден")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

