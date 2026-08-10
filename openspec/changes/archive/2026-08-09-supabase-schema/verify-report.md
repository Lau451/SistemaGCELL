```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:83006b1c199c91d98822a91d0eb3def311963285a96ca5ca91f99b1ca91165cb
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 12/12
scenarios: 19/19
test_command: docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f supabase/tests/rls_checks.sql
test_exit_code: 0
test_output_hash: sha256:99237960b8d2a4fcf6a357d1d4b184755161ea265c381be4d72bbf01932703f5
build_command: npx supabase db reset
build_exit_code: 0
build_output_hash: sha256:a7fd34f85d6cb7e54b5d0d52e0569835ca2e4e4408fa3f9bc81bdebe322c00a1
```

## Verification Report

Change: supabase-schema
Version: N/A (SQL migrations, no semver)
Mode: Strict TDD

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 24 |
| Tasks complete | 24 |
| Tasks incomplete | 0 |

### Build and Tests Execution

Build: PASSED. npx supabase db reset on a fresh empty database applied all 4 migrations plus seed.sql cleanly, no errors:
```text
Resetting local database...
Recreating database...
Initialising schema...
Applying migration 20260810000449_products_catalog.sql...
Applying migration 20260810000453_stock_movements_ledger.sql...
Applying migration 20260810000458_public_catalog_rls.sql...
Applying migration 20260810000502_storage_product_photos.sql...
Seeding data from supabase/seed.sql...
Finished supabase db reset on branch main.
```

Tests: PASSED. 14 of 14 PASS assertions plus the ALL ASSERTIONS PASSED summary line (exit 0), independently re-run against the fresh reset:
```text
docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f supabase/tests/rls_checks.sql
NOTICE:  PASS: anon denied on products (permission denied for table products)
NOTICE:  PASS: anon denied on product_variants (permission denied for table product_variants)
NOTICE:  PASS: anon denied on product_images (permission denied for table product_images)
NOTICE:  PASS: anon denied on stock_movements (permission denied for table stock_movements)
NOTICE:  PASS: catalog_products columns = created_at,description,id,name,slug
NOTICE:  PASS: catalog_variants columns = color,id,in_stock,phone_model,price,product_id
NOTICE:  PASS: catalog_product_images columns = alt_text,id,product_id,sort_order,storage_path,variant_id
NOTICE:  PASS: anon reads catalog_products row (slug=rls-check-product)
NOTICE:  PASS: variant_stock_levels derives 9 from +10,-3,+2
NOTICE:  PASS: catalog_variants.in_stock = true for a positive-stock variant
NOTICE:  PASS: catalog_variants.in_stock = false for a net-zero-movement variant (derived by INSERT only, no UPDATE)
NOTICE:  PASS: UPDATE on stock_movements rejected (stock_movements is append-only: UPDATE is not permitted)
NOTICE:  PASS: DELETE on stock_movements rejected (stock_movements is append-only: DELETE is not permitted)
NOTICE:  PASS: service_role/postgres reads cost from product_variants (cost=6000.00)
NOTICE:  ALL ASSERTIONS PASSED
exit=0
```
Also independently re-run, not just trusted from the prior agent report: npm --prefix frontend test gave 2 test files, 7 of 7 passed. uv run --project backend pytest -q gave 9 of 9 passed, with 1 pre-existing unrelated httpx/starlette deprecation warning.

Coverage: Not applicable. This is a SQL schema and migration change with no coverage tool wired for supabase/.

### Independent Spot-Checks

Run by the verifier directly, beyond rls_checks.sql, via docker exec ... psql and raw HTTP against the local Storage API.

