/**
 * Reads and validates the two public Supabase env vars the catalog client
 * factories need. Fails fast with a named-variable error instead of
 * letting `createServerClient(undefined, undefined, ...)` fail obscurely.
 *
 * `NEXT_PUBLIC_*` vars are only inlined into the client bundle where
 * `process.env.NEXT_PUBLIC_X` appears as a literal property access — a
 * dynamic `process.env[name]` lookup is invisible to that build-time
 * replacement and reads as `undefined` in the browser (still works
 * server-side, where `process.env` is the real runtime env). Both call
 * sites below MUST keep the literal form, even though this is used from
 * both Server Components and client components like `ImageManager`.
 */

export interface CatalogSupabaseEnv {
  url: string;
  anonKey: string;
}

function requireEnvVar(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getCatalogSupabaseEnv(): CatalogSupabaseEnv {
  return {
    url: requireEnvVar("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
    anonKey: requireEnvVar(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY",
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    ),
  };
}
