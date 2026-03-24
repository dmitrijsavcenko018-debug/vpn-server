import path from "node:path";
import { open } from "sqlite";
import sqlite3 from "sqlite3";

const dbPath = path.resolve(process.cwd(), "data.sqlite");

export async function initDb() {
  const db = await open({
    filename: dbPath,
    driver: sqlite3.Database
  });

  await db.exec(`
    CREATE TABLE IF NOT EXISTS subscriptions (
      user_id TEXT PRIMARY KEY,
      status TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
  `);

  return db;
}
