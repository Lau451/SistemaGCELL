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
 *
 * "Initial quantity" (design.md Decision 4) is rendered ONLY when
 * `row.id === null && productId === undefined` — i.e. every row on the
 * CREATE page, and never on the edit page (even for a newly added row
 * there, since PATCH silently ignores the field — showing it would be
 * misleading). Submitted as `variant-initial-quantity`, a parallel
 * repeated field alongside `variant-color`/`variant-price`/`variant-cost`;
 * `actions.ts`'s `buildVariantsPayload` zips it positionally the same way.
 *
 * `description`/`short_description` (content-ai-domains PR3, base = PR2)
 * are two plain, optional, hand-typeable copy fields — no Gemini
 * reference anywhere in this component. `name`/`short_description` cap
 * client-side at their backend `Field(max_length=...)` values (4000/160)
 * as a UX nicety only; the server-side 422 remains authoritative (DD4).
 * `actions.ts`'s `buildProductPayload` omits either key from the relayed
 * body when blank (mirroring the existing `reason`/`initial_quantity`
 * omit-if-blank convention), which is also how an intentional clear is
 * expressed — the write model's `Field(default=None)` treats an omitted
 * key as "set to null" (DD4's documented full-replacement semantics, not
 * a partial PATCH per field).
 *
 * "Generate copy" (content-ai-domains PR 11) prefills the two fields above
 * by calling `generateProductCopyAction`, rendered ONLY when `productId`
 * is set — generation needs an existing product to build a prompt from,
 * so it never appears on the create form. Prefill is done via `ref.value`
 * assignment on the already-uncontrolled `<textarea>`/`<input>`, exactly
 * like `image-manager.tsx`'s alt-text refs — NOT `formAction`/`useActionState`
 * — so clicking it never submits the surrounding `<form>` (D5: the
 * existing "Save changes" button stays the only write path). A `null`
 * field in the response (DD6's partial-output policy) leaves that input's
 * current value untouched rather than clearing it.
 */
import { useActionState, useRef, useState, useTransition } from "react";
import { Sparkles, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  generateProductCopyAction,
  retireVariantAction,
  type ProductFormState,
} from "./actions";

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
  initialDescription?: string;
  initialShortDescription?: string;
  initialVariants?: ProductFormVariant[];
}

interface VariantRow {
  key: string;
  id: string | null;
  color: string;
  price: string;
  cost: string;
  initialQuantity: string;
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
    initialQuantity: "",
  }));
}

