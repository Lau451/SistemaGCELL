```yaml
schema: gentle-ai.verify-result/v1
change: admin-stock-movement-date-filter
evidence_revision: cfdff24 (PR1 6597a21/463824b, PR2 63824a0/7fced46, PR3 dd42ed6/cfdff24)
verdict: pass
blockers: 0
critical_findings: 0
warnings: 0
suggestions: 0
requirements: 7/7
scenarios: 31/31
tasks: 23/23
test_command_1: "cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q"
test_command_1_result: "352 passed, 2 pre-existing/unrelated warnings"
test_command_2: "cd frontend && npm test -- --run"
test_command_2_result: "344 passed, 47 files"
test_command_3: "cd frontend && npx tsc --noEmit"
test_command_3_result: "0 errors"
```

## Verification Report: admin-stock-movement-date-filter

Delivered as 3 chained PRs on the same branch: backend (`6597a21`/`463824b`), frontend date-filter (`63824a0`/`7fced46`), variant switcher (`dd42ed6`/`cfdff24`).

### Key findings (re-run independently, not trusted from prior context)
- `InvertedDateRangeError(ValueError)` present with `since`/`until` in its constructor, caught by the existing `_execute_or_raise` mapping — no new except arm.
- `list_variant_stock_movements.py` ordering confirmed: ownership guard → normalize (naive→UTC, midnight-until expansion) → inverted-range check → reader call. A dedicated test proves a foreign variant_id + inverted range raises `VariantNotFoundError`, not `InvertedDateRangeError` — ordering holds.
- Both `postgres_stock_movement_history_reader.py` and `in_memory_stock_movement_history_reader.py` implement matching, inclusive since/until filtering in lockstep.
- `admin.py`'s route accepts plain `datetime | None` params, no `Query()` validators.
- `stock-history-dates.ts` produces offset-aware ISO-8601 instants with microsecond precision; sign inversion for `getTimezoneOffset()` is correct; `presetRange` matches D15 (0/6/29 days back, inclusive of today).
- Proxy `ALLOWED_QUERY_PARAMS` is exactly 4 entries, fresh `URLSearchParams` rebuild, never raw passthrough.
- `stock-history.tsx` is URL-driven (`router.push`), explicitly reuses the archived Decision 6 reset mechanism rather than reimplementing it, and has D13's two distinct empty-state strings.
- `variant-switcher.tsx` renders `null` for <2 variants, marks the active variant `aria-current="page"`, builds hrefs via `URLSearchParams` preserving `since`/`until`.
- `[id]/page.tsx` does a membership check (`resolveActiveVariant`) rather than trusting the raw `?variant=` param; `notFound()` is gated on `product.variants.length > 0` (confirmed in shipped code, not just the apply report) so zero-variant products stay reachable; absent `?variant=` defaults to `variants[0]`; the header docstring was corrected.
- `stock-manager.tsx` confirmed untouched by this change (D16) — last modified in an unrelated prior commit, `git status` clean.
- Zero domain-layer files and zero Supabase migration files touched across all 3 PRs combined.

### Issues
None.