| # | Check | Expected | Actual result |
|---|---|---|---|
| 1 | SET ROLE anon; SELECT cost FROM product_variants; | Denied | ERROR: permission denied for table product_variants |
| 2 | SET ROLE anon; SELECT * FROM catalog_products LIMIT 3; | Succeeds, no cost column | 3 rows returned, columns id,slug,name,description,created_at, no cost |
| 3 | SET ROLE anon; SELECT * FROM catalog_variants LIMIT 3; then SELECT quantity_on_hand FROM variant_stock_levels; | Variants view succeeds with in_stock boolean, no quantity; internal view denied | 3 rows with in_stock true or false matching seed data exactly (negro=true, transparente=false, Galaxy negro=false); variant_stock_levels access gave ERROR: permission denied for view variant_stock_levels |
| 4 | SELECT id, public FROM storage.buckets WHERE id equals product-photos; SELECT policyname, cmd, roles FROM pg_policies WHERE tablename equals objects; then SET ROLE anon; INSERT INTO storage.objects ... | public is true, one anon SELECT policy, anon INSERT denied | public=t; exactly one policy Public read access for product photos (SELECT, anon); anon INSERT gave ERROR: new row violates row-level security policy for table objects |
| 5 | INSERT duplicate slug into products | Rejected | ERROR: duplicate key value violates unique constraint products_slug_key |
| 6 | INSERT product_variants with price -1 | Rejected | ERROR: violates check constraint product_variants_price_nonnegative_check |
| 7 | INSERT product_images referencing a nonexistent variant | Rejected | ERROR: violates foreign key constraint product_images_variant_id_fkey |
| 8 | INSERT products with blank name | Rejected | ERROR: violates check constraint products_name_not_blank_check |
| 9 | Insert product plus variant in a transaction, delete the product, count remaining variants, rollback | 0 orphan variants after cascade delete | orphan_variants = 0 |
| 10 | SET ROLE service_role; full INSERT, SELECT, DELETE on products | Full CRUD succeeds | Insert, read-back, delete all succeeded |
| 11 | SET ROLE service_role; SELECT variant_id, movement_type, quantity_delta, reason FROM stock_movements; | Full ledger history including reason, unmodified | 3 rows returned with intact reason text |
| 12 | Real HTTP POST to storage object endpoint with service_role key, PNG bytes | 200, object created | HTTP 200, Key returned in JSON body |
| 13 | Real HTTP GET to public storage object endpoint, no auth header | 200, object served unauthenticated | HTTP 200 |
| 14 | Real HTTP POST to storage object endpoint with anon key, PNG bytes | Rejected by storage RLS | HTTP 400, error Unauthorized, new row violates row level security policy |

All 14 independent spot-checks matched expectations exactly. Checks 12 through 14 are genuine end-to-end HTTP requests against the local Storage API, not just SQL introspection of storage.buckets and pg_policies, closing a gap left by rls_checks.sql, which does not exercise the Storage HTTP surface at all.

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Product Identity and Slug Uniqueness | Duplicate slug rejected | rls_checks.sql fixture idempotent reuse plus spot-check 5 | COMPLIANT |
| Product Identity and Slug Uniqueness | Blank slug or name rejected | spot-check 8, products_name_not_blank_check | COMPLIANT |
| Product Variants Carry Color and Non-Negative Pricing | Negative price rejected | spot-check 6 | COMPLIANT |
| Product Variants Carry Color and Non-Negative Pricing | Variant deleted when parent product deleted | spot-check 9, 0 orphan variants after cascade | COMPLIANT |
| Product Images Reference a Variant | Image insert without valid variant rejected | spot-check 7 | COMPLIANT |
| Public Catalog Reads Exclude Cost and Raw Rows | anon denied on base products table | rls_checks.sql PASS x4 plus spot-check 1 | COMPLIANT |
| Public Catalog Reads Exclude Cost and Raw Rows | anon reads catalog via public view | rls_checks.sql PASS plus spot-check 2 | COMPLIANT |
| Service Role Has Full Catalog Access | service_role reads cost and writes rows | rls_checks.sql PASS, cost value 6000.00, plus spot-check 10 | COMPLIANT |
| Stock Movements Are Append-Only | Movement insert succeeds | rls_checks.sql fixture inserts plus seed.sql reset-apply | COMPLIANT |
| Stock Movements Are Append-Only | No UPDATE path exists | rls_checks.sql PASS, UPDATE rejected, DELETE rejected, run as connecting superuser not anon | COMPLIANT |
| Current Stock Is Derived, Not Stored | Stock reflects sum of movements | rls_checks.sql PASS, variant_stock_levels derives 9 from 10 minus 3 plus 2 | COMPLIANT |
| Public Visibility Is a Boolean Only | anon sees in_stock, not a count | rls_checks.sql PASS column-list assert plus spot-check 3 | COMPLIANT |
| Public Visibility Is a Boolean Only | anon denied on stock_movements base table | rls_checks.sql PASS plus base-table denial pattern in spot-check 1 | COMPLIANT |
| Service Role Reads Full Movement History | service_role queries movement history | spot-check 11 | COMPLIANT |
| Product Photos Bucket Is Publicly Readable | anon fetches a public photo URL | spot-check 13, real unauthenticated HTTP GET, 200 | COMPLIANT |
| Photo Writes Are Restricted to Service Role | anon upload rejected | spot-check 14, real HTTP POST as anon, 400 with RLS denial | COMPLIANT |
| Photo Writes Are Restricted to Service Role | service_role upload succeeds | spot-check 12, real HTTP POST as service_role, 200 | COMPLIANT |
| Supabase CLI Wiring Without Schema, MODIFIED | Config exists, migrations contain real schema | config.toml plus 4 migration files confirmed present on disk | COMPLIANT |
| Supabase CLI Wiring Without Schema, MODIFIED | Fresh database reset applies all schema cleanly | npx supabase db reset, build evidence above, exit 0 | COMPLIANT |

