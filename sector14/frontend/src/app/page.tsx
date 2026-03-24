"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { PricingCard } from "@/components/pricing-card";

const plans = [
  { months: 1, title: "1 месяц", price: "249₽" },
  { months: 3, title: "3 месяца", price: "599₽", popular: true },
  { months: 6, title: "6 месяцев", price: "1049₽" },
  { months: 12, title: "12 месяцев", price: "1989₽" }
];

const steps = ["Купить тариф", "Получить ссылку", "Открыть в приложении"];

export default function HomePage() {
  const [loadingPlan, setLoadingPlan] = useState<number | null>(null);
  const [message, setMessage] = useState<string>("");
  const router = useRouter();

  const handleBuy = async (months: number) => {
    setLoadingPlan(months);
    setMessage("");

    try {
      const response = await fetch("http://localhost:3001/api/buy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ months })
      });

      if (!response.ok) throw new Error("Ошибка покупки");

      setMessage("Тариф успешно активирован. Переходим в кабинет...");
      setTimeout(() => router.push("/cabinet"), 700);
    } catch (_error) {
      setMessage("Не удалось купить тариф. Проверьте backend на localhost:3001.");
    } finally {
      setLoadingPlan(null);
    }
  };

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-14 px-4 py-10 sm:px-6">
        <section className="space-y-6 text-center">
          <h1 className="text-4xl font-black sm:text-5xl">Быстрый VPN без сложностей</h1>
          <p className="mx-auto max-w-xl text-lg text-muted">Подключение за 1 минуту</p>
          <a href="https://t.me/sector14_support" target="_blank" rel="noreferrer" className="btn-secondary mx-auto max-w-sm">
            Открыть Telegram
          </a>
          {message && <p className="text-sm text-muted">{message}</p>}
        </section>

        <section className="space-y-5">
          <h2 className="text-2xl font-bold sm:text-3xl">Тарифы</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <PricingCard
                key={plan.months}
                months={plan.months}
                title={plan.title}
                price={plan.price}
                popular={plan.popular}
                loading={loadingPlan === plan.months}
                onBuy={handleBuy}
              />
            ))}
          </div>
        </section>

        <section className="card space-y-5 p-6 sm:p-8">
          <h2 className="text-2xl font-bold sm:text-3xl">Как подключиться</h2>
          <ol className="grid gap-4 sm:grid-cols-3">
            {steps.map((step, index) => (
              <li key={step} className="rounded-xl border border-white/10 bg-black/20 p-4">
                <p className="text-sm text-accent">Шаг {index + 1}</p>
                <p className="mt-2 text-lg font-semibold">{step}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
