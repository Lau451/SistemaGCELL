import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="bg-brand-cream flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <span className="font-heading text-brand-primary text-3xl font-bold tracking-tight">
        404
      </span>
      <h1 className="font-heading text-foreground text-xl font-semibold">
        Página no encontrada
      </h1>
      <p className="text-muted-foreground max-w-sm text-sm">
        La página que buscás no existe o fue movida.
      </p>
      <Button className="mt-2" render={<Link href="/" />}>
        Volver al catálogo
      </Button>
    </div>
  );
}
