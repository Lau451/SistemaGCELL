import Link from "next/link";
import { Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <h1 className="font-heading text-2xl font-semibold">Administración</h1>
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Bienvenido</CardTitle>
        </CardHeader>
        <CardContent className="pb-5">
          <Button render={<Link href="/admin/products" />}>
            <Package />
            Ver productos
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
