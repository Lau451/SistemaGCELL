# Proposal: Admin Product Images

## Intent

`product_images` (nullable `variant_id`), the `product-photos` bucket, and the full public read path (hero fallback + per-variant gallery) already ship and are stable. `admin-product-crud` deferred upload. Today an admin cannot attach a photo at all — catalog rows show the `ImageOff` placeholder unless rows are seeded by hand. This change closes the admin **write** path only.

## Locked Decisions (question round — final, not reopened)

1. **Backend proxy transport**: Server Action → FastAPI (multipart) → Storage via `service_role` → `product_images` row. No service-role secret in Next.js; FastAPI stays sole write authority.
2. **Hard delete**: delete/replace removes DB row *and* Storage object. No soft-delete — images carry no order-integrity concern.
3. **Image processing IS in scope**: resize/compress on upload. Net-new backend dependency (Pillow) plus real processing logic land here; no such tooling exists in the repo today.
4. **Multiple images per variant, no cap** (`sort_order` and the gallery already support it).

## Scope

### In Scope
- Image port + upload/delete/reorder use cases with use-case-layer ownership checks (IDOR guard); both adapters.
- Server-side normalization to bucket-legal jpeg/png/webp under 5MiB.
- Backend Storage client + `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` config (neither exists today).
- Multipart endpoints on the existing `verify_admin_jwt`-gated `/admin` router.
- `adminBackendFetch` multipart path (hard-codes `JSON.stringify` + `application/json` today).
- Admin form: file input, hero-vs-variant assignment, thumbnails, delete, reorder — Server Actions only.
- Reconcile `product-catalog-schema` drift: it forbids images with no parent variant; the shipped schema allows hero images.

### Out of Scope
- Any migration or bucket change (both already exist); public read path; Gemini/AI generation; separate thumbnail objects/CDN; bulk drag-drop; image restore.

## Capabilities

### New Capabilities
- `admin-product-images`: admin upload, replace, delete, reorder, hero/variant assignment, validation feedback.

### Modified Capabilities
- `product-media-storage`: backend `service_role` upload/delete contract + normalization guarantees.
- `admin-api-access`: multipart image endpoints in the admin router contract.
- `product-persistence`: `product_images` reaches the port and both adapters.
- `product-catalog-schema`: fix "Product Images Reference a Variant" — NULL `variant_id` is a valid hero image (same drift class as `f073d8c`).

## Approach

Mirror `admin-product-crud`: pure domain, use cases owning authorization, FastAPI the only writer, Server Actions the only frontend write path (no write Route Handlers — Server Actions enforce origin natively). Images become their own port/aggregate rather than a `Product` field, matching how `gcell.stock` stays separate from `gcell.products`. Upload is one transaction-shaped use case — validate → normalize → put object → insert row — with a compensating object delete on insert failure. `storage_path` follows the seed convention plus a uniqueness suffix so re-uploads never collide.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/.../products/domain/` | New | Image value object, mime/size/order rules |
| `backend/.../products/application/` | New/Mod | Image port, use cases, ownership checks |
| `backend/.../products/infrastructure/` | Mod | `product_images` in postgres + in-memory adapters |
| `backend/.../shared/infrastructure/` | New/Mod | Storage adapter, normalizer, Supabase config |
| `backend/.../api/admin.py` | Mod | First `UploadFile` endpoints in the codebase |
| `backend/pyproject.toml`, `.env.example` | Mod | Pillow + service-role secret |
| `frontend/src/lib/admin/backend-fetch.ts` | Mod | Multipart relay alongside JSON |
| `frontend/src/app/(admin)/admin/products/**` | Mod | File input, image manager, Server Actions |
| `openspec/specs/product-catalog-schema/spec.md` | Mod | Drift reconciliation |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Storage/DB divergence (orphans) | High | Compensating delete on insert failure; row first on removal, tolerate object 404 |
| Pillow net-new: decode bombs, EXIF, animated webp, CMYK | Med | Cap decoded pixels, strip EXIF, 422 on unsupported modes |
| Multipart relay weakens CSRF posture | Med | Server Actions only, relay stays server-only |
| Service-role key = new secret surface | Med | Backend-only env var, never `NEXT_PUBLIC_`, absent → 503 |
| Client/bucket validation mismatch (5MiB, 3 mimes) | Med | One domain constant enforced both sides |
| 400-line review budget | High | Expect ~3 slices: port+adapters, API+storage/normalizer, frontend |

## Rollback Plan

No migration, no bucket change: revert the commits and drop the two env vars. Rows and objects written during the trial survive and are harmless — the public read path already tolerates images present or absent. Manual bucket cleanup only if a failed run left orphans.

## Dependencies

- New backend runtime dependency: Pillow.
- New backend secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (local Supabase already emits both).
- No Gemini usage. No Supabase schema/migration impact.

## Success Criteria

- [ ] Admin uploads from the product form; image appears in admin list and public catalog with no manual step.
- [ ] An oversized/4000px source is stored resized and recompressed within bucket limits.
- [ ] A disallowed mime is rejected with a clear message before any Storage write.
- [ ] Hero (no variant) and per-variant images both persist and render via the existing read path.
- [ ] Several images on one variant render in `sort_order`; reorder persists.
- [ ] Deleting an image removes both row and Storage object.
- [ ] Every image endpoint 401s without an admin JWT and never reaches Storage; another product's image id 404s.
- [ ] No service-role key in frontend code or client bundles.
- [ ] `product-catalog-schema` no longer contradicts the nullable-`variant_id` schema.
- [ ] Existing public-catalog, admin-auth, and admin-CRUD tests pass unmodified.
