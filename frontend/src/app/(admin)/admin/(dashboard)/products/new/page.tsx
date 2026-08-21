/**
 * `/admin/products/new` — create page. Renders `product-form.tsx` wired
 * to `createProductAction`; no slug field, ever (spec: "Product Creation
 * Form...MUST NEVER accept an admin-typed `slug`").
 *
 * @see design.md "Data Flow" (Create)
 */
import { createProductAction } from "../actions";
import { ProductForm } from "../product-form";

export default function NewProductPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10">
      <h1 className="font-heading text-2xl font-semibold">Nuevo producto</h1>
      <ProductForm action={createProductAction} submitLabel="Crear producto" />
    </div>
  );
}
