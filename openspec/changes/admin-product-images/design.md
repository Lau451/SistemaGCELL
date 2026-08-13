# Design: Admin Product Images

## Technical Approach

Images become a **separate aggregate with three ports**, not a `Product` field — confirming the
proposal's lean. Persistence (`ProductImageRepository`) lives in `products/application/`; the two
cross-domain capabilities (`ObjectStorage`, `ImageNormalizer`) live in `shared/application/` so their
`shared/infrastructure/` adapters never import from `products/` (wrong dependency direction).
`products/domain/product_image.py` stays pure Python; Pillow and httpx are confined to adapters.
Use cases own authorization (ownership scan on the already-fetched aggregate, never a SQL join),
`/admin` routes call use cases only, Server Actions are the only frontend write path.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|---|---|---|
| 1 | Own aggregate + 3 ports (`ProductImageRepository`, `ObjectStorage`, `ImageNormalizer`) | Field on `Product`/`ProductVariant` | Loading a product would drag image rows into every CRUD read; storage/normalization are cross-domain and must not live under `products/`. Mirrors `gcell.stock`. |
| 2 | `storage_path` = `{product_slug}/{color_slug\|"hero"}-{image_id.hex[:12]}.webp` | Seed's bare `slug/color.ext`; full-UUID filename | Bare form collides on multi-image-per-variant and on delete-then-reupload (CDN caches the old object). Row-id-derived suffix stays traceable and keeps the seed's human-readable bucket listing. Color slug truncated to 40 chars; an unslugifiable color falls back to `variant` (the prefix is cosmetic — the suffix carries uniqueness). |
| 3 | Always re-encode to **WebP q82, long edge ≤ 1600px, downscale only** | Preserve source format; keep original dimensions | Collapses the output matrix to one mime/one extension/one `remotePatterns` entry. 1600px covers the detail gallery (~800 CSS px) at 2× DPR. Bucket already allows `image/webp`. Accepted tradeoff: lossy re-encode of flat-colour PNGs — this catalog stores photos. Alpha preserved (WebP supports it). |
| 4 | Upload: **Storage object first, DB row second, compensating object delete on insert failure** | Row first | Failure asymmetry: a row without an object is a broken `<img>` for every public visitor; an orphan object is invisible. Compensation catches `BaseException` (client-disconnect `CancelledError`) and must never mask the original error. |
| 5 | Delete: **DB row first, then best-effort object delete; port `delete` is idempotent (404 = success)** | Object first; 2-phase | Same asymmetry, inverted. A Storage outage must not block the user-visible contract (row gone). Non-404 storage errors are logged and swallowed; the route still returns 204. |
| 6 | Reorder: dedicated **`PUT /admin/products/{id}/images/order`** with the full ordered id list | Batch `PATCH` of `{id, sort_order}` deltas; folding into `PATCH /admin/products/{id}` | Order is a whole-collection property: the full list makes "is this exactly a permutation of this product's images" one checkable precondition (stale tab → deterministic 404, not a corrupt/gapped order), makes the IDOR guard a set comparison, and is idempotent. Folding into the product `PATCH` would pollute its `extra="forbid"` contract and rewrite image rows on every product save. |
| 7 | **No replace endpoint** — replace = delete + upload composed in the Server Action | `PUT /images/{image_id}` | A replace needs 3-way compensation (put new, update row, delete old) for zero user-visible gain. |
| 8 | `adminBackendFetch` branches on `init.body instanceof FormData` | New function / overload / `formData` field | Purely additive: `body?: unknown` already accepts `FormData`, so every JSON caller is byte-identical. **Must NOT set `Content-Type` for FormData** — a manual header omits `boundary=` and FastAPI's parser fails with a misleading 400. |
| 9 | Thin httpx adapter against the Storage REST API; `httpx` promoted dev→runtime | `supabase-py` / `storage3` | Pulls gotrue/postgrest/realtime for two HTTP calls. Repo posture is thin explicit adapters (hand-rolled Postgres adapter, no ORM). |
| 10 | `PIL` added to `BANNED_MODULES` in `tests/architecture/test_domain_boundary.py` | Leave as-is | Nothing else stops the normalizer drifting into `domain/`. |

### Pillow safety guardrails (all in `shared/infrastructure/pillow_image_normalizer.py`)

