# Sector14 Frontend (Next.js + Tailwind)

Готовый production-style лендинг и кабинет для VPN сервиса **Sector14**.

## Что внутри

- Next.js (App Router)
- Tailwind CSS
- Тёмный минималистичный UI
- Тарифы и шаги подключения
- Страница личного кабинета `/cabinet`
- Mock API endpoint `/api/subscription`

## Локальный запуск

```bash
npm install
npm run dev
```

Откройте: `http://localhost:3000`

## Структура

```text
frontend/
  src/
    app/
      api/subscription/route.ts
      cabinet/page.tsx
      globals.css
      layout.tsx
      page.tsx
    components/
      header.tsx
      pricing-card.tsx
  package.json
  tailwind.config.ts
  postcss.config.js
  tsconfig.json
  next.config.ts
```
