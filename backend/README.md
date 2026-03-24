# Sector14 Backend (Node.js + Express + SQLite)

Минимальный backend для локального запуска отдельно от frontend.

## Запуск

```bash
cd backend
npm install
npm run dev
```

Сервер по умолчанию стартует на `http://localhost:4000`.

## API

### POST /api/buy
Покупка подписки.

Пример body:

```json
{
  "userId": "demo-user",
  "months": 3
}
```

### GET /api/subscription
Проверка подписки.

Query params (опционально):
- `userId` (по умолчанию `demo-user`)

### POST /api/extend
Продление подписки.

Пример body:

```json
{
  "userId": "demo-user",
  "months": 1
}
```
