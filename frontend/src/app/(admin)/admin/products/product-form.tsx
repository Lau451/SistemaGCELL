"use client";

/**
 * `ProductForm` — client component shared by `new/page.tsx` (create) and
 * `[id]/page.tsx` (edit), wired to whichever action is passed in through
 * React 19's `useActionState` (same pattern as `login-form.tsx`, this
 * repo's one existing form precedent). Never renders a slug field — the
 * slug is always server-generated on create and frozen on edit (spec:
 * "Product Creation Form...MUST NEVER accept an admin-typed `slug`",
 * "the edit form MUST NOT expose a slug field to change").
 *
 * Variant rows live in `useState`, NOT bracket-notation form fields:
 * `actions.ts`'s `buildVariantsPayload` zips `variant-id`/`variant-color`/
 * `variant-price`/`variant-cost` positionally via `formData.getAll()`, so
 * each row renders exactly one of each field, in order. A row with no
 * `id` yet (added via "Add variant") renders a blank hidden
 * `variant-id`, which `actions.ts` reads as "new".
 *
 * Removing a row:
 * - UNSAVED (no `id`): client-only `setState`, no request — the row
 *   never existed on the server, so there is nothing to retire.
 * - SAVED (has an `id`): submits `retireVariantAction` directly (Server
 *   Actions are plain async functions and can be invoked imperatively,
 *   not only via `<form action>`), then removes the row locally once the
 *   retire resolves.
 *
 * Price/cost inputs are `type="number" step="0.01" min="0"` — see
 * `actions.ts`'s file-level comment for why their submitted VALUE is
 * never parsed to a JS number on this form's own side either.
 */
import { useActionState, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { retireVariantAction, type ProductFormState } from "./actions";

export interface ProductFormVariant {
  id: string;
  color: string;
  price: string;
  cost: string;
}

export interface ProductFormProps {
  action: (
    prevState: ProductFormState,
    formData: FormData,
  ) => Promise<ProductFormState>;
  submitLabel: string;
  productId?: string;
  initialName?: string;
  initialModel?: string;
  initialVariants?: ProductFormVariant[];
}

interface VariantRow {
  key: string;
  id: string | null;
  color: string;
  price: string;
  cost: string;
}

const INITIAL_STATE: ProductFormState = { error: null };

let rowKeySequence = 0;
function nextRowKey(): string {
  rowKeySequence += 1;
  return `variant-row-${rowKeySequence}`;
}

function toInitialRows(variants: ProductFormVariant[] | undefined): VariantRow[] {
  if (!variants || variants.length === 0) {
    return [];
  }
  return variants.map((variant) => ({
    key: nextRowKey(),
    id: variant.id,
    color: variant.color,
    price: variant.price,
    cost: variant.cost,
  }));
}

export function ProductForm({
  action,
  submitLabel,
  productId,
  initialName = "",
  initialModel = "",
  initialVariants,
}: ProductFormProps) {
  const [state, formAction, pending] = useActionState(action, INITIAL_STATE);
  const [rows, setRows] = useState<VariantRow[]>(() =>
    toInitialRows(initialVariants),
  );
  const [isRemoving, startRemoving] = useTransition();

  function addRow() {
    setRows((previous) => [
      ...previous,
      { key: nextRowKey(), id: null, color: "", price: "", cost: "" },
    ]);
  }

  function updateRow(
    key: string,
    field: "color" | "price" | "cost",
    value: string,
  ) {
    setRows((previous) =>
      previous.map((row) => (row.key === key ? { ...row, [field]: value } : row)),
    );
  }

  function removeRow(row: VariantRow) {
    if (row.id === null) {
      // Unsaved row: client-only removal, no request — it never existed
      // on the server.
      setRows((previous) => previous.filter((entry) => entry.key !== row.key));
      return;
    }

    if (!productId) {
      return;
    }

    const rowId = row.id;
    const formData = new FormData();
    formData.set("product-id", productId);
    formData.set("variant-id", rowId);

    startRemoving(async () => {
      await retireVariantAction(formData);
      setRows((previous) => previous.filter((entry) => entry.key !== row.key));
    });
  }

  return (
    <form action={formAction} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="product-name" className="text-sm font-medium">
          Name
        </label>
        <input
          id="product-name"
          name="name"
          type="text"
          required
          defaultValue={initialName}
          className="border-border rounded-md border px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="product-model" className="text-sm font-medium">
          Model
        </label>
        <input
          id="product-model"
          name="model"
          type="text"
          required
          defaultValue={initialModel}
          className="border-border rounded-md border px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Variants</h2>
        {rows.map((row) => (
          <div
            key={row.key}
            className="border-border flex flex-wrap items-end gap-2 border-b pb-3"
          >
            <input type="hidden" name="variant-id" value={row.id ?? ""} />
            <div className="flex flex-col gap-1">
              <label
                htmlFor={`${row.key}-color`}
                className="text-xs font-medium"
              >
                Color
              </label>
              <input
                id={`${row.key}-color`}
                name="variant-color"
                type="text"
                required
                value={row.color}
                onChange={(event) =>
                  updateRow(row.key, "color", event.target.value)
                }
                className="border-border rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label
                htmlFor={`${row.key}-price`}
                className="text-xs font-medium"
              >
                Price
              </label>
              <input
                id={`${row.key}-price`}
                name="variant-price"
                type="number"
                step="0.01"
                min="0"
                required
                value={row.price}
                onChange={(event) =>
                  updateRow(row.key, "price", event.target.value)
                }
                className="border-border rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label
                htmlFor={`${row.key}-cost`}
                className="text-xs font-medium"
              >
                Cost
              </label>
              <input
                id={`${row.key}-cost`}
                name="variant-cost"
                type="number"
                step="0.01"
                min="0"
                required
                value={row.cost}
                onChange={(event) =>
                  updateRow(row.key, "cost", event.target.value)
                }
                className="border-border rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={isRemoving}
              onClick={() => removeRow(row)}
            >
              Remove
            </Button>
          </div>
        ))}
        <Button type="button" variant="secondary" onClick={addRow}>
          Add variant
        </Button>
      </div>

      {state.error && (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      )}

      <Button type="submit" disabled={pending}>
        {submitLabel}
      </Button>
    </form>
  );
}
