import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-bg/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-wide">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent font-bold">S14</span>
          <span>Sector14</span>
        </Link>
        <Link href="/cabinet" className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium transition hover:bg-white/10">
          Личный кабинет
        </Link>
      </div>
    </header>
  );
}
