import cors from "cors";
import express from "express";
import { v4 as uuidv4 } from "uuid";
import { createDb } from "./db.js";

const app = express();
const PORT = Number(process.env.PORT) || 3001;
const USER_ID = 1;

app.use(cors({ origin: "http://localhost:3000" }));
app.use(express.json());

const addMonths = (date, months) => {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
};

const getStatus = (expiryDateIso) => (new Date(expiryDateIso).getTime() > Date.now() ? "ACTIVE" : "EXPIRED");

const getMonths = (value) => {
  const months = Number(value);
  return Number.isInteger(months) && months > 0 ? months : 1;
};

const buildSubscriptionUrl = () => `vless://${uuidv4()}@server:443?type=tcp&security=reality#sector14`;

const db = await createDb();

app.post("/api/buy", async (req, res) => {
  const months = getMonths(req.body?.months);
  const expiryDate = addMonths(new Date(), months).toISOString();
  const subscriptionUrl = buildSubscriptionUrl();

  await db.run(
    `
      INSERT INTO subscriptions (user_id, expiry_date, subscription_url, updated_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(user_id)
      DO UPDATE SET
        expiry_date=excluded.expiry_date,
        subscription_url=excluded.subscription_url,
        updated_at=excluded.updated_at
    `,
    [USER_ID, expiryDate, subscriptionUrl, new Date().toISOString()]
  );

  return res.status(201).json({
    status: getStatus(expiryDate),
    expiry_date: expiryDate,
    subscription_url: subscriptionUrl
  });
});

app.get("/api/subscription", async (_req, res) => {
  const subscription = await db.get(
    `SELECT expiry_date, subscription_url FROM subscriptions WHERE user_id = ?`,
    [USER_ID]
  );

  if (!subscription) {
    return res.json({
      status: "EXPIRED",
      expiry_date: null,
      subscription_url: null
    });
  }

  return res.json({
    status: getStatus(subscription.expiry_date),
    expiry_date: subscription.expiry_date,
    subscription_url: subscription.subscription_url
  });
});

app.post("/api/extend", async (req, res) => {
  const months = getMonths(req.body?.months);
  const current = await db.get(`SELECT expiry_date, subscription_url FROM subscriptions WHERE user_id = ?`, [USER_ID]);

  const base = current?.expiry_date && new Date(current.expiry_date).getTime() > Date.now() ? new Date(current.expiry_date) : new Date();

  const nextExpiryDate = addMonths(base, months).toISOString();
  const subscriptionUrl = current?.subscription_url || buildSubscriptionUrl();

  await db.run(
    `
      INSERT INTO subscriptions (user_id, expiry_date, subscription_url, updated_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(user_id)
      DO UPDATE SET
        expiry_date=excluded.expiry_date,
        subscription_url=excluded.subscription_url,
        updated_at=excluded.updated_at
    `,
    [USER_ID, nextExpiryDate, subscriptionUrl, new Date().toISOString()]
  );

  return res.json({
    status: getStatus(nextExpiryDate),
    expiry_date: nextExpiryDate,
    subscription_url: subscriptionUrl
  });
});

app.listen(PORT, () => {
  console.log(`Sector14 backend is running at http://localhost:${PORT}`);
});