| Threat | Guardrail | Failure |
|---|---|---|
| Decode bomb | `Image.MAX_IMAGE_PIXELS = 40_000_000`; **explicit pre-decode check** of `im.size` against 40 MP and 10 000 px/side after lazy `Image.open`, before `load()`/`convert()`/`thumbnail()` — Pillow only *warns* between 1× and 2× the limit | 422 `image_too_large` |
| Spoofed mime | Allowlist the **decoded** `im.format ∈ {JPEG, PNG, WEBP}`; the multipart `content_type` and client filename are never trusted and never reach `storage_path` | 422 `unsupported_image_format` |
| Animated WebP / APNG | `getattr(im, "n_frames", 1) > 1` rejected (silently saving frame 0 is surprising) | 422 `unsupported_animated_image` |
| CMYK / YCbCr / I;16 / F | Mode allowlist `{RGB, RGBA, L, LA, P}`; CMYK→RGB without an ICC profile ships wrong-coloured photos | 422 `unsupported_color_mode` |
| EXIF (GPS/serial) + sideways phone photos | `ImageOps.exif_transpose()` first, then re-encode **without** passing `exif` — orientation corrected, all metadata dropped | — |
| Oversized input | `len(data) > 5 MiB` rejected **before decode**; post-encode size re-asserted | 422 `image_too_large` |
| Non-image bytes | `UnidentifiedImageError` | 422 |
| Truncated file | `ImageFile.LOAD_TRUNCATED_IMAGES` stays `False` | 422 |

## Data Flow

```
                        ┌ 401 (router JWT) ─ 503 (db) ─ 503 (storage) ─┐
Browser ──FormData──► Server Action ──multipart──► POST /admin/products/{id}/images
                       (origin-checked)   adminBackendFetch      │
                                          (no Content-Type)      ▼
                                                    UploadProductImageUseCase
   1 get_by_id → 404 │ 2 variant ∈ product.variants → 404 │ 3 size → 422
   4 normalize → 422 (NO storage/db call yet) │ 5 path │ 6 next_sort_order
   7 ObjectStorage.put ──► Supabase Storage (service_role)
   8 repo.add ──► product_images        ✗ → ObjectStorage.delete(path), re-raise
```

Delete inverts 7/8: `repo.delete` → then best-effort `ObjectStorage.delete` (404 tolerated).

## Interfaces / Contracts

```python
# products/application/image_repository.py
class ProductImageRepository(Protocol):
    async def add(self, image: ProductImage) -> None: ...
    async def get_by_id(self, image_id: UUID) -> ProductImage | None: ...
    async def list_for_product(self, product_id: UUID) -> list[ProductImage]: ...
    async def delete(self, image_id: UUID) -> None: ...          # HARD delete; 0 rows -> ImageNotFoundError
    async def next_sort_order(self, product_id: UUID, variant_id: UUID | None) -> int: ...
    async def reorder(self, product_id: UUID, ordered_image_ids: list[UUID]) -> None: ...

# shared/application/object_storage.py
class ObjectStorage(Protocol):
    async def put(self, path: str, data: bytes, content_type: str) -> None: ...
    async def delete(self, path: str) -> None: ...               # IDEMPOTENT: missing object is success

# shared/application/image_normalizer.py
class ImageNormalizer(Protocol):
    def normalize(self, data: bytes) -> NormalizedImage: ...     # bytes, content_type, width, height
```

`list_for_product` joins `product_variants ... AND deleted_at IS NULL` for non-NULL `variant_id`,
mirroring the read-time soft-delete cascade — otherwise the admin manager shows images the public
gallery no longer renders (the exact divergence class of `f073d8c`).

### Endpoints (existing `verify_admin_jwt`-gated `/admin` router)

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/admin/products/{product_id}/images` | — | 200 `list[AdminProductImageResponse]` |
| POST | `/admin/products/{product_id}/images` | multipart: `file: UploadFile`, `variant_id: UUID\|None = Form(None)`, `alt_text: str\|None = Form(None)` | 201 `AdminProductImageResponse` |
| DELETE | `/admin/products/{product_id}/images/{image_id}` | — | 204 |
| PUT | `/admin/products/{product_id}/images/order` | JSON `{"image_ids": [UUID, ...]}`, `extra="forbid"` | 200 `list[AdminProductImageResponse]` |

Status mapping extends `_execute_or_raise` unchanged: 422 rejected body / domain error, 404
`ImageNotFoundError` (unknown, wrong parent, or foreign id in the order list — never 403), new 502
`ObjectStorageError`. Dependency order stays 401 → `require_db_pool` 503 → `require_storage` 503.

### Config

`shared/infrastructure/config.py` gains `supabase_url()` and `supabase_service_role_key()`, same
`os.environ`-only / returns-`None` shape as `db_url()`/`jwks_url()`. **Backend-only.** The service
role key MUST NEVER acquire a `NEXT_PUBLIC_` twin; enforced by an architecture test asserting zero
`SERVICE_ROLE` hits under `frontend/src`. `require_storage` (mirrors `require_db_pool`) returns 503
`storage_unavailable` when either is unset.

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/products/domain/product_image.py` | Create | `ProductImage`; `MAX_UPLOAD_BYTES`, `ALLOWED_UPLOAD_MIMES`; id-equality like `Product` |
| `backend/src/gcell/products/application/image_repository.py` | Create | Port |
| `backend/src/gcell/products/application/image_path.py` | Create | `build_storage_path` (reuses `slug.slugify`) |
| `backend/src/gcell/products/application/{upload,delete,reorder}_product_image.py` | Create | Use cases + IDOR guard + compensation |
| `backend/src/gcell/products/application/exceptions.py` | Modify | `ImageNotFoundError`, `UnsupportedImageError`, `ImageTooLargeError` |
| `backend/src/gcell/products/infrastructure/{postgres,in_memory}_product_image_repository.py` | Create | Both adapters |
| `backend/src/gcell/shared/application/{object_storage,image_normalizer}.py` | Create | Cross-domain ports |
| `backend/src/gcell/shared/infrastructure/supabase_storage.py` | Create | httpx adapter, `ObjectStorageError` |
| `backend/src/gcell/shared/infrastructure/pillow_image_normalizer.py` | Create | Guardrail table above |
| `backend/src/gcell/shared/infrastructure/{config,dependencies}.py` | Modify | Supabase config + `require_storage` |
| `backend/src/gcell/api/admin.py` | Modify | 4 routes, first `UploadFile` in the repo |
| `backend/pyproject.toml` | Modify | `pillow`, `python-multipart`, `httpx` dev→runtime |
| `backend/tests/architecture/test_domain_boundary.py` | Modify | Ban `PIL` |
| `frontend/src/lib/admin/backend-fetch.ts` | Modify | ~6 lines: FormData branch |
| `frontend/src/app/(admin)/admin/products/{actions.ts,image-manager.tsx,[id]/page.tsx}` | Mod/Create | Upload/delete/reorder actions + manager UI |
| `openspec/specs/product-catalog-schema/spec.md` | Modify | Drift: NULL `variant_id` is a valid hero image |

