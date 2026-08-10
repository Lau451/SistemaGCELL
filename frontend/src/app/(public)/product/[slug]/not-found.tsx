import Link from "next/link";

/**
 * Rendered when `getCatalogProductBySlug` resolves `data: null` and the
 * detail page calls `notFound()`.
 */
export default function ProductNotFound() {
  return (
    <div
      role="status"
      data-testid="product-not-found"
      className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-24 text-center"
    >
      <h1 className="text-xl font-semibold">No encontramos este producto</h1>
      <p className="text-muted-foreground text-sm">
        El producto que buscás no existe o ya no está disponible.
      </p>
      <Link
        href="/"
        className="text-primary text-sm underline-offset-4 hover:underline"
      >
        Volver al catálogo
      </Link>
    </div>
  );
}
