# VPN Subscription MVP

Минимальный VPN-сервис с подпиской и Telegram-ботом.

## Стек

- FastAPI + SQLAlchemy 2 + PostgreSQL + Alembic
- aiogram 3
- Docker / docker-compose
- CryptoPay для оплаты через TON

## Быстрый старт

1. Скопируйте настройки:

   ```bash
   cp .env.example .env
   ```

   Обновите значения в `.env`:
   
   **Обязательные переменные:**
   - `BOT_TOKEN` - токен Telegram бота от @BotFather
   - `BACKEND_URL` - URL backend сервиса (для Docker: `http://backend:8000`)
   - `CRYPTOPAY_API_TOKEN` - токен API от CryptoBot для оплаты через TON
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - настройки базы данных
   
   **Примечание:** `TON_PROVIDER_TOKEN` больше не используется, оплата TON происходит только через CryptoPay.

2. Соберите и запустите проект:

   ```bash
   docker compose up --build
   ```

3. После старта контейнеров примените миграции внутри backend-контейнера:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. Проверьте API (`http://localhost:8000/docs`) и настройте Telegram-бота, указав токен в `.env`.

## Основные маршруты

- `POST /api/users/by-telegram`
- `GET /api/subscriptions/{telegram_id}`
- `POST /api/subscriptions/{telegram_id}/create-month`
- `GET /api/vpn/config/{telegram_id}`

Бот использует эти эндпоинты для работы команд `/start`, `/status`, `/buy`, `/config`.