export function ProductForm({
  action,
  submitLabel,
  productId,
  initialName = "",
  initialModel = "",
  initialDescription = "",
  initialShortDescription = "",
  initialVariants,
}: ProductFormProps) {
  const [state, formAction, pending] = useActionState(action, INITIAL_STATE);
  const [rows, setRows] = useState<VariantRow[]>(() =>
    toInitialRows(initialVariants),
  );
  const [isRemoving, startRemoving] = useTransition();
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const shortDescriptionRef = useRef<HTMLInputElement>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [isGenerating, startGenerating] = useTransition();

  function handleGenerateCopy() {
    if (!productId) {
      return;
    }
    startGenerating(async () => {
      const result = await generateProductCopyAction(productId);
      if (result.error) {
        setGenerateError(result.error);
        return;
      }
      setGenerateError(null);
      // DD6 partial-output policy: a `null` field means "not generated" —
      // leave that input's current value untouched rather than clearing it.
      if (result.description !== null && descriptionRef.current) {
        descriptionRef.current.value = result.description;
      }
      if (result.short_description !== null && shortDescriptionRef.current) {
        shortDescriptionRef.current.value = result.short_description;
      }
    });
  }

  function addRow() {
    setRows((previous) => [
      ...previous,
      {
        key: nextRowKey(),
        id: null,
        color: "",
        price: "",
        cost: "",
        initialQuantity: "",
      },
    ]);
  }

  function updateRow(
    key: string,
    field: "color" | "price" | "cost" | "initialQuantity",
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
      <Card>
        <CardHeader>
          <CardTitle>Información básica</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 pb-5">
          <Input
            id="product-name"
            name="name"
            type="text"
            required
            defaultValue={initialName}
            label="Nombre"
          />
          <Input
            id="product-model"
            name="model"
            type="text"
            required
            defaultValue={initialModel}
            label="Modelo"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Descripción</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 pb-5">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="product-description"
              className="text-sm font-medium text-foreground"
            >
              Descripción
            </label>
            <textarea
              id="product-description"
              name="description"
              ref={descriptionRef}
              defaultValue={initialDescription}
              maxLength={4000}
              rows={4}
              className="border-border bg-background text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 rounded-lg border px-3 py-2 text-sm outline-none transition-colors focus-visible:ring-3"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="product-short-description"
              className="text-sm font-medium text-foreground"
            >
              Descripción corta
            </label>
            {/* Plain `<input>`, not the `Input` primitive: `Input` is a
                non-forwardRef function component, and `shortDescriptionRef`
                MUST resolve to a real DOM node for `handleGenerateCopy`'s
                direct `.value` prefill (this file's module docstring). */}
            <input
              id="product-short-description"
              name="short_description"
              type="text"
              ref={shortDescriptionRef}
              defaultValue={initialShortDescription}
              maxLength={160}
              className="border-border bg-background text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 h-10 rounded-lg border px-3 py-2 text-sm outline-none transition-colors focus-visible:ring-3"
            />
          </div>

          {productId !== undefined && (
            <div className="flex flex-col gap-1.5">
              <Button
                type="button"
                variant="outline"
                disabled={isGenerating}
                onClick={handleGenerateCopy}
                className="w-fit"
              >
                <Sparkles />
                Generar descripción
              </Button>
              {generateError && (
                <p role="alert" className="text-destructive text-sm">
                  {generateError}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {productId !== undefined && (
        <Card>
          <CardHeader>
            <CardTitle>Estado</CardTitle>
          </CardHeader>
          <CardContent className="pb-5">
            <Badge variant="success">Activo</Badge>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Variantes</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pb-5">
          {rows.map((row) => (
            <div
              key={row.key}
              className="border-border bg-muted/30 flex flex-wrap items-end gap-2 rounded-lg border p-3"
            >
              <input type="hidden" name="variant-id" value={row.id ?? ""} />
              <Input
                id={`${row.key}-color`}
                name="variant-color"
                type="text"
                required
                value={row.color}
                onChange={(event) =>
                  updateRow(row.key, "color", event.target.value)
                }
                label="Color"
                className="w-32"
              />
              <Input
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
                label="Precio"
                className="w-28"
              />
              <Input
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
                label="Costo"
                className="w-28"
              />
              {row.id === null && productId === undefined && (
                <Input
                  id={`${row.key}-initial-quantity`}
                  name="variant-initial-quantity"
                  type="number"
                  step="1"
                  min="0"
                  value={row.initialQuantity}
                  onChange={(event) =>
                    updateRow(row.key, "initialQuantity", event.target.value)
                  }
                  label="Cantidad inicial"
                  className="w-32"
                />
              )}
              <IconButtonRemove
                disabled={isRemoving}
                onClick={() => removeRow(row)}
              />
            </div>
          ))}
          <Button
            type="button"
            variant="secondary"
            onClick={addRow}
            className="w-fit"
          >
            Agregar variante
          </Button>
        </CardContent>
      </Card>

      {state.error && (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      )}

      <Button type="submit" disabled={pending} className="w-fit">
        {submitLabel}
      </Button>
    </form>
  );
}

function IconButtonRemove({
  disabled,
  onClick,
}: {
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      onClick={onClick}
      className="border-destructive/40 text-destructive hover:bg-destructive/10"
    >
      <X />
      Quitar
    </Button>
  );
}
