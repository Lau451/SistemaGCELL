/**
 * Reads and validates the two public Supabase env vars the catalog client
 * factories need. Fails fast with a named-variable error instead of
 * letting `createServerClient(undefined, undefined, ...)` fail obscurely.
 */

export interface CatalogSupabaseEnv {
  url: string;
  anonKey: string;
}

function requireEnvVar(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getCatalogSupabaseEnv(): CatalogSupabaseEnv {
  return {
    url: requireEnvVar("NEXT_PUBLIC_SUPABASE_URL"),
    anonKey: requireEnvVar("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  };
}
