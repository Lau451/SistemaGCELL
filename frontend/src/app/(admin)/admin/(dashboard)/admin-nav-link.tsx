"use client";

/**
 * `AdminNavLink` — presentational-only client component for the sidebar
 * nav in `layout.tsx`. Split out purely so the active/inactive pink-tinted
 * styling (Phase 3 mockup) can read the current route via `usePathname()`
 * — `AdminLayout` itself stays a synchronous Server Component (unchanged
 * from Phase 2), and `StockAlertBadge` (an async Server Component) is
 * still passed straight through as `children`, composed from the server
 * side exactly as before.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface AdminNavLinkProps {
  href: string;
  icon: ReactNode;
  children: ReactNode;
}

export function AdminNavLink({ href, icon, children }: AdminNavLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href || pathname?.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "bg-brand-primary/25 text-white"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
      )}
    >
      <span className="[&_svg]:size-4 [&_svg]:shrink-0">{icon}</span>
      {children}
    </Link>
  );
}
