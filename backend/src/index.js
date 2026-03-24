import express from "express";
import { initDb } from "./db.js";

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.json());

const addMonths = (sourceDate, months) => {
  const next = new Date(sourceDate);
  next.setMonth(next.getMonth() + months);
  return next;
};

const toIso = (date) => new Date(date).toISOString();

const normalizeMonths = (value) => {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return 1;
  return parsed;
};

const normalizeUserId = (value) => {
  if (typeof value !== "string" || !value.trim()) return "demo-user";
  return value.trim();
};

const db = await initDb();

app.post("/api/buy", async (req, res) => {
  const userId = normalizeUserId(req.body?.userId);
  const months = normalizeMonths(req.body?.months);
  const now = new Date();
  const expiresAt = addMonths(now, months);

  await db.run(
    `
      INSERT INTO subscriptions(user_id, status, expires_at, updated_at)
      VALUES (?, 'active', ?, ?)
      ON CONFLICT(user_id)
      DO UPDATE SET
        status = 'active',
        expires_at = excluded.expires_at,
        updated_at = excluded.updated_at
    `,
    [userId, toIso(expiresAt), toIso(now)]
  );

  return res.status(201).json({
    message: "Тариф успешно куплен",
    userId,
    status: "active",
    expiresAt: toIso(expiresAt)
  });
});

app.get("/api/subscription", async (req, res) => {
  const userId = normalizeUserId(req.query.userId);

  const subscription = await db.get(
    `SELECT user_id as userId, status, expires_at as expiresAt FROM subscriptions WHERE user_id = ?`,
    [userId]
  );

  if (!subscription) {
    return res.json({
      userId,
      status: "expired",
      expiresAt: null
    });
  }

  const isExpired = new Date(subscription.expiresAt).getTime() <= Date.now();

  return res.json({
    ...subscription,
    status: isExpired ? "expired" : "active"
  });
});

app.post("/api/extend", async (req, res) => {
  const userId = normalizeUserId(req.body?.userId);
  const months = normalizeMonths(req.body?.months);
  const now = new Date();

  const current = await db.get(`SELECT expires_at as expiresAt FROM subscriptions WHERE user_id = ?`, [userId]);

  const baseDate = current?.expiresAt && new Date(current.expiresAt) > now ? new Date(current.expiresAt) : now;
  const nextExpiresAt = addMonths(baseDate, months);

  await db.run(
    `
      INSERT INTO subscriptions(user_id, status, expires_at, updated_at)
      VALUES (?, 'active', ?, ?)
      ON CONFLICT(user_id)
      DO UPDATE SET
        status = 'active',
        expires_at = excluded.expires_at,
        updated_at = excluded.updated_at
    `,
    [userId, toIso(nextExpiresAt), toIso(now)]
  );

  return res.json({
    message: "Подписка продлена",
    userId,
    status: "active",
    expiresAt: toIso(nextExpiresAt)
  });
});

app.listen(PORT, () => {
  console.log(`Sector14 backend is running on http://localhost:${PORT}`);
});
