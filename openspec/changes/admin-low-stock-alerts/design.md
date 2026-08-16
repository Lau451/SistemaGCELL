# Design: Admin Low-Stock Alerts

## Technical Approach

Frontend-only. A new async Server Component `stock-alert-badge.tsx` fetches
`GET /api/admin/stock?below=5` with the exact `fetchAdminStock` idiom of
`(admin)/admin/stock/page.tsx` (`headers()` → host / `x-forwarded-proto` /
`cookie`, same-origin, `cache: "no-store"`), derives the count as
`rows.length`, and renders it inside the existing `<Link href="/admin/stock">`
in `admin/layout.tsx`. `AdminLayout` stays a **synchronous** Server Component;
the badge is mounted through `<Suspense fallback={null}>`. Zero backend files,
zero proxy changes, zero migration (D3, D5).

## Architecture Decisions

### Decision 1: Isolated async badge component + Suspense — not an async layout

| Option | Tradeoff | Decision |
|---|---|---|
| Make `AdminLayout` `async` and fetch inline | Simplest diff, but the whole admin shell (header, nav, sign-out, `{children}`) blocks on the round trip D5 accepts, and all four existing `layout.test.tsx` cases must be rewritten to the `await Component(props)` pattern | Rejected |
| Client component + `useEffect` | Adds a client bundle and a second waterfall, and abandons the server-only cookie-forwarding pattern every admin read uses | Rejected |
| `stock-alert-badge.tsx` (async RSC) inside `<Suspense fallback={null}>` | Nav renders immediately and stays clickable while the count streams in; a failure is contained to one subtree; layout stays sync so its existing tests are untouched and the badge gets its own test file | **Chosen** |

### Decision 2: Failure and zero collapse to `null`; the 401 is the gate

The badge never throws. There is no `error.tsx` under `(admin)/`, so an
uncaught throw in the shell would take down every admin page — the exact
opposite of an additive badge. So the whole fetch (network throw, `!ok`,
`json()` parse throw) is wrapped and degrades to "render nothing", the same
render as count `0` (D6).

Auth needs no new logic. `proxy.ts` gates `/admin/:path*` only — `/api/admin/*`
is deliberately outside its matcher, so the badge's own fetch can **never** be
redirected to the login HTML page; it receives the Route Handler's own
`401 {"error":"unauthenticated"}` and omits the badge. No redirect loop is
structurally possible.

`(admin)/admin/login/page.tsx` **is** wrapped by this layout, so an
unauthenticated login render issues one same-origin fetch that 401s and shows
nothing. Accepted: Next 16 gives Server Components no supported pathname API,
so skipping by path would depend on an undocumented header. One wasted 401 per
login render is cheaper than that coupling.

Payload: `?below=5` narrows server-side, so the response already carries only
low-stock rows — bounded by the low-stock count, not the catalog. A count-only
endpoint or `X-Total-Count` header would be cheaper but is excluded by D3/D5.

## Data Flow

    layout.tsx (sync)
      └─ <Link href="/admin/stock"> Stock
           └─ <Suspense fallback={null}>
                └─ StockAlertBadge (async RSC)
                     │ headers() → host, x-forwarded-proto, cookie
                     ▼
              GET /api/admin/stock?below=5   (allowlist rebuild, adminBackendFetch)
                     ▼
              GET /admin/stock?below=5  →  ListCatalogStockLevelsUseCase
                     ▼
              rows[] ── rows.length ──▶ 0 or fetch failure → null (nothing)
                                        n > 0              → <span>(n)</span>

## File Changes

| File | Action | Description |
|---|---|---|
| `frontend/src/app/(admin)/admin/stock-alert-badge.tsx` | Create | Async RSC: fetch, count, safe `null` (Decisions 1–2) |
| `frontend/src/app/(admin)/admin/stock-alert-badge.test.tsx` | Create | Threshold, zero, all three failure modes |
| `frontend/src/app/(admin)/admin/layout.tsx` | Modify | `<Suspense fallback={null}>` badge inside the existing Stock `<Link>` |
| `frontend/src/app/(admin)/admin/layout.test.tsx` | Modify | One added case, mocking `./stock-alert-badge`; existing four untouched |
| `frontend/src/app/api/admin/stock/route.ts`, `backend/**`, `supabase/migrations/**`, `(admin)/admin/page.tsx` | Unchanged | Verified (D5) |

## Interfaces / Contracts

```tsx
// stock-alert-badge.tsx — reuses AdminStockRow's shape; only length is read.
export async function StockAlertBadge() {
  const count = await fetchLowStockCount();   // number | null, never throws
  if (count === null || count === 0) return null;          // D6
  return (
    <span className="text-destructive ml-1 text-xs font-medium">({count})</span>
  );
}
```

```tsx
// layout.tsx — explicit {" "} keeps the accessible name exactly "Stock (3)".
<Link href="/admin/stock" className="text-sm">
  Stock{" "}
  <Suspense fallback={null}>
    <StockAlertBadge />
  </Suspense>
</Link>
```

D7 styling is the **literal** admin zero-stock convention, not a new one:
`text-destructive` (`admin/products/page.tsx:106`, `admin/stock/page.tsx:161`)
plus the sibling-label classes `ml-1 text-xs font-medium`
(`products/page.tsx:111`, `stock/page.tsx:164`), applied here on `count > 0`
instead of `quantity === 0`. The pill style in `catalog/variant-picker.tsx:100`
is public-catalog, not admin, and is deliberately not copied.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (badge) | Fetch URL is exactly `…/api/admin/stock?below=5`; 3 rows → `(3)` carrying `text-destructive`; `[]` → renders nothing (D6); `!response.ok` (401 / 502) → nothing, no throw; `fetch` rejects → nothing, no throw; `json()` throws → nothing, no throw; cookie header forwarded | `stock-alert-badge.test.tsx`: `vi.mock("next/headers")` + `vi.spyOn(globalThis,"fetch")`, `const jsx = await StockAlertBadge(); render(jsx)` — the `stock/page.test.tsx` precedent |
| Unit (layout) | Badge slot sits inside the `/admin/stock` link; link accessible name is `Stock (3)`; existing four cases still pass unchanged | Extend `layout.test.tsx`; `vi.mock("./stock-alert-badge")` with a **sync** stub (RTL cannot client-render an async RSC under `Suspense`) |
| Integration | None new. `?below=5` inclusive `<=` semantics are already proven by `backend/tests/integration/api/test_admin_stock.py` and the proxy allowlist test | Reused as-is (D3) |
| E2E | N/A — the repo has no E2E harness (`vitest run` only) | — |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. Reference rows are all `N/A`
for the same reason. Change-specific: **no new user-controlled input** (the
threshold is a hard-coded literal `5`, never read from a query param, cookie,
or env), **no new endpoint** (the proxy allowlist and `verify_admin_jwt` are
untouched), **read-only** (no write path, no schema change), **no new
dependency**. Auth reuses `adminBackendFetch`'s existing `getClaims()` gate.

## Migration / Rollout

No migration required. No schema, feature flag, or dependency change.
Single-commit revert removes the badge component and the layout's `Suspense`
block; `/admin/stock` and `/admin/products` are untouched.

## Open Questions

None blocking. One deliberate consequence is recorded rather than deferred:
the badge fetch also runs on `/admin/login` (that page is inside this layout)
and 401s there, rendering nothing — see Decision 2.