Compliance summary: 19 of 19 scenarios compliant, 12 of 12 requirements

### Correctness (Static Evidence)

| Requirement domain | Status | Notes |
|---|---|---|
| product-catalog-schema | Implemented | products, product_variants, product_images match design DDL; composite FK product_id plus variant_id correctly forbids cross-product variant images per Decision 10 |
| inventory-schema | Implemented | stock_movements append-only via BEFORE UPDATE OR DELETE trigger, binds even a direct superuser connection per Decision 6, plus restrictive GRANTs; sign-direction CHECK matches design rule: restock and return positive, sale and breakage negative |
| product-media-storage | Implemented | Bucket public is true, single anon SELECT storage policy, zero write policies since service_role bypasses RLS, matches Decision 11 |
| platform-foundation MODIFIED delta | Implemented | Delta correctly retires the no-schema-SQL requirement and asserts real schema now exists; both are true on disk and confirmed by a clean db reset |

### Coherence (Design)

| Decision | Followed | Notes |
|---|---|---|
| 1: Views plus GRANT-on-view-only for public column hiding | Yes | catalog_products, catalog_variants, catalog_product_images; no base-table GRANT to anon |
| 2: security_invoker off, definer views | Yes | All 4 views explicit with security_invoker false |
| 3: movement_type as text plus CHECK, not enum | Yes | stock_movements_movement_type_check |
| 4: Live SUM view, not materialized or trigger counter | Yes | variant_stock_levels, covering index on variant_id including quantity_delta |
| 5: COALESCE quantity_on_hand zero greater than zero for in_stock | Yes | Confirmed correct false-for-no-movements behavior via seed data, Galaxy S24 negro and azul |
| 6: Append-only via GRANT plus trigger, not GRANT alone | Yes | Trigger fires even for the connecting superuser, verified: UPDATE and DELETE rejected without SET ROLE anon |
| 7: ON DELETE RESTRICT on ledger FK | Yes | stock_movements.variant_id references product_variants on delete restrict |
| 8: slug format plus length CHECK | Yes | products_slug_format_check, products_slug_length_check |
| 9: numeric 10,2 for money | Yes | price and cost both numeric 10,2 |
| 10: Composite FK for image ownership, product_id not null, variant_id nullable | Yes, plus one undocumented extra, see WARNING below | Composite FK present and correct; an additional simple column-level FK on variant_id alone also exists, redundant but harmless |
| 11: Storage, zero write policies | Yes | Confirmed only one SELECT policy exists in pg_policies |

### Issues Found

CRITICAL: None

WARNING:
1. apply-progress.md TDD Cycle Evidence table states the GREEN run produced 18 PASS notices, but the actual script produces 14 PASS notices plus one ALL ASSERTIONS PASSED summary line, 15 NOTICE lines total. state.yaml apply_result tdd_evidence field correctly says 15 of 15. This is a documentation inaccuracy in apply-progress.md only; the underlying GREEN evidence itself, exit 0, all assertions genuinely passing, is correct and was independently reproduced twice in this verify pass.
2. supabase/migrations/20260810000449_products_catalog.sql defines product_images.variant_id as a plain uuid column referencing product_variants id, on delete cascade, which creates an implicit simple FK named product_images_variant_id_fkey in addition to the explicit composite FK product_images_variant_fk that design.md Decision 10 documents. The simple FK is redundant, fully subsumed by the composite FK when variant_id is not null, and is not a security or correctness defect, but it is an undocumented deviation not listed in design.md Decision 10's code sample nor in apply-progress.md's Deviations from Design section.

