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
 * No computed running-balance column and no movement-type filter control
 * are rendered (spec MUST NOT clauses, unchanged by D4/D5). A date-range
 * filter (`since`/`until`) IS now rendered (D3 reverses only the
 * date-range half of the old MUST NOT clause) — this view still only
 * ever lists the persisted rows as returned by the backend.
 *
 * The filter is URL-driven (design.md DD2): a preset click or a date
 * input change pushes `?since=&until=` via `useRouter`, a REAL
 * navigation. `[id]/page.tsx` re-fetches under the new filter and hands
 * down a fresh `initialHistory` object reference — which is exactly what
 * the existing Decision 6 reset above already handles. No new
 * reset-on-filter-change code is written here.
 *
 * @see design.md "Data Flow", "Decision 5", "Decision 6", "DD2", "D13"
 */
import { useState, useTransition, type ChangeEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  dayFromParam,
  presetRange,
  toSinceParam,
  toUntilParam,
} from "./stock-history-dates";

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
  /** Full offset-aware ISO-8601 wire value, as produced by `toSinceParam`. */
  since?: string;
  /** Full offset-aware ISO-8601 wire value, as produced by `toUntilParam`. */
  until?: string;
}

const UNFILTERED_EMPTY_COPY = "No movements recorded yet.";
const FILTERED_EMPTY_COPY = "No movements in the selected date range.";

export function StockHistory({
  productId,
  variantId,
  initialHistory,
  since,
  until,
}: StockHistoryProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  const [entries, setEntries] = useState(initialHistory.items);
  const [cursor, setCursor] = useState(initialHistory.next_before_id);
  const [loading, setLoading] = useState(false);
  // Compare-during-render reset (no effect): when `initialHistory` gets a
  // NEW object reference — page refresh after recording a movement, a
  // variant switch, OR a filter change producing a fresh server fetch —
  // snap local state back to page one. Unchanged from before this filter
  // existed (design.md Decision 6).
  const [trackedInitialHistory, setTrackedInitialHistory] =
    useState(initialHistory);
  if (trackedInitialHistory !== initialHistory) {
    setTrackedInitialHistory(initialHistory);
    setEntries(initialHistory.items);
    setCursor(initialHistory.next_before_id);
  }

  const filterActive = Boolean(since || until);

  function pushRange(nextSince: string | undefined, nextUntil: string | undefined) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextSince) {
      params.set("since", nextSince);
    } else {
      params.delete("since");
    }
    if (nextUntil) {
      params.set("until", nextUntil);
    } else {
      params.delete("until");
    }
    const query = params.toString();
    startTransition(() => {
      router.push(query ? `${pathname}?${query}` : pathname);
    });
  }

  function handleSinceChange(event: ChangeEvent<HTMLInputElement>) {
    const day = event.target.value;
    pushRange(day ? toSinceParam(day) : undefined, until);
  }

  function handleUntilChange(event: ChangeEvent<HTMLInputElement>) {
    const day = event.target.value;
    pushRange(since, day ? toUntilParam(day) : undefined);
  }

  function handlePreset(preset: "today" | "last7" | "last30") {
    const range = presetRange(preset);
    pushRange(range.since, range.until);
  }

  function handleClear() {
    pushRange(undefined, undefined);
  }

  async function handleLoadMore() {
    if (cursor === null || loading) {
      return;
    }
    setLoading(true);
    try {
      // Re-send the active since/until on every subsequent page (D12 /
      // design.md DD2) — built through `URLSearchParams`, never string
      // concatenation, so the offset's `+`/`:` survive percent-encoded
      // (design.md's encoding gotcha).
      const params = new URLSearchParams();
      params.set("before_id", String(cursor));
      if (since) {
        params.set("since", since);
      }
      if (until) {
        params.set("until", until);
      }
      const response = await fetch(
        `/api/admin/products/${productId}/variants/${variantId}/stock/movements?${params.toString()}`,
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

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="stock-history-since"
            className="text-sm font-medium"
          >
            Since
          </label>
          <input
            id="stock-history-since"
            type="date"
            value={since ? dayFromParam(since) : ""}
            onChange={handleSinceChange}
            className="border-border rounded-md border px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="stock-history-until"
            className="text-sm font-medium"
          >
            Until
          </label>
          <input
            id="stock-history-until"
            type="date"
            value={until ? dayFromParam(until) : ""}
            onChange={handleUntilChange}
            className="border-border rounded-md border px-3 py-2 text-sm"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handlePreset("today")}
        >
          Today
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handlePreset("last7")}
        >
          Last 7 days
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => handlePreset("last30")}
        >
          Last 30 days
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={handleClear}>
          Clear
        </Button>
      </div>

      {entries.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          {filterActive ? FILTERED_EMPTY_COPY : UNFILTERED_EMPTY_COPY}
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
