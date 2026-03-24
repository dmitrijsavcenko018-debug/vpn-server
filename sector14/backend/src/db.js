import path from "node:path";
import { open } from "sqlite";
import sqlite3 from "sqlite3";

const dbFilePath = path.resolve(process.cwd(), "data.sqlite");

export async function createDb() {
  const db = await open({
    filename: dbFilePath,
    driver: sqlite3.Database
  });

  await db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
      user_id INTEGER PRIMARY KEY,
      expiry_date TEXT NOT NULL,
      subscription_url TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
  `);

  await db.run(`INSERT OR IGNORE INTO users(id, name) VALUES (1, 'Test User')`);

  return db;
}