SUGGESTION:
1. The 588-line diff versus the 400-line budget was driven roughly 55 percent by the 324-line rls_checks.sql test script. Already flagged and accepted as a size exception per state.yaml; no further action needed, noted here only for archive-time completeness.
2. Storage bucket public-read behavior, the anon fetches a public photo URL scenario, was previously verified only at the SQL config level by both the apply and orchestrator re-runs. This verify pass closed that gap with a genuine end-to-end HTTP upload as service_role, an unauthenticated fetch as anon, and a rejected anon upload attempt. Worth keeping as a documented pattern for future storage-bucket changes, since rls_checks.sql itself never exercises the Storage HTTP surface.

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | Yes | Found in apply-progress.md, RED, GREEN, REFACTOR table present |
| All tasks have tests | Yes | Single macro RED-GREEN cycle covers all 24 tasks, per design.md Testing Strategy, a schema change rather than per-function TDD |
| RED confirmed, tests exist | Yes | supabase/tests/rls_checks.sql exists, 324 lines, matches apply-progress.md's reported RED authoring |
| GREEN confirmed, tests pass | Yes | Independently re-run twice in this verify pass, after two separate db reset runs, exit 0 both times, all assertions PASS |
| Triangulation adequate | Yes | 14 distinct assertions across 4 requirement domains: RLS denial x4, column-list x3, view-read, stock-sum, in_stock true and false, UPDATE rejected, DELETE rejected, service_role reads cost; no single-assertion coverage for any requirement domain |
| Safety Net for modified files | N slash A, new | All 4 migrations, seed.sql, and rls_checks.sql are newly created files, not modifications; the config.toml modification, storage block, is additive only, verified present |

TDD Compliance: 6 of 6 checks passed

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Schema and Integration, SQL-level RLS plus constraint asserts | 14 assertions | 1, rls_checks.sql | psql via docker exec, no psql binary on host |
| End-to-end, HTTP, storage | 3, verifier spot-checks 12 through 14, not in repo | 0 repo files, ad hoc this verify pass only | curl against local Storage API |
| Unit and Integration, unrelated app regression code | 7 frontend plus 9 backend equals 16 | 2 frontend test files plus backend suite | vitest, pytest |
| Total, repo-committed | 14 | 1 | n/a |

### Changed File Coverage
Coverage analysis skipped, no coverage tool wired for SQL migrations, not applicable to this stack.

### Assertion Quality
Reviewed supabase/tests/rls_checks.sql, 324 lines, for banned patterns: tautologies, orphan empty checks, ghost loops, assertion-without-production-call, smoke-test-only, mock-heavy.

No tautologies found; every DO block queries a real table or view or performs a real DML statement against the actual schema before asserting. No ghost loops; the script contains no FOR or FOREACH over query results, every assertion is a direct scalar check. No assertion-without-production-code-call; every block performs a real SELECT, INSERT, UPDATE, or DELETE against the schema under test. The expect 0 rows or a privilege error pattern for anon-denied checks is intentionally dual-branch, checking both the empty-result and the exception path, not a trivial always-pass, confirmed by re-running and observing the actual permission denied SQLERRM text in NOTICE output, not just an assumed exit code. One minor observation: the four anon-denied checks for products, variants, images, and stock_movements are structurally near-identical, same pattern repeated per table, which is acceptable table-by-table triangulation rather than redundant duplication, since each covers a distinct base table RLS enablement.

Assertion quality: All assertions verify real behavior

### Quality Metrics
Linter: Not available, no SQL linter configured in this repo
Type Checker: Not applicable, SQL migrations have no static type checker

### Verdict
PASS WITH WARNINGS
All 12 requirements and 19 scenarios are genuinely compliant with independently reproduced runtime evidence, including new end-to-end HTTP storage checks beyond the committed test script. Two non-blocking documentation and design-note gaps, the apply-progress PASS-count typo and one undocumented redundant FK, do not affect security or correctness and do not block archive.
