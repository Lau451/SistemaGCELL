# Design: Admin Stock Movement Date Filter

## Technical Approach

Additive read-side filter on the existing movement-history slice (D1). Two optional
`datetime` params thread route → use case → reader → one extra SQL predicate pair.
All validation, normalization and the inverted-range rejection live in
`ListVariantStockMovementsUseCase` (D6, D10), mirroring the existing `limit` clamp.
The proxy allowlist grows by two (D9). The frontend filter is **URL-driven**
(DD2), so a filter change is a real navigation that produces a new `initialHistory`
prop reference and the archived Decision 6 compare-during-render reset fires
unchanged. No new endpoint, no port added, no migration (D8), no domain change.

**Scope expansion (D14):** the variant switcher is built in this change. It is the
same URL model — a third `searchParams` key, `?variant=<id>` (DD3) — so switcher
and date filter share one state model rather than colliding. It adds **zero**
backend surface: the endpoint is already per-variant and already ownership-guarded.

## Architecture Decisions

### DD1: Browser-local day boundaries, carried as offset-aware ISO-8601 instants

| Option | Tradeoff | Decision |
|---|---|---|
| UTC day boundaries | GCELL is UTC−03. A movement recorded 21:00–23:59 local falls on the *next* UTC day, so "today" silently omits every evening movement — an off-by-one the admin would hit weekly | Rejected |
| Browser-local day, wire format = naked date string | Server Component (`[id]/page.tsx`) would have to convert, using **server** TZ, not browser TZ | Rejected |
| **Browser-local day, wire format = offset-aware instant** | Slightly ugly URL; conversion must happen client-side | **Chosen** |

The backend never guesses a timezone: it compares `timestamptz` to a supplied
instant. The *day* concept exists only in the browser, where the admin's calendar
actually lives. Exact conversion for `"2026-08-15"` (client-side, pure module):

- `since` → `2026-08-15T00:00:00.000000-03:00`
- `until` → `2026-08-15T23:59:59.999999-03:00` (D11: whole day, inclusive)

Offset comes from `new Date("2026-08-15T00:00:00").getTimezoneOffset()` — resolved
per selected date, so DST is correct for free. Microseconds are written into the
*string*, not derived from a JS `Date`, so there is no millisecond truncation gap
between `until` and the next midnight: `<= 23:59:59.999999` is exactly `<` next
midnight at Postgres' microsecond resolution.

**Naive-input rule** (application code, D6): a `datetime` with `tzinfo is None`
(e.g. a hand-written `?since=2026-08-15` curl) is normalized to UTC. A naive
`until` at exactly `00:00:00.000000` is then expanded to
`+1 day − 1 microsecond`, so a date-only `until` means the whole day at the API
boundary too, honoring D11 literally rather than only in the UI. Accepted wart: an
API caller wanting "up to exactly midnight" must send `00:00:00.000001`.

### DD2: URL/`searchParams`-driven filter; the URL becomes the single source of truth for history-view state

**Verified fact that resolves the flagged inconsistency**: there is **no variant
switcher in the shipped code**. `[id]/page.tsx` hardwires
`variantId={product.variants[0].id}`, and `stock-history.tsx` renders no variant
control. The "client-driven variant switcher" the proposal and exploration flag is
documented intent in the archived design, never built.

| Option | Tradeoff | Decision |
|---|---|---|
| New client-side reset in `stock-history.tsx` | Duplicates Decision 6's already-tested reset; filter not shareable/back-buttonable; and it would *establish* client-state as the model, guaranteeing the two-model split when the switcher is built | Rejected |
| **URL `searchParams` on `[id]/page.tsx`** | A filter change re-runs all four server fetches on that page | **Chosen** |

Rationale: this change does not create two coexisting state models — it establishes
**one** (URL-driven history-view state) *before* the switcher exists, and records
that the future switcher must be URL-driven (`?variant=`) to stay consistent.
Choosing client state now is what would deepen the inconsistency. It also closes
the proposal's only High risk (stale keyset cursor) with an existing mechanism
instead of new code, and makes **D12 structural**: `since`/`until` live in the URL,
so any navigation that changes the variant preserves them by construction. D12 is
additionally honored by `handleLoadMore` re-sending the current `since`/`until` on
every cursor page.

