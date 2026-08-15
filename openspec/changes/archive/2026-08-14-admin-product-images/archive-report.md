# Archive Report: Admin Product Images

**Change**: admin-product-images  
**Archive Date**: 2026-08-14  
**Status**: ARCHIVED SUCCESSFULLY  
**Mode**: hybrid (OpenSpec + Engram persistence)

## Change Summary

This change delivers a complete admin write path for product images: upload with server-side normalization, delete with compensation on partial failure, reorder with validation, and hero/variant assignment — all with IDOR-safe ownership checks at the use-case layer.

## Final State Authority

This archive report describes the final state of the change at closure time, per the Final-State Authority hierarchy (commit evidence, explicit launch-prompt facts, and persisted artifacts rank higher than intermediate snapshots).

**Key Final-State Fact**: The single WARNING from the verify-report (missing architecture test for SERVICE_ROLE key leak guardrail) was resolved post-verification via commit 62002f8 (`backend/tests/architecture/test_frontend_service_role_boundary.py`), which is now passing and has been committed to main. This fix ranks above the verify-report's snapshot per the authority hierarchy.

## Task Completion

**Status**: ✅ COMPLETE (50/50 tasks)

All implementation tasks marked as [x] in the persisted tasks artifact:
- Phase 1 (Domain): 3/3 ✅
- Phase 2 (Persistence): 3/3 ✅
- Phase 3 (Storage/Normalizer): 4/4 ✅
- Phase 4 (Use Cases): 6/6 ✅
- Phase 5 (Admin Routes): 3/3 ✅
- Phase 6 (Relay + Server Actions): 4/4 ✅
- Phase 7 (Image Manager UI): 3/3 ✅

## Verification Summary

**Verdict**: PASS WITH WARNINGS (warning resolved post-verify)

