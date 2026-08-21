import Link from "next/link";
import { LogOut, Package, Boxes } from "lucide-react";
import { Suspense, type ReactNode } from "react";
import { signOutAction } from "../actions";
import { StockAlertBadge } from "./stock-alert-badge";
import { AdminNavLink } from "./admin-nav-link";

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
 *
 * Phase 3: restyled into the confirmed Pencil mockup's dark-plum sidebar
 * shell (`bg-sidebar`/`text-sidebar-foreground`, phase 1 tokens). Only the
 * `AdminNavLink` active/inactive state is a client component — everything
 * else here, including the `StockAlertBadge` Suspense boundary, is
 * unchanged server-rendered composition.
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="bg-sidebar text-sidebar-foreground flex shrink-0 flex-col gap-6 px-4 py-6 md:w-60 md:px-3">
        <Link
          href="/admin"
          className="font-heading px-2 text-xl font-bold tracking-tight text-white"
        >
          GCELL
        </Link>
        <nav className="flex flex-1 flex-col gap-1">
          <AdminNavLink href="/admin/products" icon={<Package />}>
            Productos
          </AdminNavLink>
          <AdminNavLink href="/admin/stock" icon={<Boxes />}>
            Stock{" "}
            <Suspense fallback={null}>
              <StockAlertBadge />
            </Suspense>
          </AdminNavLink>
        </nav>
        <form action={signOutAction}>
          <button
            type="submit"
            className="text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            Cerrar sesión
          </button>
        </form>
      </aside>
      <main className="bg-background flex-1">{children}</main>
    </div>
  );
}
