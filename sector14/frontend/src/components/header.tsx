import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-white/10 bg-background/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-wide">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent">S14</span>
          Sector14
        </Link>
        <a
          href="https://t.me/sector14_support"
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium hover:bg-white/10"
        >
          Открыть Telegram
        </a>
      </div>
    </header>
  );
}