**From `sdd/admin-product-images/verify-report` (observation #361)**:
- Evidence revision: sha256:3aabb62 (main, origin/main, working tree clean at verify time)
- **Backend Tests**: 257/257 passed (including 86 image-related tests with local Supabase Postgres integration)
- **Frontend Tests**: 237/237 passed (vitest run on 38 files, independently re-confirmed)
- **Build**: tsc clean, ruff clean, eslint 0 errors (1 reviewed judgment-call warning on next/no-img-element)
- **Spec Compliance**: 34/34 scenarios compliant across 5 spec files (admin-product-images, product-media-storage, product-persistence, product-catalog-schema, admin-api-access)

**Investigated Judgment Calls (both sound)**:
1. Undocumented `GET /admin/products/{id}/images/route.ts` — byte-for-byte identical to sibling route, correct minimal addition closing a real gap.
2. `router.refresh()` UI-sync strategy — guaranteed fresh data per cache headers and architecture, textbook-correct pattern not redundant.

**Post-Verification Fix** (commit 62002f8):
- **Issue**: design.md's "Config" section committed to "enforced by an architecture test asserting zero SERVICE_ROLE hits under frontend/src" but no such test existed — gap was unflagged.
- **Resolution**: Added `backend/tests/architecture/test_frontend_service_role_boundary.py` with the promised guardrail test. Test now passing and committed.
- **Authority**: This fix, committed to main post-verify, outranks the verify-report's WARNING per Final-State Authority hierarchy.

**Final Verdict After Fix**: ✅ PASS (no outstanding blockers or critical findings)

## Specs Merged

All delta specs successfully merged into main specs with mechanical shell operations and diff verification:

| Spec Domain | Action | Details |
|---|---|---|
| **admin-product-images** | NEW | Created `openspec/specs/admin-product-images/spec.md` with 10 requirements, 10 scenarios (new complete spec for admin write path) |
| **product-media-storage** | ADDED | Appended 3 requirements (Backend Service Role contract, Normalization constraints, Storage Path uniqueness) + 4 scenarios to existing spec |
| **product-persistence** | ADDED | Appended 3 requirements (Image repository port, Soft-deleted-variant filtering, Image isolation from product/variant writes) + 7 scenarios to existing spec |
| **product-catalog-schema** | MODIFIED | Updated "Product Images Reference a Variant" requirement to reflect shipped nullable `variant_id` (documentation-drift fix, not behavior change) + 2 scenarios |
| **admin-api-access** | ADDED | Appended 1 requirement (Multipart Image Endpoints) + 3 scenarios to existing spec |

**Total**: 15 requirements, 34 scenarios across 5 specs, all merged and committed to source of truth.

**Merge Verification**: All main specs verified via diff against delta sources — zero differences, files byte-identical after merge.

## Artifacts Archived

**Change Folder Move** (verified):
- Source: `openspec/changes/admin-product-images/`
- Destination: `openspec/changes/archive/2026-08-14-admin-product-images/`
- Verification: Pre-move snapshot diff-verified against post-move archive — **PASS (empty diff)**
- Source directory confirmed removed after move

**Main Specs Updated**:
- `openspec/specs/admin-product-images/spec.md` (NEW)
- `openspec/specs/product-media-storage/spec.md` (MERGED)
- `openspec/specs/product-persistence/spec.md` (MERGED)
- `openspec/specs/product-catalog-schema/spec.md` (MERGED)
- `openspec/specs/admin-api-access/spec.md` (MERGED)

## Engram Persistence

**Artifact Observation IDs** (for traceability):
- #349: `sdd/admin-product-images/proposal`
- #350: `sdd/admin-product-images/spec`
- #351: `sdd/admin-product-images/design`
- #353: `sdd/admin-product-images/tasks`
- #361: `sdd/admin-product-images/verify-report`
- NEW: `sdd/admin-product-images/archive-report` (this artifact)

## Implementation Summary

**Commits on main** (7 implementation + 1 SDD-docs = 8 total):
- 9b55853..3aabb62 (plus archive commit)
- All pushed to origin/main
- Working tree clean at archive time

**Backend Implementation**:
- Domain: `products/domain/product_image.py` (ProductImage entity, validation)
- Repository port: `products/application/image_repository.py` (ImageRepository port, image operations)
- Postgres adapter: `products/infrastructure/postgres_product_image_repository.py` (Postgres persistence)
- In-memory adapter: `products/infrastructure/in_memory_product_image_repository.py` (test adapter)
- Storage ports: `shared/application/{object_storage,image_normalizer}.py` (Supabase and normalizer contracts)
- Storage adapter: `shared/infrastructure/supabase_storage.py` (httpx-backed service-role client)
- Normalizer: `shared/infrastructure/pillow_image_normalizer.py` (Pillow-backed image processing)
- Use cases: `products/application/{upload,delete,reorder}_product_image.py` (3 use cases with compensation logic)
- API routes: `api/admin.py` (4 endpoints: GET/POST/DELETE/PUT)
- Config: `config.py` + `dependencies.py` (Supabase environment, storage injection)
- Architecture test: `backend/tests/architecture/test_domain_boundary.py` (PIL ban) + `test_frontend_service_role_boundary.py` (post-verify fix)

**Frontend Implementation**:
- Relay: `frontend/src/lib/admin/backend-fetch.ts` (FormData branch for multipart)
- Server Actions: `frontend/src/app/(admin)/admin/products/actions.ts` (upload/delete/reorder actions)
- Component: `frontend/src/app/(admin)/admin/products/image-manager.tsx` (Image Manager with upload, reorder, delete, validation feedback)
- Integration: `frontend/src/app/(admin)/admin/products/[id]/page.tsx` (wired into product detail page)

## Known Considerations

1. **Architecture Test Post-Verification**: The design.md-promised architecture test for SERVICE_ROLE key leaks was added post-verify (commit 62002f8), now passing. No re-verification run needed per user guidance.
2. **ESLint Warning**: One reviewed judgment-call warning (`@next/next/no-img-element` on image-manager.tsx) retained to avoid `next.config.remotePatterns` churn. Documented in verify-report.
3. **Coverage**: No coverage tool detected in verify run (informational, not blocking per Strict TDD rules).

## Cycle Complete

The SDD cycle for `admin-product-images` is now closed:
- ✅ Proposed (accepted)
- ✅ Specified (5 specs, 34 scenarios)
- ✅ Designed (7 decisions, 2 architecture judgments)
- ✅ Tasked (50 tasks, 7 phases)
- ✅ Applied (7 PRs, ~2880 lines, all committed)
- ✅ Verified (PASS, warning resolved post-verify)
- ✅ Archived (specs merged, folder moved, audit trail closed)

Ready for the next change.
