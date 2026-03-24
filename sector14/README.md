# Sector14 — VPN SaaS (Next.js + Express + SQLite)

Единый рабочий mock-продукт: frontend и backend уже связаны.

## Структура

```text
sector14/
  frontend/
  backend/
```

## Backend

```bash
cd backend
npm install
npm run dev
```

Backend запускается на `http://localhost:3001`.

Доступные API:
- `POST /api/buy` с body `{ "months": number }`
- `GET /api/subscription`
- `POST /api/extend` с body `{ "months": number }`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend запускается на `http://localhost:3000` и обращается к backend на `http://localhost:3001`.

## Что реализовано

- Главная с тарифами и кнопками "Купить" (реальный вызов `POST /api/buy`).
- Кабинет `/cabinet` получает данные из `GET /api/subscription`.
- Показываются: статус (ACTIVE/EXPIRED), дата окончания, subscription URL, кнопка копирования и QR-код.
- Генерация subscription URL:
  - `vless://UUID@server:443?type=tcp&security=reality#sector14`
- CORS включён для `http://localhost:3000`.