> **Update (D14).** The switcher is no longer future work — DD3 builds it in this
> change, on exactly the `?variant=` URL model this decision reserved for it. Every
> line of DD2's reasoning stands unchanged; only its "until the switcher exists"
> framing is superseded. D12 stops being merely structural-by-construction and
> becomes directly exercisable and testable.

Accepted cost: the four sequential `fetch`es in `[id]/page.tsx` re-run per filter
change. All are already `cache: "no-store"` on a single-admin tool, so no caching
regression; parallelizing with `Promise.all` is a separate concern.

React state safety: an RSC soft navigation re-renders the client components in
place (same position, same key), so `ProductForm`'s uncontrolled inputs keep
unsaved edits — only `StockHistory`, which opts into the reset, resets.

### DD3: Variant switcher = a server-rendered link row driven by `?variant=<id>` (D14)

**Read of the actual page.** Only `StockHistory` is variant-scoped. `ProductForm`,
`ImageManager` and `StockManager` all receive the **full** variant list and are
whole-product surfaces; `StockManager` additionally owns an *uncontrolled* variant
`<select name="variant-id" defaultValue={stock[0]?.variant_id}>` that chooses a
**write target**, not a view. So the switcher scopes exactly one section.

| Option | Tradeoff | Decision |
|---|---|---|
| Client `<select>` + `router.push` | Needs a new `"use client"` island for zero computation; a `<select>` is a form control, semantically wrong for navigation | Rejected |
| Local `useState` in a client wrapper | Re-introduces the second state model DD2 exists to prevent; breaks D12 and shareable URLs | Rejected |
| **Server-rendered `<nav>` of `<Link>`s, one per variant** | Wide products render a wide row (GCELL variants are phone colors: 2–5) | **Chosen** |

Each link's `href` is built with `URLSearchParams` (never string concatenation —
see DD1's encoding gotcha, which applies verbatim to `since`/`until` riding along),
carrying `variant` plus any active `since`/`until`, so **D12 holds by
construction**. The active variant is marked with `aria-current="page"` — a
semantic proxy for tests, matching the repo's existing "Out of stock" label
precedent rather than asserting CSS classes. The switcher renders nothing when
`variants.length < 2`: a one-variant product gets no pointless control, and the
page stays byte-identical to today for the common single-variant case.

**Scope of the switcher.** It changes **only** which variant's `StockHistory` is
rendered. `StockManager` is deliberately left untouched: its list is a whole-product
stock overview, and its `<select>` is an uncontrolled write-target chooser. Coupling
its `defaultValue` to `?variant=` would not even work by itself — React does not
reset an uncontrolled DOM value when `defaultValue` changes on re-render, so it
would need `key={activeVariantId}`, which **discards the admin's in-progress
quantity/reason input on every variant switch** and directly contradicts DD2's
preserved-unsaved-edits property. Not worth it. (Flagged: this is a UX call D1–D15
does not cover — see Open Questions.)

**No `key` on `StockHistory`.** A variant switch is a soft navigation, so
`initialHistory` arrives as a fresh object reference and Decision 6's
compare-during-render reset snaps `entries`/`cursor` back to page one — already
tested, no new mechanism. Adding `key={activeVariantId}` would bypass that tested
path with a remount. The new `variantId` prop simultaneously retargets
`handleLoadMore`, so cursor pagination cannot leak across variants.

### DD4: An unknown `?variant=` 404s — membership checked against already-fetched data, before any history read

| Option | Tradeoff | Decision |
|---|---|---|
| Fall back to `variants[0]` | Silently renders a *different* variant's history than the URL claims; a bookmarked URL for a deleted variant lies instead of failing | Rejected |
| 403 / error banner | Violates the repo's "404, never 403" IDOR rule — 403 confirms the variant exists elsewhere | Rejected |
| **`notFound()` (404)** | A stale bookmark hard-fails instead of degrading | **Chosen** |

