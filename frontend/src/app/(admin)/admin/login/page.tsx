/**
 * `/admin/login` — login page. Reachable both unauthenticated (renders
 * the form) and, transiently, mid-redirect for an already-authenticated
 * visit (`proxy.ts` bounces those to `/admin` before this ever renders —
 * see `admin-authentication` spec's "Already-Authenticated Visit To
 * Login Redirects To Landing").
 *
 * `next` is read here (Server Component, `searchParams` per Next 16's
 * async page-props contract) and handed to `LoginForm` as a plain
 * string — `signInAction` re-validates it with `isSafeAdminPath` itself,
 * so this extraction only needs to survive a malformed/array query
 * value, not repeat the safety check.
 */
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LoginForm } from "./login-form";

interface LoginPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function resolveNextParam(
  value: string | string[] | undefined,
): string | null {
  return typeof value === "string" ? value : null;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const next = resolveNextParam(params.next);

  return (
    <div className="bg-brand-ink relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-16">
      <div
        aria-hidden="true"
        className="bg-brand-primary/40 pointer-events-none absolute top-1/2 left-1/2 size-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[120px]"
      />
      <Card className="relative w-full max-w-[420px] gap-5 py-2 shadow-xl">
        <CardHeader className="items-center gap-2 text-center">
          <span className="font-heading text-2xl font-bold tracking-tight text-brand-primary">
            GCELL
          </span>
          <h1 className="text-lg font-semibold text-foreground">
            Iniciar sesión
          </h1>
          <p className="text-sm text-muted-foreground">
            Panel de administración
          </p>
        </CardHeader>
        <CardContent className="pb-5">
          <LoginForm next={next} />
        </CardContent>
      </Card>
    </div>
  );
}
