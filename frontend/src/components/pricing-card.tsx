type PricingCardProps = {
  period: string;
  price: string;
  popular?: boolean;
};

export function PricingCard({ period, price, popular = false }: PricingCardProps) {
  return (
    <article
      className={`card relative flex h-full flex-col gap-5 p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-glow ${
        popular ? "border-accent/60 shadow-glow" : ""
      }`}
    >
      {popular && (
        <span className="absolute -top-3 left-4 rounded-full bg-accent px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white">
          Популярный тариф
        </span>
      )}
      <div>
        <p className="text-sm text-textSoft">Тариф</p>
        <h3 className="mt-1 text-2xl font-bold">{period}</h3>
      </div>
      <p className="text-3xl font-extrabold tracking-tight">{price}</p>
      <button type="button" className="btn-primary mt-auto">
        Купить
      </button>
    </article>
  );
}
