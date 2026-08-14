# Tasks: Admin Product Images

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2880 (7 slices, 330-520 each) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1→PR2→PR3→PR4→PR5→PR6→PR7 (stacked) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Domain: `ProductImage`, path builder, exceptions | PR1 | `pytest backend/tests/unit/domain/test_product_image.py` | N/A — pure unit | Revert 3 new/mod files, no dependents yet |
| 2 | Persistence: port + Postgres/in-memory adapters | PR2 | `pytest backend/tests/integration/test_product_image_repository.py` | Local Supabase Postgres | Revert adapters/port, unused until PR4 |
| 3 | Storage/normalizer ports, Pillow/httpx, config | PR3 | `pytest backend/tests/unit/infrastructure/test_pillow_image_normalizer.py` | N/A — mocked httpx | Revert deps + adapters, unused until PR4/PR5 |
| 4 | Upload/delete/reorder use cases | PR4 | `pytest backend/tests/unit/application/test_*_product_image.py` | N/A — fakes/spies | Revert use cases, unused until PR5 |
| 5 | `/admin` multipart routes | PR5 | `pytest backend/tests/integration/api/test_admin_images.py` | `uvicorn` + local Supabase | Revert 4 routes in `admin.py`, unreachable |
| 6 | Relay + Server Actions | PR6 | `pnpm test backend-fetch.test.ts` | N/A — mocked fetch | Revert relay branch + actions, unused until PR7 |
| 7 | Image manager UI | PR7 | Manual: upload/reorder/delete via `/admin/products/[id]` | Dev server + local Supabase, real upload | Revert UI files, feature entry point removed |

## Phase 1: Domain (PR1, ~380)
- [x] 1.1 RED: `product_image.py` tests — storage_path shape/uniqueness/hero prefix, unslugifiable colour→`variant`, blank path & negative sort_order rejected (spec: admin-product-images "Hero Assignment"; product-media-storage "Storage Path")
- [x] 1.2 GREEN: create `products/domain/product_image.py` (`ProductImage`, `MAX_UPLOAD_BYTES`, `ALLOWED_UPLOAD_MIMES`) + `products/application/image_path.py` (`build_storage_path`)
- [x] 1.3 Add `ImageNotFoundError`, `UnsupportedImageError`, `ImageTooLargeError` to `products/application/exceptions.py`

## Phase 2: Persistence (PR2, ~480)
- [x] 2.1 RED: db integration — hero insert (NULL `variant_id`), composite FK violation, `list_for_product` hides soft-deleted-variant images, `reorder` writes 0..n-1 atomically (spec: product-persistence)
- [x] 2.2 GREEN: `products/application/image_repository.py` port + `postgres_product_image_repository.py`
- [x] 2.3 GREEN: `in_memory_product_image_repository.py`; add adapter-parity test (same ops → same observable state)

## Phase 3: Storage/Normalizer (PR3, ~520)
- [x] 3.1 RED: normalizer guardrail suite — decode bomb, spoofed mime, animated webp, CMYK, EXIF strip, oversized (pre-decode), non-image bytes, truncated, 4000px→≤1600px webp output (spec: product-media-storage "Normalized")
- [x] 3.2 GREEN: `shared/application/{object_storage,image_normalizer}.py` ports; `shared/infrastructure/pillow_image_normalizer.py`; ban `PIL` in `tests/architecture/test_domain_boundary.py`
- [x] 3.3 RED: `require_storage` returns 503 when Supabase config unset (spec: product-media-storage "Missing service-role")
- [x] 3.4 GREEN: `shared/infrastructure/supabase_storage.py` (httpx adapter); `config.py` (`supabase_url`, `supabase_service_role_key`); `dependencies.py` `require_storage`; add pillow/python-multipart/httpx to `pyproject.toml` runtime deps + `.env.example`

## Phase 4: Use Cases (PR4, ~420)
- [ ] 4.1 RED: upload — DB insert failure triggers exactly one compensating `delete(path)` + re-raise; foreign `variant_id` → not-found before any storage call, spy asserts zero calls (spec: admin-product-images "Compensation", "Ownership")
- [ ] 4.2 GREEN: `products/application/upload_product_image.py`
- [ ] 4.3 RED: delete — storage delete raising on removal still returns success, row deleted (spec: "Delete Is Hard")
- [ ] 4.4 GREEN: `products/application/delete_product_image.py`
- [ ] 4.5 RED: reorder — foreign image id → not-found, zero writes; list missing a product's own image id → not-found, zero writes (spec: "Reorder Replaces")
- [ ] 4.6 GREEN: `products/application/reorder_product_image.py`

## Phase 5: Admin Routes (PR5, ~380)
- [x] 5.1 Reconcile `specs/admin-api-access/spec.md` endpoint list with `design.md` Decisions 6/7 (single `PUT .../images/order`, no separate replace endpoint) — DONE, orchestrator rewrote the spec requirement directly (GET/POST/DELETE/PUT only, no replace route)
- [ ] 5.2 RED: api integration — 4 routes 401 with repo+storage spy (zero calls); 503 when storage unset; 422 for text-as-file; 404 cross-product `image_id` (spec: admin-api-access; admin-product-images "Authorization")
- [ ] 5.3 GREEN: add `GET/POST/DELETE/PUT` image routes to `api/admin.py` calling the 4 use cases; extend `_execute_or_raise` with 502 `ObjectStorageError`

## Phase 6: Relay + Server Actions (PR6, ~330)
- [ ] 6.1 RED: `adminBackendFetch` with `FormData` sets no `Content-Type`, skips `JSON.stringify`; existing JSON callers' request shape unchanged (spec: admin-product-images)
- [ ] 6.2 GREEN: `FormData` branch in `frontend/src/lib/admin/backend-fetch.ts`
- [ ] 6.3 RED: Server Action relays `File` without buffering
- [ ] 6.4 GREEN: upload/delete/reorder Server Actions in `frontend/src/app/(admin)/admin/products/actions.ts`

## Phase 7: Image Manager UI (PR7, ~370)
- [ ] 7.1 GREEN: `frontend/src/app/(admin)/admin/products/image-manager.tsx` — file input, hero/variant assignment, thumbnails, delete, reorder, actionable validation-error display (spec: "Validation Failures Surface Actionable Feedback")
- [ ] 7.2 GREEN: wire manager into `frontend/src/app/(admin)/admin/products/[id]/page.tsx`
- [ ] 7.3 Verify existing public-catalog, admin-auth, admin-CRUD suites pass unmodified; manual upload→admin-list→public-catalog check
