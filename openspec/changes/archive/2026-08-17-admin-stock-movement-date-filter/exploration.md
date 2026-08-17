## Exploration: Date filter on stock movement history

### Current State

`admin-stock-movement-history` (archived 2026-08-15) shipped a read-only, per-variant, keyset-paginated view of `stock_movements`:

- `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements` (`backend/src/gcell/api/admin.py:681-703`) → `ListVariantStockMovementsUseCase.execute(product_id, variant_id, limit=20, before_id=None)` (`backend/src/gcell/stock/application/list_variant_stock_movements.py`) → `PostgresStockMovementHistoryReader.list_for_variant` (`backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py`).
- SQL: `SELECT id, variant_id, movement_type, quantity_delta, reason, created_at FROM stock_movements WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2) ORDER BY id DESC LIMIT $3`.
- `limit` clamped `[1,100]` (default 20); use case fetches `limit+1` and trims to compute `next_before_id`.
- IDOR guard (`VariantNotFoundError` → 404, never 403) runs before any reader call.
- Frontend `stock-history.tsx` holds LOCAL `useState` for `entries`/`cursor` — a documented deliberate deviation (design.md Decision 6) from the admin area's normal "server prop only" convention, needed because "Load more" appends. Resets via a compare-during-render pattern when the `initialHistory` prop reference changes (no `useEffect`).
- Proxy route allowlists only `limit`/`before_id` into a fresh `URLSearchParams`, never `request.url.search` verbatim (Decision 7).

### Why Date/Type Filtering Was Deferred

The archived proposal's Out-of-Scope table: *"Filter by movement type / date range — Keeps this slice a plain listing; adds query-shape and index questions."* This is now a **merged main-spec MUST NOT clause**, not just a proposal note: `openspec/specs/admin-stock-management/spec.md` (~line 245): *"The view MUST NOT display a computed running/resulting balance per row, and MUST NOT expose any filter by movement type or date range."* A date-filter change needs an explicit `MODIFIED Requirements` delta against that exact requirement (`Admin Views Per-Variant Movement History`), and `admin-api-access/spec.md` (~line 338) also needs a delta for its locked `limit`/`before_id`-only query-parameter contract.

### Schema/Index Reality

`supabase/migrations/20260810000453_stock_movements_ledger.sql`: only index is `stock_movements_variant_id_covering_idx ON stock_movements(variant_id) INCLUDE (quantity_delta)` — a SUM-covering index, not ordered by and not including `created_at`. `id DESC` keyset works today purely because `id` is a monotonic identity PK on an append-only, trigger-protected table (no UPDATE/DELETE), so PK order == chronological order. Adding a `created_at` range predicate forces heap fetches (acceptable per the original design's "row counts are small" reasoning, but worth re-surfacing).

### Pagination/Date-Filter Interaction — the Real Risk

SQL correctness is not actually at risk: `WHERE variant_id=$1 AND created_at>=$2 AND created_at<$3 AND ($4::bigint IS NULL OR id<$4) ORDER BY id DESC` is a valid, gap-free compound predicate for any *fixed* `$2`/`$3`. The real risk is client state: if a stale `before_id` cursor (computed under filter A) is sent alongside a *new* date filter B, results still satisfy both predicates but look broken to the user (newest matching rows under B silently excluded). This is the same shape as the already-solved Decision 6 problem ("load more" vs "reset on new page-1 data") — the fix is to treat a filter change as a fresh fetch (reset cursor to null, discard entries), not to invent new correctness logic.

### Approaches

1. **`?since`/`?until` SQL-level filter + plain two-input date range UI, no presets.**
   - Pros: smallest surface; reuses `ListVariantStockMovementsUseCase`'s clamp precedent; one new SQL predicate; proxy allowlist grows by two entries (same Decision 7 shape).
   - Cons: still needs an explicit reset-on-filter-change story; no quick-pick ergonomics.
   - Effort: Low–Medium.

2. **Same backend as (1) + quick presets (today / last 7 days / last 30 days).**
   - Pros: much better UX for the likely common case; zero backend difference from (1) — presets are pure client-side date math.
   - Cons: more frontend surface/tests; shares (1)'s reset risk.
   - Effort: Medium.

3. **Server/URL-driven filter (`[id]/page.tsx` `searchParams`) instead of client-only state**, layered on (1) or (2).
   - Pros: a filter change becomes a real navigation → new `initialHistory` prop reference → Decision 6's *existing* reset mechanism handles cursor/entries for free, no new reset code.
   - Cons: variant switching is currently client-driven, not URL-driven (archived design's own Open Question #2) — mixing a URL-driven date filter with a client-driven variant selector is an inconsistency `sdd-design` must resolve explicitly, not silently pick a side of.
   - Effort: Medium.

### Recommendation

Approach 1 as the locked MVP shape (simple `since`/`until`, no presets), with the reset problem resolved via Approach 3's server/URL-driven refetch — reusing Decision 6's existing reset-on-new-prop mechanism rather than writing new client reset logic — but the variant-switch/date-filter consistency question must be decided explicitly in `sdd-design`. Presets (Approach 2) are a natural fast-follow once the base filter and spec deltas are locked, since they add zero backend surface. `sdd-propose` must draft explicit `MODIFIED Requirements` deltas for both `admin-stock-management` (reverses the MUST NOT clause) and `admin-api-access` (extends the query-parameter contract) — this is a locked-requirement reversal, not a purely additive change.

### Hexagonal Constraints

Same `stock -> products` convention-only dependency direction (not enforced by `test_domain_boundary.py`). No domain or migration change needed for `since`/`until` filtering — `created_at` already exists on the table and is already read into `RecordedStockMovement`. `RecordedStockMovement` stays the application-layer read model, separate from the domain `StockMovement` value object, unchanged by this filter.

### Open Questions for Proposal
1. Timezone handling: `created_at` is `timestamptz`, UI date inputs are date-only — does `?since=2026-08-01` mean start of that day in UTC, or in the browser's local timezone? Needs an explicit, documented convention.
2. Presets now (Approach 2) or as a fast-follow later (user only asked for "filtro por fecha", not presets)?
3. Reset mechanism: URL-driven refetch (Approach 3, reuses Decision 6) vs. client-side self-reset — and how this interacts with the currently client-driven variant switcher.

### Risks
- Reversing a locked, merged-spec `MUST NOT` clause needs deliberate `MODIFIED Requirements` deltas in two spec files, not a silent overwrite.
- Stale keyset cursor across a filter change is a real UX bug class unless explicitly designed for (known fix pattern exists — Decision 6 precedent — but must be re-applied, not assumed).
- `created_at` isn't covered by the existing covering index; range predicates force heap fetches — acceptable now per original design's row-count reasoning, revisit with an index if ever measured as slow.

### Ready for Proposal
Yes.
