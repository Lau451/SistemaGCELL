"use client";

/**
 * `StockManager` — client component rendered on the product detail page
 * (`[id]/page.tsx`), the ONLY UI surface for `recordStockMovementAction`
 * (design.md's "Frontend relay" — Server Actions are the sole write
 * path). Mirrors `image-manager.tsx`'s file shape: `initialStock` IS the
 * rendered list (no local `useState` copy), and after a successful
 * submission this calls `router.refresh()` so `[id]/page.tsx`'s server
 * fetch re-runs and delivers the authoritative quantities back down
 * through this same prop.
 *
 * One record-movement form (design.md Decision 6): a variant `<select>`,
 * a `movement_type` `<select>`, a positive-magnitude quantity input, a
 * `direction` control shown ONLY for `adjustment` (Decision 7 —
 * `signedQuantityDelta` in `actions.ts` ignores `direction` for every
 * other type), and an optional `reason` text input.
 *
 * Zero-stock variants are distinguished by an "Out of stock" label
 * (design.md Decision 8) — the semantic proxy asserted in tests, rather
 * than a CSS class name.
 *
 * @see design.md "Data Flow", "Decision 6", "Decision 7", "Decision 8"
 */
import { useActionState, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { recordStockMovementAction, type ProductFormState } from "./actions";

export interface AdminVariantStock {
  variant_id: string;
  color: string;
  quantity_on_hand: number;
}

export interface StockManagerProps {
  productId: string;
  initialStock: AdminVariantStock[];
}

const INITIAL_STATE: ProductFormState = { error: null };
const DEFAULT_MOVEMENT_TYPE = "restock";

const MOVEMENT_TYPES = [
  { value: "restock", label: "Restock" },
  { value: "sale", label: "Sale" },
  { value: "return", label: "Return" },
  { value: "breakage", label: "Breakage" },
  { value: "adjustment", label: "Adjustment" },
] as const;

export function StockManager({ productId, initialStock }: StockManagerProps) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  // `stock` intentionally has NO local `useState`: `initialStock` is the
  // single source of truth, refreshed via `router.refresh()` below — same
  // strategy as `image-manager.tsx`'s `images`.
  const stock = initialStock;
  const [movementType, setMovementType] = useState<string>(
    DEFAULT_MOVEMENT_TYPE,
  );
  const boundAction = useMemo(
    () => recordStockMovementAction.bind(null, productId),
    [productId],
  );
  const [state, formAction, pending] = useActionState(
    boundAction,
    INITIAL_STATE,
  );

  useEffect(() => {
    // Same "never submitted yet" vs. "just submitted and succeeded"
    // distinction as `image-manager.tsx`'s upload effect. `movementType`
    // is intentionally left as-is on success (not reset to the default)
    // — resetting controlled state synchronously inside an effect is a
    // React anti-pattern (cascading renders); `formRef.current?.reset()`
    // already clears every uncontrolled field (variant, quantity,
    // reason).
    if (state !== INITIAL_STATE && state.error === null) {
      formRef.current?.reset();
      router.refresh();
    }
  }, [state, router]);

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold">Stock</h2>

      <div className="flex flex-col gap-3">
        {stock.length === 0 && (
          <p className="text-muted-foreground text-sm">No variants yet.</p>
        )}
        {stock.map((variant) => {
          const isZero = variant.quantity_on_hand === 0;
          return (
            <div
              key={variant.variant_id}
              className={
                isZero
                  ? "border-border text-destructive flex items-center justify-between border-b pb-2"
                  : "border-border flex items-center justify-between border-b pb-2"
              }
            >
              <span className="font-medium">{variant.color}</span>
              <span className="flex items-center gap-2 text-sm">
                <span>{variant.quantity_on_hand}</span>
                {isZero && (
                  <span className="text-xs font-medium">Out of stock</span>
                )}
              </span>
            </div>
          );
        })}
      </div>

      <form
        ref={formRef}
        action={formAction}
        className="border-border flex flex-col gap-3 border-b pb-4"
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="stock-variant" className="text-sm font-medium">
            Variant
          </label>
          <select
            id="stock-variant"
            name="variant-id"
            defaultValue={stock[0]?.variant_id ?? ""}
            className="border-border rounded-md border px-3 py-2 text-sm"
          >
            {stock.map((variant) => (
              <option key={variant.variant_id} value={variant.variant_id}>
                {variant.color}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="stock-movement-type"
            className="text-sm font-medium"
          >
            Movement type
          </label>
          <select
            id="stock-movement-type"
            name="movement-type"
            value={movementType}
            onChange={(event) => setMovementType(event.target.value)}
            className="border-border rounded-md border px-3 py-2 text-sm"
          >
            {MOVEMENT_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="stock-magnitude" className="text-sm font-medium">
            Quantity
          </label>
          <input
            id="stock-magnitude"
            name="magnitude"
            type="number"
            min="1"
            step="1"
            className="border-border rounded-md border px-3 py-2 text-sm"
          />
        </div>

        {movementType === "adjustment" && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="stock-direction" className="text-sm font-medium">
              Direction
            </label>
            <select
              id="stock-direction"
              name="direction"
              defaultValue="increase"
              className="border-border rounded-md border px-3 py-2 text-sm"
            >
              <option value="increase">Increase</option>
              <option value="decrease">Decrease</option>
            </select>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="stock-reason" className="text-sm font-medium">
            Reason (optional)
          </label>
          <input
            id="stock-reason"
            name="reason"
            type="text"
            className="border-border rounded-md border px-3 py-2 text-sm"
          />
        </div>

        {state.error && (
          <p role="alert" className="text-destructive text-sm">
            {state.error}
          </p>
        )}

        <Button type="submit" disabled={pending}>
          Record movement
        </Button>
      </form>
    </div>
  );
}
