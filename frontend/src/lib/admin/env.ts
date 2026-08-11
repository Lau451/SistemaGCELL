/**
 * Reads the server-only `BACKEND_URL` env var the admin proxy Route
 * Handler (PR3) needs to reach FastAPI. Same `requireEnvVar`-style
 * fail-fast pattern as `lib/supabase/env.ts`, except this var has a
 * default: local dev should work without an `.env.local` at all.
 *
 * Defaults to `http://127.0.0.1:8000`, NOT `http://localhost:8000` — see
 * design.md "`GET /api/admin/products`": Node's DNS resolution of
 * `localhost` can intermittently prefer `::1`, while `uvicorn` binds
 * `127.0.0.1` by default, producing a flaky `ECONNREFUSED` that only
 * reproduces some of the time. `BACKEND_URL` is deliberately never
 * exposed as `NEXT_PUBLIC_*` — it is server-only, read solely inside the
 * proxy Route Handler, never shipped to the browser bundle.
 */

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export function getBackendUrl(): string {
  return process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
}
