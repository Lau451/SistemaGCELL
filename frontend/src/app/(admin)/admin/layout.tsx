import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { signOutAction } from "./actions";
import { StockAlertBadge } from "./stock-alert-badge";

/**
 * Admin shell wrapping every `/admin/*` page — mirrors the shape of
 * `(public)/layout.tsx`. The sign-out control is a plain form whose
 * `action` is the `signOutAction` Server Action reference directly
 * (no client-side state needed here, unlike the login form's
 * `useActionState`), per `admin-authentication` spec's "Logout Clears
 * The Session" requirement.
 *
 * `StockAlertBadge` is an async Server Component mounted through
 * `<Suspense fallback={null}>` (design.md Decision 1) so the shell — this
 * nav included — renders immediately and stays clickable while the
 * low-stock count streams in; a failure there is contained to that one
 * subtree. `AdminLayout` itself stays a **synchronous** Server Component.
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="border-border border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Link href="/admin" className="text-lg font-semibold">
            GCELL Admin
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/admin/products" className="text-sm">
              Products
            </Link>
            <Link href="/admin/stock" className="text-sm">
              Stock{" "}
              <Suspense fallback={null}>
                <StockAlertBadge />
              </Suspense>
            </Link>
            <form action={signOutAction}>
              <button type="submit" className="text-sm">
                Sign out
              </button>
            </form>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </>
  );
}
