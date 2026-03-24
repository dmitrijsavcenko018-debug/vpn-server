"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Header } from "@/components/header";

type SubscriptionData = {
  status: "ACTIVE" | "EXPIRED";
  expiry_date: string | null;
  subscription_url: string | null;
};

export default function CabinetPage() {
  const [data, setData] = useState<SubscriptionData | null>(null);
  const [qrCode, setQrCode] = useState<string>("");
  const [copyText, setCopyText] = useState<string>("Скопировать");

  useEffect(() => {
    const load = async () => {
      const response = await fetch("http://localhost:3001/api/subscription", { cache: "no-store" });
      const payload = (await response.json()) as SubscriptionData;
      setData(payload);

      if (payload.subscription_url) {
        const qr = await QRCode.toDataURL(payload.subscription_url, { margin: 1, width: 240 });
        setQrCode(qr);
      }
    };

    load();
  }, []);

  const handleCopy = async () => {
    if (!data?.subscription_url) return;
    await navigator.clipboard.writeText(data.subscription_url);
    setCopyText("Скопировано");
    setTimeout(() => setCopyText("Скопировать"), 1500);
  };

  const formattedDate = data?.expiry_date ? new Date(data.expiry_date).toLocaleString("ru-RU") : "—";

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
        <h1 className="text-3xl font-black">Личный кабинет</h1>

        <section className="card space-y-5 p-6 sm:p-8">
          {!data ? (
            <p className="text-muted">Загрузка данных...</p>
          ) : (
            <>
              <div className="space-y-2">
                <p className="text-sm text-muted">Статус подписки</p>
                <p
                  className={`inline-flex rounded-full px-3 py-1 text-sm font-bold ${
                    data.status === "ACTIVE" ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
                  }`}
                >
                  {data.status}
                </p>
                <p className="text-muted">Дата окончания: {formattedDate}</p>
              </div>

              <div className="space-y-3">
                <p className="text-sm text-muted">Subscription URL</p>
                <p className="break-all rounded-xl border border-white/10 bg-black/25 p-3 text-sm">
                  {data.subscription_url ?? "Нет активной ссылки"}
                </p>
                <button type="button" className="btn-primary" onClick={handleCopy}>
                  {copyText}
                </button>
              </div>

              {qrCode && (
                <div className="space-y-2">
                  <p className="text-sm text-muted">QR-код</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={qrCode} alt="Subscription QR" className="h-56 w-56 rounded-xl border border-white/10 bg-white p-2" />
                </div>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