`resolveActiveVariant` matches the param against `product.variants` — data already
fetched under the authenticated proxy — so this is a pure in-memory membership test:
no extra backend read, and "does not exist" and "belongs to another product" are
**indistinguishable**, exactly like `VariantNotFoundError` in
`list_variant_stock_movements.py:53` (`# never 403 (IDOR)`). It also *closes* a
surface rather than opening one: without the guard, a hand-typed foreign variant id
would be forwarded to the movements proxy and the failed fetch would fall back to
`EMPTY_STOCK_HISTORY`, rendering a misleading "No movements recorded yet."

Two consequences worth stating: the check runs **before** the history fetch is
issued (mirroring "ownership checked before any read"), and once matched the page
uses the **matched variant's own `id`**, never the raw param, when building the
fetch URL — so no attacker-controlled string ever reaches a path segment. A
malformed value (`?variant=not-a-uuid`) fails the same membership test and 404s;
no UUID parsing is added. An **absent** `?variant` defaults to `variants[0].id`,
keeping every existing URL and bookmark working (backward compatible).

**Shared param normalization**: `searchParams` values are `string | string[] |
undefined`. A repeated key (`?variant=a&variant=b`) yields an array; take the first
entry, then apply the normal rule. Same normalization for `since`/`until`.

## Data Flow

    variant links (server) ──href=?variant&since&until──▶ soft nav
    filter inputs / presets (client) ──toSinceParam/toUntilParam──▶ router.push(?since&until&variant)
                                                                          │ soft nav
    [id]/page.tsx (RSC) ──await searchParams──▶ resolveActiveVariant ──unknown──▶ notFound() 404
                          │ known / absent → variants[0]
                          ├─▶ inverted? ──yes──▶ render guard copy, no fetch
                          └─▶ fetchAdminProductStockHistory(activeVariantId, since, until)
                                                     └─▶ proxy route.ts (allowlist ×4)
                                                                          │ adminBackendFetch
    admin.py GET ─▶ ListVariantStockMovementsUseCase ─▶ products.get_by_id (404, never 403)
                        │ normalize tz → expand midnight until → since > until? → 422
                        └─▶ history_reader.list_for_variant ─▶ stock_movements
                                                                          │
    new initialHistory reference ──▶ Decision 6 compare-during-render reset (entries+cursor)

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/stock/application/exceptions.py` | Modify | Add `InvertedDateRangeError(ValueError)` |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | Modify | `since`/`until` params, tz-normalize, midnight-`until` expansion, inverted-range raise |
| `backend/src/gcell/stock/application/stock_movement_history_reader.py` | Modify | Port gains `since`/`until` (defaulted `None`) |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py` | Modify | Two `$4`/`$5` predicates, positional order preserved |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py` | Modify | **Not in the proposal's affected-areas table** — must mirror the filter or use-case unit tests cannot cover it |
| `backend/src/gcell/api/admin.py` | Modify | Two optional `datetime` params, passed through. No `Query()`, no new `except` arm |
| `frontend/src/app/api/admin/.../stock/movements/route.ts` | Modify | `ALLOWED_QUERY_PARAMS = ["limit", "before_id", "since", "until"]` — **`variant` is NOT forwarded**: it is a page-level view key, and the variant already lives in the path |
| `frontend/src/app/(admin)/admin/products/stock-history-dates.ts` | Create | Pure day↔instant/preset math (same "pure helper out of the component" precedent as commit 4881583's `signedQuantityDelta`) |
| `frontend/src/app/(admin)/admin/products/variant-switcher.tsx` | Create | **New (D14/DD3)** — server component: `<nav>` of `<Link>`s, `aria-current` on active, `URLSearchParams` href builder preserving `since`/`until`, renders `null` for <2 variants |
| `frontend/src/app/(admin)/admin/products/stock-history.tsx` | Modify | Date inputs, 3 presets, Clear, `useRouter`+`useTransition` push (preserving `variant`), `since`/`until` props, D13 empty states, filtered `handleLoadMore` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modify | `await searchParams`; `resolveActiveVariant` + `notFound()` (DD4); render `VariantSwitcher`; pass `activeVariantId` to `StockHistory`; inverted guard; forward params via `URLSearchParams`; update the file's header docstring, which currently documents variant switching as a client-side fetch |
| `frontend/src/app/(admin)/admin/products/stock-manager.tsx` | **Unchanged** | DD3: whole-product surface, uncontrolled write-target select |
| `supabase/migrations/**`, `**/domain/**` | Unchanged | D8 / no domain change |

## Interfaces / Contracts

```python
class InvertedDateRangeError(ValueError):  # -> 422 via existing _execute_or_raise
    def __init__(self, since: datetime, until: datetime) -> None: ...

async def execute(self, product_id: UUID, variant_id: UUID, limit: int = 20,
                  before_id: int | None = None,
                  since: datetime | None = None,
                  until: datetime | None = None) -> StockMovementPage: ...

async def list_for_variant(self, variant_id: UUID, limit: int, before_id: int | None,
                           since: datetime | None = None,
                           until: datetime | None = None) -> list[RecordedStockMovement]: ...
```

```sql
SELECT id, variant_id, movement_type, quantity_delta, reason, created_at
FROM stock_movements
WHERE variant_id = $1
  AND ($2::bigint IS NULL OR id < $2)
  AND ($4::timestamptz IS NULL OR created_at >= $4)
  AND ($5::timestamptz IS NULL OR created_at <= $5)
ORDER BY id DESC
LIMIT $3
```

`$3` stays `limit`, so the existing `fetch(sql, variant_id, before_id, limit)` call
only appends two arguments. Null-guard idiom copied verbatim from the `$2` clause.

```ts
// stock-history-dates.ts
export function toSinceParam(day: string): string;   // "2026-08-15" -> "...T00:00:00.000000-03:00"
export function toUntilParam(day: string): string;   // "2026-08-15" -> "...T23:59:59.999999-03:00"
export function dayFromParam(param: string): string; // param.slice(0, 10) — redisplay in <input type="date">
export function presetRange(p: "today" | "last7" | "last30"): { since: string; until: string };
export function isInvertedRange(since?: string, until?: string): boolean; // ISO strings compare lexically
```

```ts
// variant-switcher.tsx (server component — no "use client")
export interface VariantSwitcherProps {
  productId: string;
  variants: { id: string; color: string }[]; // structural subset of ProductFormVariant
  activeVariantId: string;
  since?: string;
  until?: string;
}
export function VariantSwitcher(props: VariantSwitcherProps): ReactNode; // null when variants.length < 2

// [id]/page.tsx — DD4 guard. Returns the matched variant, or null => notFound().
function resolveActiveVariant(
  variants: ProductFormVariant[],
  raw: string | string[] | undefined,
): ProductFormVariant | null;
```

Label = `color` only. `price` is already rendered by `ProductForm` directly above,
so repeating it here duplicates data and drags in currency formatting for no gain.

Presets (local days, `until` always today): `today` → today; `last7` → today−6;
`last30` → today−29 (both inclusive of today = 7 / 30 calendar days) — **locked by
D15**, no longer an open call.

**Encoding gotcha**: a raw `+HH:MM` offset in a query string decodes to a space.
Every hop must build the query with `URLSearchParams` (the proxy already does);
`[id]/page.tsx` and `variant-switcher.tsx` must not string-concatenate.

D13 copy (`stock-history.tsx`):
- no filter, zero rows → `"No movements recorded yet."` (unchanged string)
- filter active, zero rows → `"No movements in the selected date range."`
- inverted range guard (page-level, no fetch) → `"Start date is after end date."`

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (use case) | naive→UTC normalization; midnight-`until` expansion; `since == until` is valid; `since > until` → `InvertedDateRangeError`; ownership guard still runs first (foreign variant + inverted range → `VariantNotFoundError`, zero reader calls); both `None` → today's exact behavior | Extend `test_list_variant_stock_movements.py` with the filtered in-memory adapter |
| Unit (port) | Protocol still declares exactly `{list_for_variant}` | Existing port-shape test |
| Integration (db) | Boundary rows at `since` and `until` included; range + `before_id` compound predicate gap-free across pages; variant isolation under a filter | Extend `test_stock_movement_repository.py` |
| Integration (api) | `?since`/`?until` filter; inverted → 422 (body from `str(exc)`); `?since=abc` → 422 not 500; omitting both byte-identical to current response; 404 for foreign variant still precedes 422 | Extend `test_admin_stock.py` |
| Frontend (proxy) | Exactly four params forwarded; a fifth injected param dropped; an injected `variant` param dropped; `+HH:MM` offset survives encoding | Extend `movements/__tests__/route.test.ts` |
| Frontend (pure) | `toSinceParam`/`toUntilParam`/`presetRange` under a mocked negative **and** positive offset; `dayFromParam` round-trip | New `stock-history-dates.test.ts` |
| Frontend (switcher) | One link per variant, labelled by color; `aria-current="page"` on the active one; hrefs carry `?variant=` **and** the active `since`/`until` (D12); renders nothing for a single-variant product; offset in the href is percent-encoded, not a space | New `variant-switcher.test.tsx` |
| Frontend (page) | Absent `?variant` → `variants[0]` (backward compat); valid `?variant` → that variant's history fetched; **foreign/nonexistent/malformed `?variant` → `notFound()`, and the movements proxy is NOT called**; the fetch URL uses the matched variant id, not the raw param; `StockManager` output is unaffected by `?variant`; inverted URL renders the guard and issues **no** fetch | Extend `[id]/page.test.tsx` |
| Frontend (component) | Preset click pushes the right query and preserves the active `variant`; both D13 empty states; `handleLoadMore` re-sends `since`/`until` and targets the active variant; new `initialHistory` reference resets entries+cursor on a variant switch | Extend `stock-history.test.tsx` |

## Threat Matrix

| Boundary | Applicability |
|---|---|
| Documentation-like paths | N/A — no file classification or execution |
| Git repository selection | N/A — no VCS automation |
| Commit / push state | N/A |
| PR commands | N/A |
| Shell / subprocess | N/A |
| HTTP query passthrough (routing-adjacent) | **Applicable** — the proxy allowlist grows from 2 to 4 entries. It must stay a fresh `URLSearchParams` rebuild, never `new URL(request.url).search` (D9 / archived Decision 7). RED test: an injected fifth param is dropped |
| User-controlled `?variant=` → resource selection (IDOR-adjacent) | **Applicable (new, D14/DD3)** — the param selects which variant's history is read. Safe behavior: membership-checked against the already-authorized `product.variants` **before** any history fetch; unknown/foreign/malformed → `notFound()` 404, never 403 and never a fallback render; the matched variant's own id (never the raw param) is interpolated into the fetch path; `variant` is not in the proxy allowlist. RED tests: foreign variant id → 404 with zero proxy calls; malformed value → 404; raw param never reaches a URL path segment |

## Migration / Rollout

No migration required (D8). No schema change, no index, no dependency, no feature
flag. Both params optional (D7), so a single-commit revert restores prior behavior
exactly. The switcher is likewise revertible: `?variant` absent falls back to
`variants[0]`, which is precisely today's hardwired behavior. The unindexed
`created_at` range predicate forces heap fetches — accepted per D8's row-count
reasoning; revisit only if measured slow.

## Open Questions

- [x] **RESOLVED — locked as D15.** "Last 7 days" is today−6 through today (7
      calendar days including today); "last 30 days" is today−29 through today.
      Confirmed by the user on 2026-08-16; this design's preset math already
      matched and is unchanged.
- [x] **RESOLVED — locked as D14.** The variant switcher **is built in this
      change**, not deferred. The earlier draft's "building the switcher stays out
      of scope. Confirm." is superseded: DD3 designs it as a URL-driven
      (`?variant=`) server-rendered link row and DD4 defines its validation. D12 is
      now directly exercisable, not merely structural.
- [x] **RESOLVED — locked as D16.** `StockManager`'s record-movement variant
      `<select>` stays **independent** from `?variant=` — no pre-selection, no
      coupling. Confirmed by the user on 2026-08-16 via AskUserQuestion: avoids
      discarding in-progress quantity/reason input when the admin switches which
      variant's history they're viewing. DD3's default stands as designed.
