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
    <div className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-16">
      <h1 className="text-xl font-semibold">Admin sign in</h1>
      <LoginForm next={next} />
    </div>
  );
}
