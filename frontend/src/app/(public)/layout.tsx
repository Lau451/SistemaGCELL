import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Public storefront shell shared by `/`, `/catalog`, and `/product/[slug]`.
 * Not a root layout (the app already has one at `app/layout.tsx`) — this
 * just adds the header/nav around the route group.
 */
export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link
            href="/"
            className="font-heading text-xl font-bold text-brand-primary"
          >
            GCELL
          </Link>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="bg-brand-ink text-brand-cream">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-1 px-4 py-8 text-center">
          <p className="font-heading text-base font-semibold">GCELL</p>
          <p className="text-sm text-brand-cream/70">
            Fundas y accesorios para celular.
          </p>
          <p className="mt-3 text-xs text-brand-cream/50">
            © {new Date().getFullYear()} GCELL. Todos los derechos
            reservados.
          </p>
        </div>
      </footer>
    </>
  );
}
