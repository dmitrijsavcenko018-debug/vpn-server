import Link from "next/link";
import { Header } from "@/components/header";
import { PricingCard } from "@/components/pricing-card";

const plans = [
  { period: "1 месяц", price: "249 ₽" },
  { period: "3 месяца", price: "599 ₽", popular: true },
  { period: "6 месяцев", price: "1049 ₽" },
  { period: "12 месяцев", price: "1989 ₽" }
];

const connectSteps = ["Купить тариф", "Получить ссылку", "Открыть в приложении"];

export default function Home() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-4 py-10 sm:px-6 sm:py-14">
        <section className="space-y-6 text-center sm:space-y-8">
          <p className="inline-flex rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-accent">
            Secure by Sector14
          </p>
          <h1 className="text-4xl font-black leading-tight sm:text-5xl">Быстрый VPN без сложностей</h1>
          <p className="mx-auto max-w-xl text-lg text-textSoft sm:text-xl">Подключение за 1 минуту</p>
          <div className="mx-auto grid max-w-sm gap-3 sm:grid-cols-2 sm:max-w-2xl">
            <button className="btn-primary">Скачать для iPhone</button>
            <button className="btn-secondary">Скачать для Android</button>
          </div>
        </section>

        <section className="space-y-5">
          <div className="flex items-end justify-between">
            <h2 className="text-2xl font-bold sm:text-3xl">Тарифы</h2>
            <p className="text-sm text-textSoft">Выберите формат подписки</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <PricingCard key={plan.period} period={plan.period} price={plan.price} popular={plan.popular} />
            ))}
          </div>
        </section>

        <section className="card space-y-6 p-6 sm:p-8">
          <h2 className="text-2xl font-bold sm:text-3xl">Как подключиться</h2>
          <ol className="grid gap-4 sm:grid-cols-3">
            {connectSteps.map((step, index) => (
              <li key={step} className="rounded-xl border border-white/10 bg-black/20 p-4">
                <p className="text-sm text-accent">Шаг {index + 1}</p>
                <p className="mt-2 text-lg font-semibold">{step}</p>
              </li>
            ))}
          </ol>
          <div className="grid gap-3 sm:grid-cols-2">
            <button className="btn-primary">Скачать для iPhone</button>
            <button className="btn-secondary">Скачать для Android</button>
          </div>
        </section>

        <section className="card flex flex-col gap-4 p-6 text-center sm:flex-row sm:items-center sm:justify-between sm:p-7 sm:text-left">
          <div>
            <h2 className="text-xl font-bold sm:text-2xl">Уже есть подписка?</h2>
            <p className="mt-2 text-textSoft">Проверьте статус и получите ссылку в личном кабинете.</p>
          </div>
          <Link href="/cabinet" className="btn-primary sm:w-auto sm:px-8">
            Перейти в кабинет
          </Link>
        </section>
      </main>
    </div>
  );
}
