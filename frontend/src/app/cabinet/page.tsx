"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/header";

type Subscription = {
  status: "active" | "expired";
  expiresAt: string;
  connectUrl: string;
};

export default function CabinetPage() {
  const [data, setData] = useState<Subscription | null>(null);

  useEffect(() => {
    const loadSubscription = async () => {
      const response = await fetch("/api/subscription", { cache: "no-store" });
      const payload = (await response.json()) as Subscription;
      setData(payload);
    };

    loadSubscription();
  }, []);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
        <h1 className="text-3xl font-black">Личный кабинет</h1>

        <section className="card space-y-5 p-6 sm:p-8">
          {!data ? (
            <p className="text-textSoft">Загружаем данные подписки…</p>
          ) : (
            <>
              <div className="space-y-3">
                <p className="text-sm text-textSoft">Статус подписки</p>
                <p
                  className={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${
                    data.status === "active" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"
                  }`}
                >
                  {data.status}
                </p>
                <p className="text-base text-textSoft">Дата окончания: {new Date(data.expiresAt).toLocaleDateString("ru-RU")}</p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Link href={data.connectUrl} className="btn-primary text-center">
                  Подключиться
                </Link>
                <button className="btn-secondary">Продлить</button>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
