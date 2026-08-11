import Link from "next/link";

/**
 * `/admin` — default landing page for the authenticated admin area. The
 * default redirect target for `signInAction` (unsafe/absent `next`) and
 * `proxy.ts`'s already-authenticated `/admin/login` bounce
 * (`admin-authentication` spec). Minimal by design — this change's
 * `product_decisions.scope` deliberately narrows to exactly one proof
 * page (`/admin/products`), no dashboard widgets.
 */
export default function AdminLandingPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Admin</h1>
      <p className="text-muted-foreground">
        <Link href="/admin/products" className="text-primary underline">
          View products
        </Link>
      </p>
    </div>
  );
}