## Testing Strategy (Strict TDD)

| Layer | Highest-value RED tests |
|---|---|
| Unit — domain | `storage_path` shape/uniqueness/`hero` prefix; unslugifiable colour → `variant`; blank path & negative `sort_order` rejected |
| Unit — normalizer | One test per guardrail row (12 001×12 001 header rejected **without decode**; `.png` bytes renamed `.jpg` still classified by decoded format; animated WebP 422; CMYK 422; EXIF GPS absent from output; 4000px → ≤1600px; output is `image/webp`) |
| Unit — use case | Fake storage raising on `put`/`add`: **DB insert failure triggers exactly one compensating `delete(path)` and re-raises the original**; storage `delete` raising on removal still returns success and leaves the row deleted; foreign `variant_id` → `VariantNotFoundError` **before** any storage call (spy asserts zero calls); reorder with a foreign image id → `ImageNotFoundError`, zero writes |
| Integration — db | Hero image (NULL `variant_id`) inserts; image on another product's variant violates the composite FK; `list_for_product` hides images of a soft-deleted variant; `reorder` writes 0..n-1 in one transaction |
| Integration — api | Each of the 4 routes 401s with a repository+storage spy proving zero calls; 503 with storage unset; 422 for a text file posted as `file`; 404 cross-product `image_id` |
| Unit — frontend | `adminBackendFetch` with `FormData` sets **no** `Content-Type` and does not `JSON.stringify`; existing JSON callers' request shape unchanged; Server Action relays the `File` without buffering |

Existing catalog, admin-auth and admin-CRUD suites must pass **unmodified**.

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths / executable-file classification | **Applicable** — user-supplied file crosses a trust boundary | Client filename and `content_type` never reach `storage_path`; extension is always `.webp` from the server; classification is by decoded `im.format` allowlist; bucket `allowed_mime_types` is a second gate | Renamed-extension test; polyglot/text-as-image → 422; assert stored path derives only from slug + row id |
| Git repository selection | N/A — no VCS automation | — | — |
| Commit state | N/A — no VCS automation | — | — |
| Push state | N/A — no VCS automation | — | — |
| PR commands | N/A — no VCS automation | — | — |

No shell, subprocess, or process-integration boundary: Pillow and httpx are in-process libraries.

## Migration / Rollout

No migration, no bucket change — `product_images`, the composite FK, and `product-photos` (5 MiB,
jpeg/png/webp) already ship. Rollout = set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`; absent →
503, feature simply unavailable. Rollback = revert commits, drop the two env vars; written rows and
objects are harmless (the public read path already tolerates images present or absent).

## Open Questions

- [ ] `python-multipart` is a net-new **runtime** dependency (FastAPI does not ship it; `UploadFile`/`Form` require it) that the proposal's Dependencies section names nowhere — it lists only Pillow. `httpx` also moves dev→runtime. Spec/tasks must carry all three.
- [ ] Images of a **soft-deleted variant** are never cascaded: the composite FK's `ON DELETE CASCADE` never fires because variants are only ever soft-deleted, so the row and its Storage object persist forever. This design hides them at read time; no purge is in scope. This MUST become an explicit spec requirement or it is an undocumented divergence — the exact failure class of `f073d8c`.
- [ ] Decision 7 (no replace endpoint) needs a spec sentence stating replace is a delete+upload composition, since proposal decision 2 says "delete/replace".
- [ ] Reorder scopes the whole product's image list (one drag list); per-group relative order is what the gallery renders. Spec must state this so a per-variant reorder contract is not assumed.
