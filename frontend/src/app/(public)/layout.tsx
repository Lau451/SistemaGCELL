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
      <header className="border-border border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link href="/" className="text-lg font-semibold">
            GCELL
          </Link>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </>
  );
}
