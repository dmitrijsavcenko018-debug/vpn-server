type PricingCardProps = {
  months: number;
  title: string;
  price: string;
  popular?: boolean;
  onBuy: (months: number) => void;
  loading: boolean;
};

export function PricingCard({ months, title, price, popular = false, onBuy, loading }: PricingCardProps) {
  return (
    <article
      className={`card relative flex flex-col gap-5 p-5 transition-all duration-300 hover:-translate-y-1 ${popular ? "border-accent/60" : ""}`}
    >
      {popular && (
        <span className="absolute -top-3 left-4 rounded-full bg-accent px-3 py-1 text-xs font-semibold uppercase">Популярный</span>
      )}
      <div>
        <p className="text-sm text-muted">Тариф</p>
        <h3 className="text-2xl font-bold">{title}</h3>
      </div>
      <p className="text-3xl font-extrabold">{price}</p>
      <button type="button" className="btn-primary mt-auto" onClick={() => onBuy(months)} disabled={loading}>
        {loading ? "Обработка..." : "Купить"}
      </button>
    </article>
  );
}
