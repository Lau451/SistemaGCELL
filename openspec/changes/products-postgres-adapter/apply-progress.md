# Apply Progress: products-postgres-adapter

## Batch: PR1 — Phase 1 Domain Realignment

**Branch**: `pr1-products-domain-realignment` (branched from `main`)
**Mode**: Strict TDD
**Scope**: Phase 1 tasks only (1.1-1.7). Phase 2 (Postgres adapter) and Phase 3
(stock domain) are separate PRs, NOT touched in this batch. Frontend / public
catalog untouched.

### Completed Tasks (7/7 in Phase 1)

- [x] 1.1 [RED] Rewrote `test_product_domain.py`: id-based eq/hash, Decimal price/cost, slug/model/color invariants
- [x] 1.2 [GREEN] Rewrote `products/domain/product.py`: `@dataclass(eq=False)` `Product{id,slug,name,model,variants}` / `ProductVariant{id,color,price:Decimal,cost:Decimal}`; explicit `__eq__`/`__hash__` on `id`; slug regex+length, Decimal-type/finite/`>=0`/scale-2 checks
- [x] 1.3 [RED] Rewrote `test_register_product_use_case.py` for async `execute` + `get_by_slug`/`get_by_id`
- [x] 1.4 [GREEN] Made `products/application/repository.py` async: `add`/`get_by_id`/`get_by_slug`/`list_all`, dropped `get_by_name`
- [x] 1.5 [GREEN] Created `products/application/exceptions.py`: `DuplicateProductSlugError`
- [x] 1.6 [GREEN] Updated `register_product.py`: async `execute`, removed the `get_by_slug` pre-check (duplicate detection now solely via `repository.add` raising `DuplicateProductSlugError`)
- [x] 1.7 [GREEN] Updated `in_memory_product_repository.py`: async, id-keyed dict + slug index, raises `DuplicateProductSlugError` on slug collision

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/src/gcell/products/domain/product.py` | Modified | `Product{id,slug,name,model,variants}`, `ProductVariant{id,color,price:Decimal,cost:Decimal}`; `eq=False` + explicit id-based `__eq__`/`__hash__`; slug regex+length; money validation (Decimal type, finite, non-negative, scale<=2) |
| `backend/src/gcell/products/application/repository.py` | Modified | `ProductRepository` Protocol fully async; `get_by_name` replaced by `get_by_id`+`get_by_slug` |
| `backend/src/gcell/products/application/exceptions.py` | Created | `DuplicateProductSlugError(slug)` |
| `backend/src/gcell/products/application/register_product.py` | Modified | `execute` is now `async`; pre-check removed, relies on `repository.add` |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Modified | Async; `dict[UUID, Product]` + `dict[str, UUID]` slug index; raises `DuplicateProductSlugError` |
| `backend/tests/unit/products/test_product_domain.py` | Modified | New shape fixtures (`id`, `color`, `Decimal` price/cost, `slug`/`model`); 17 tests covering id-equality, slug format/length, money invariants (type/finite/non-negative/scale) |
| `backend/tests/unit/products/test_register_product_use_case.py` | Modified | Async tests; `get_by_slug`/`get_by_id`; `DuplicateProductSlugError` on slug collision; zero-variant registration |
| `openspec/changes/products-postgres-adapter/tasks.md` | Modified | Phase 1 tasks 1.1-1.7 marked `[x]` |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1/1.2 | `backend/tests/unit/products/test_product_domain.py` | Unit | ✅ 9/9 (baseline full suite) | ✅ Written — 15/17 failed against old `product.py` shape | ✅ 17/17 passed after rewrite | ✅ id-equality (2 cases), slug format/length (3 cases), money type/finite/negative/scale (6 cases) | ✅ Clean — shared `_validate_money` helper avoids duplicating 4 checks across price/cost |
| 1.3-1.7 | `backend/tests/unit/products/test_register_product_use_case.py` | Unit | ✅ 17/17 (post 1.1/1.2) | ✅ Written — collection error (`ModuleNotFoundError: gcell.products.application.exceptions`) against old sync/`get_by_name` shape | ✅ 5/5 passed after `exceptions.py`, async `repository.py`, async `register_product.py`, async `in_memory_product_repository.py` | ✅ duplicate-slug rejection, zero-variant registration, get_by_id round-trip, get_by_slug unknown->None | ✅ Clean — no dead code, docstrings note the design rationale (TOCTOU avoidance) |

### Test Summary
- **Total tests written/updated**: 22 (17 domain + 5 use-case/repository)
- **Total tests passing**: 24/24 full backend suite (`pytest backend/tests -q`)
- **Layers used**: Unit (22 in products), plus 2 pre-existing (health API, architecture boundary) unaffected
- **Approval tests**: None — no refactoring-only tasks in this batch, only spec-driven behavior changes
- **Pure functions created**: `_validate_money(field_name, value)` in `product.py`

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/unit/products -q` -> `22 passed` |
| Runtime harness command/scenario and exact result | N/A — pure Python domain + in-memory adapter, no DB boundary in this PR |
| Rollback boundary | Revert `backend/src/gcell/products/domain/product.py`, `backend/src/gcell/products/application/{repository.py,register_product.py,exceptions.py}`, `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`, `backend/tests/unit/products/*.py` |

Also ran full suite: `uv run --project backend pytest backend/tests -q` -> `24 passed` (includes `test_health.py` and `test_domain_boundary.py`, both untouched and green — `products/domain/product.py` still imports only `re`/`dataclasses`/`decimal`/`uuid`, stdlib only).
`ruff check backend/src/gcell/products backend/tests/unit/products` -> `All checks passed!`

### Deviations from Design
None — implementation matches `design.md`'s "identity, equality, and money invariants" and "duplicate slug via constraint translation" decisions exactly, scoped to the in-memory adapter (Postgres constraint translation is PR2's job per the task split).

One spec/design tension resolved in favor of design (authoritative for HOW): the spec's Requirement text says `ProductVariant` should carry "a reference to its parent product's id," but design's exact `Interfaces / Contracts` section states "`ProductVariant` carries no `product_id`: the adapter derives it from the root" — followed design, since PR2's Postgres adapter is the layer that owns the `product_id` foreign key column, not the domain model.

### Issues Found
None.

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR1 of 3)
- Current work unit: Work Unit 1 — "Domain realignment: id/slug/model/Decimal on Product+Variant, async in-memory port"
- Boundary: starts from `main` (post `supabase-schema` archive), ends at Phase 1 tasks 1.1-1.7 complete — Phase 2 (Postgres adapter, `asyncpg`, `shared/infrastructure`) and Phase 3 (stock domain) are separate PRs not started
- Estimated review budget impact: within the "Domain realignment" work unit's forecasted line count; no DB dependency added in this slice

### Remaining Tasks (Phase 2 and Phase 3, separate PRs — not this batch)
- [ ] 2.1-2.9 Products Postgres Adapter (PR2)
- [ ] 3.1-3.11 Stock Domain (PR3)
- [ ] 4.1-4.3 Verification (after PR2/PR3 land)

### Status
7/7 Phase 1 tasks complete. Ready for sdd-verify on this PR1 slice.
