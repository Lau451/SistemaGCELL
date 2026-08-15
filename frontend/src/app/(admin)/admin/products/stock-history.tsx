"use client";

/**
 * `StockHistory` — client component rendered on the product detail page
 * (`[id]/page.tsx`) below `StockManager`, the read-only view of a single
 * variant's recorded stock movements, newest-first (spec:
 * admin-stock-management "Admin Views Per-Variant Movement History").
 *
 * Unlike `stock-manager.tsx` (which intentionally has NO local `useState`
 * for its list), `entries`/`cursor` here ARE local state (design.md
 * Decision 6, deliberate deviation): an append-in-place "Load more" list
 * cannot be expressed by a server prop, which only ever describes page
 * one. Reset on a NEW `initialHistory` prop reference (e.g. after
 * `router.refresh()` re-runs the server fetch, or a variant switch) uses
 * React's compare-prop-during-render pattern — no `useEffect` — comparing
 * against the previous prop reference during render itself.
 *
 * No computed running-balance column and no movement-type/date filter
 * controls are rendered (spec MUST NOT clauses) — this view only ever
 * lists the persisted rows as returned by the backend.
 *
 * @see design.md "Data Flow", "Decision 5", "Decision 6"
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";

export interface AdminStockMovement {
  id: number;
  variant_id: string;
  movement_type: string;
  quantity_delta: number;
  reason: string | null;
  created_at: string;
}

export interface AdminStockMovementPage {
  items: AdminStockMovement[];
  next_before_id: number | null;
}

export interface StockHistoryProps {
  productId: string;
  variantId: string;
  initialHistory: AdminStockMovementPage;
}

export function StockHistory({
  productId,
  variantId,
  initialHistory,
}: StockHistoryProps) {
  const [entries, setEntries] = useState(initialHistory.items);
  const [cursor, setCursor] = useState(initialHistory.next_before_id);
  const [loading, setLoading] = useState(false);
  // Compare-during-render reset (no effect): when `initialHistory` gets a
  // NEW object reference — page refresh after recording a movement, or a
  // variant switch — snap local state back to page one.
  const [trackedInitialHistory, setTrackedInitialHistory] =
    useState(initialHistory);
  if (trackedInitialHistory !== initialHistory) {
    setTrackedInitialHistory(initialHistory);
    setEntries(initialHistory.items);
    setCursor(initialHistory.next_before_id);
  }

  async function handleLoadMore() {
    if (cursor === null || loading) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(
        `/api/admin/products/${productId}/variants/${variantId}/stock/movements?before_id=${cursor}`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        return;
      }
      const page: AdminStockMovementPage = await response.json();
      setEntries((previous) => [...previous, ...page.items]);
      setCursor(page.next_before_id);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-xl font-semibold">Movement history</h2>

      {entries.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No movements recorded yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="border-border flex items-center justify-between border-b pb-2 text-sm"
            >
              <span className="font-medium">{entry.movement_type}</span>
              <span>{entry.quantity_delta}</span>
              <span className="text-muted-foreground">
                {entry.reason ?? ""}
              </span>
              <span className="text-muted-foreground">
                {entry.created_at}
              </span>
            </li>
          ))}
        </ul>
      )}

      {cursor !== null && (
        <Button
          type="button"
          variant="outline"
          onClick={handleLoadMore}
          disabled={loading}
          className="w-fit"
        >
          Load more
        </Button>
      )}
    </div>
  );
}
