# Design: Content + AI Domains (Gemini-Assisted Product Copy)

## Technical Approach

Four seams, all additive, ordered so the first two carry **zero** Gemini
dependency (proposal's Delivery Forecast slices 1–2):

1. **Schema + two text fields end-to-end.** One migration (D3):
   `products.short_description` plus a `create or replace view
   catalog_products` that appends it (DD7). `Product` gains two optional
   fields; both repository adapters, `create`/`update`, the admin API, the
   admin form, and the pinned frontend column allowlist follow.
2. **Alt-text update path.** A new `PATCH
   /admin/products/{product_id}/images/{image_id}` (DD3) behind a new
   `ProductImageRepository.update_alt_text`, reusing the existing
   use-case-layer ownership guard verbatim (404, never 403).
3. **`ai` domain.** A generic `ContentGenerator` port (`ai/application/`) +
   a thin `httpx` adapter (`ai/infrastructure/`) that speaks Gemini's REST
   `:generateContent` in **structured-JSON mode** (DD6), mirroring the
   `ObjectStorage`/`SupabaseStorage` precedent byte for byte —
   constructor-injected `transport` so every test runs under
   `httpx.MockTransport` with zero live network (D8, DD4). `GEMINI_API_KEY`
   in `config.py`, `require_gemini` 503 guard in `dependencies.py`, exactly
   mirroring `require_storage` (D7).
4. **`content` domain.** Two use cases behind two narrow read-only ports
   declared in `content/application/` (DD2). Neither touches a repository
   write method — D5's no-write-side-effect rule becomes **structural**,
   not a reviewer duty.

`shared/application/object_storage.py` gains a `get` method (DD1) so the
alt-text flow reads bytes through the port it already owns.
`backend/tests/architecture/test_domain_dependencies.py` is new (DD5) and
makes D9's directionality rule executable for the first time.

## Architecture Decisions

### DD1: Add `ObjectStorage.get()`; never hand Gemini a public object URL

| Option | Tradeoff | Decision |
|---|---|---|
| (b) Pass the `product-photos` public URL to Gemini | Zero bandwidth on our side, but the URL is unreachable from Google's network in **every** non-production environment | **Rejected** |
| **(a) `get(path) -> StoredObject` on the port + `SupabaseStorage`** | One extra ~200 KB download per generate click | **Chosen** |

Four verified reasons, strongest first:

1. **It does not work outside production.** `supabase_url()` is
   `http://127.0.0.1:54321` locally (see `test_supabase_storage.py`,
   `storage-url.test.ts`, and CI's placeholder in the archived
   `ci-and-rls-tests` workflow). A public object URL built from it is a
   loopback address Google cannot fetch, so alt-text generation would be
   unrunnable and unverifiable by the developer who writes it.
2. **The Gemini REST API does not fetch arbitrary URLs.** Image input is
   either `inline_data` (base64 bytes) or `file_data.file_uri` pointing at
   a **Files API** object. Option (b) therefore does not remove the byte
   fetch — it adds a second upload plus a Google-hosted temporary copy.
   *(Apply-time verification task: confirm against current Gemini docs
   before writing the adapter; the decision holds either way on reasons
   1/3/4.)*
3. **Testability.** `get` behind the existing port is faked in three lines
   for the use-case test and covered by `httpx.MockTransport` for the
   adapter — the exact pattern `test_supabase_storage.py` already uses.
   Option (b) leaks Supabase's public-URL convention into `content/`.
4. **Coupling and blast radius.** (b) makes generation silently break the
   day the bucket stops being public, and hands a third party a durable,
   re-fetchable object URL. (a) sends bytes for exactly one call.

`get` returns a `StoredObject(data, content_type)` rather than bare bytes:
`inline_data.mime_type` must be correct, and the adapter already has the
authoritative value in the response's `Content-Type` header. Symmetric with
`NormalizedImage` in `shared/application/image_normalizer.py`.

### DD2: Narrow read-only ports in `content/application/`, not `ProductRepository` reuse

**The existing precedent is the opposite**, and it was checked: every
`stock -> products` seam (`record_variant_stock_movement.py`,
`list_catalog_stock_levels.py`, `list_variant_stock_movements.py`,
`create_stocked_product.py`) imports `products.application.repository.
ProductRepository` directly. This design deviates deliberately, for two
reasons that do not apply to `stock`:

| Option | Tradeoff | Decision |
|---|---|---|
| Call products' **use cases** | There is no read use case to call — `get_by_id` lives on the repository — and D5 forbids the write ones | Rejected |
| Depend on **`ProductRepository`** (stock's precedent) | Free, familiar; but hands `content` `add`/`update`/`soft_delete` **and** `ProductVariant.price`/`cost` | Rejected |
| **Narrow ports + a products-backed adapter** | One `Protocol` + one ~20-line adapter + two DTOs | **Chosen** |

- **D5 becomes structural.** The proposal's own risk row says "Reviewer must
  confirm no generate handler touches a repository." A port with no write
  method makes that unfalsifiable-by-construction instead of a review duty.
- **OQ2 becomes structural.** "No price in the prompt" is a user-confirmed
  hard constraint. A DTO with no price field cannot leak one; a `Product`
  carrying `ProductVariant.price` makes OQ2 a convention one refactor away
  from breaking. This is the same "make it unreachable, not forbidden"
  posture the catalog design already uses ("cost / exact stock
  unreachable").

The adapter lives in `content/infrastructure/`, delegates to
`ProductRepository`/`ProductImageRepository` (never SQL — D4 satisfied
literally), and is injected at the composition root in `api/admin.py`.

**Ownership without a duplicated predicate:** `photo_context` resolves the
image via `ProductImageRepository.list_for_product(product_id)` and picks
`image_id` out of that list. Ownership is then a *consequence* of a
product-scoped query rather than a re-implementation of
`DeleteProductImageUseCase`'s `image.product_id != product_id` check — and
it inherits the soft-deleted-variant hiding for free. Absent → `None` →
404 `not_found`.

### DD3: New `PATCH /admin/products/{product_id}/images/{image_id}`

| Option | Tradeoff | Decision |
|---|---|---|
| Extend `PUT .../images/order` | Whole-list reorder semantics; would force alt text into every reorder call | Rejected |
| Nest `alt_text` in the product `PATCH` body | Images are a separate aggregate; needs a nested list and reopens the product write model | Rejected |
| `PUT .../images/{image_id}` (full replace) | Implies replacing `storage_path`/`sort_order`, which this route must never do | Rejected |
| **`PATCH .../images/{image_id}`, body `{alt_text}`** | One new route, one new port method, one new use case | **Chosen** |

Mirrors the existing `PATCH /admin/products/{product_id}` partial-update
precedent. Guards, in the exact order `admin.py` already documents:
router-level `verify_admin_jwt` (401) → `require_db_pool` (503). **No
`require_storage`** — no Storage object is touched, the same reasoning
already written for `GET`/reorder in `admin.py`'s images section.

`UpdateProductImageAltTextUseCase` lives in `products/application/` (D4)
and reproduces the guard verbatim: `get_by_id` → `image is None or
image.product_id != product_id` → `ImageNotFoundError` → 404 `not_found`
via the existing `_execute_or_raise`. `alt_text` is a **required key**
(`str | None`, no default), so a body missing it is 422 and an explicit
`null`/blank-after-strip clears the column — the only way to undo bad alt
text. Non-blank values are stored stripped.

### DD4: Failure, timeout, validation, and pinning policy

Mirrors the `ObjectStorage` precedent pair exactly: **503 when
unconfigured, 502 when the call fails.**

| Concern | Decision | Rationale |
|---|---|---|
| Unconfigured | `require_gemini()` → `503 gemini_unavailable`, scoped to the two generate routes only | Byte-for-byte `require_storage` (D7). App boots, `/health`, public catalog, and every existing admin route are untouched |
| Transport/status/timeout | `GenerationError` → `502 generation_failed` | `ObjectStorageError` → 502 precedent |
| Safety block / no usable candidate | `GenerationRefusedError` → `502`, detail `generation_refused` | Not a rejected body (422 would be wrong — the request was valid); the admin's remedy is identical to a transport failure. Distinct `detail`, same status, so the UI can say "the model declined" |
| Timeout | `httpx.Timeout(30.0, connect=5.0)` | The admin is blocked on a Server Action; Fly/Vercel request budgets. `httpx.TimeoutException` → `GenerationError` |
| **Retry** | **None.** 429/5xx map straight to 502 | (a) D6 cost guardrail — an automatic retry silently doubles a paid call per click; (b) generation is non-idempotent in output *and* cost; (c) the admin already has a free, explicit retry (click again); (d) no retry loop = no sleep control needed, so mock-transport tests stay deterministic |
| Model pinning | `GEMINI_MODEL` module constant `"gemini-2.5-flash"`, overridable by an optional `GEMINI_MODEL` env var; API version pinned in the base URL (`/v1beta`) | Never a floating alias (`*-latest`): a silent model swap changes output shape and cost. The env override makes a deprecation a config change, not a deploy |
| Draft caps | blurb **160**, body **1200**, alt text **125** chars | 160 = a card blurb under a fixed-height grid tile (and the conventional meta-description budget if reused); 1200 ≈ 200 words, bounded paid output; 125 = the standard screen-reader alt-text guidance |
| Over-cap output | **Trim at the last word boundary within the cap**, return the draft | D5 makes every draft human-reviewed and editable *before* save. Discarding an otherwise-good body over 20 excess characters wastes a paid call. Residual: a trimmed blurb can end mid-sentence — visible and editable, which is the review gate working |
| Over-cap **save** | `422` via Pydantic `Field(max_length=...)` on the write model | Never silently truncate a persisted value |
| **No domain-level length invariant** | Caps live at the write boundary only | Deliberate deviation from the `slug` precedent: `slug`'s domain invariant is backed by a DB `CHECK` (`products_slug_format_check`), so the domain can never *read* a violating row. There is no such constraint here, and `description` is populated by direct DB access today — a domain cap would turn a lenient nullable `text` column into a read-time 500 landmine |
| **No DB `CHECK`** | Migration stays exactly D3's shape | Keeps the "metadata-only, no table rewrite" property provably identical to `deleted_at`'s. Residual: a direct-DB writer can exceed 160 chars, so the listing card renders with `line-clamp`, never assuming the cap |
| Language | `es-AR`, a module constant in the prompt | Verified: every product `name`, `model`, `color` and the one existing `description` in `supabase/seed.sql` is Spanish, prices in ARS |
| CI | Adapter constructor takes `transport: httpx.AsyncBaseTransport \| None = None` | Identical to `SupabaseStorage`. Zero secrets in CI (archived `ci-and-rls-tests` D2); no test ever opens a socket |

Dependency order on the alt-text generate route (the only one needing
three): 401 → `require_db_pool` 503 → `require_storage` 503 → `require_gemini` 503.
`require_storage` is genuinely required there because DD1 reads object bytes.

### DD5: Yes — automate directionality, in a **new** test module

**Decision: add `backend/tests/architecture/test_domain_dependencies.py`;
leave `test_domain_boundary.py` untouched.**

This change is the right trigger: cross-domain edges go from 1
(`stock -> products`) to 3, and D9 states a *prohibition* (`ai` imports
nothing; nothing imports `content`) that today has **no executable form at
all**. A prohibition living only in docstrings is exactly what breaks when
the deferred "dominios part 2" adds `recommendation`.

Separate module, not an extension: the existing one has a single scoped
responsibility (purity of `domain/`) and its walker only visits `domain/`;
this check walks all three layers of all six domains. Merging them would
blur two different rules into one failure message.

Mechanism — same `ast` technique, an explicit allowed-edges map:

```python
ALLOWED_EDGES = {
    "products": set(),
    "stock": {"products"},
    "content": {"ai", "products"},   # the two new edges (D9)
    "ai": set(),                     # leaf (D9)
    "recommendation": set(),         # stays empty (D1)
    "shared": set(),                 # shared must import NO domain
}
# Every domain may import `shared`. `gcell/api/` is the composition root
# and is exempt by design -- it imports everything.
```

**Verified green against today's tree** before writing it: the only
cross-domain imports in `backend/src/gcell/**` are `stock -> products`
(4 modules), everything → `shared`, and `api/admin.py` → everything.
`shared` imports no domain (the rule `object_storage.py` and `postgres.py`
already assert in prose).

### DD6: Structured JSON output with a response schema; partial output is a draft, not a failure

| Option | Tradeoff | Decision |
|---|---|---|
| Delimiter / heading parsing | Needs a bespoke parser plus a test per malformation (markdown fences, restated/translated headings), and fails *silently* — a mis-split blurb swallowing the body's first line looks like valid output | Rejected |
| Two calls (one per field) | Violates D10 outright | Rejected |
| **`responseMimeType: "application/json"` + `responseSchema`** | Couples the adapter to a Gemini generation-config feature | **Chosen** |

A schema cannot produce a plausible-but-wrong split; a delimiter parser
can. The `ai` port stays domain-agnostic (D9): it takes an
`instruction`, a `response_schema` mapping, and an optional `ImagePart`,
and returns a parsed `Mapping[str, Any]`. Naming product copy is
`content`'s job, not `ai`'s.

**Partial-output policy** (the explicitly required half):

| Model returned | Result |
|---|---|
| Both fields, non-blank after strip | `200` draft, each field trimmed to its own cap independently |
| Exactly one field blank or missing | **`200` draft with that field `null`** — the UI marks it "not generated". A half-useful draft the admin completes beats a hard failure that burned the same paid call (D6), and D5 makes the human the publish gate regardless |
| Both blank/missing, non-JSON, or schema-invalid | `502 generation_failed` — nothing to review |
| `promptFeedback.blockReason`, or `finishReason` outside `{STOP, MAX_TOKENS}` with no parts | `502 generation_refused` |

`maxOutputTokens` is set to 1024 — comfortably above the 160+1200-char
budget — because a `MAX_TOKENS` cut yields truncated, unparseable JSON,
which would land in the malformed branch and waste the call.

Alt-text generation uses the same machinery with a one-key schema; a blank
or missing `alt_text` there means nothing was produced → `502`.

### DD7: `CREATE OR REPLACE VIEW` — confirmed

| Option | Tradeoff | Decision |
|---|---|---|
| `DROP VIEW ... CASCADE` + recreate | Tidy column order, but **drops the `anon`/`authenticated` GRANT** issued in `20260810000458_public_catalog_rls.sql` and makes the public catalog's read privilege depend on a hand-copied GRANT in a second file. `CASCADE` also buys nothing: verified that no other object depends on `catalog_products` — `catalog_variants` and `catalog_product_images` read the base tables directly | **Rejected** |
| **`CREATE OR REPLACE VIEW` (append-only)** | `short_description` lands after `created_at`, next to nothing related | **Chosen** |

Column order is purely cosmetic here, and provably so: every read passes an
explicit column list (`CATALOG_PRODUCT_COLUMNS`), `select("*")` is banned
by a source-grep test, and PostgREST returns name-keyed objects. Nothing in
the codebase reads a view column by position. Weighing a cosmetic gain
against re-issuing grants on the only public read surface is not a close
call — and it matches `20260811000000_products_soft_delete.sql` verbatim.

Three artifacts must move in the **same slice**, column-for-column:

| Artifact | New value |
|---|---|
| View | `select id, slug, name, description, created_at, short_description` |
| `CATALOG_PRODUCT_COLUMNS` | `"id,slug,name,description,created_at,short_description"` |
| `CatalogProductRow` | `short_description: string \| null` appended after `created_at` |

`with (security_invoker = false)` is restated verbatim.

**Search is deliberately NOT changed.** `listCatalogProducts` keeps
`name.ilike,description.ilike`; adding `short_description.ilike` is a
public behaviour change no requirement asks for. Recorded as a follow-up.

## Sequence Diagrams

Generate copy (D10 — one click, one call, two fields):

    admin UI            Server Action        FastAPI /admin          content              ai                  Gemini
       │  click Generate    │                    │                     │                   │                    │
       ├───────────────────>│  POST .../copy/generate ─────────────────>│                   │                    │
       │                    │                401 <- verify_admin_jwt    │                   │                    │
       │                    │                503 <- require_db_pool / require_gemini        │                    │
       │                    │                    ├─ GenerateProductCopy ─>│                  │                    │
       │                    │                    │   product_context(id) │ (name, model, colors -- NO price)     │
       │                    │                    │   build prompt es-AR  ├─ generate_json ──>│  POST :generateContent
       │                    │                    │                      │                   ├───────────────────>│
       │                    │                    │                      │   {short_description, description}     │
       │                    │                    │   trim per-field caps <───────────────────┤<───────────────────┤
       │                    │<─ 200 {short_description, description} ────┤                   │                    │
       │  prefill 2 fields  │                    │                     │                   │                    │
       │<───────────────────┤   NO WRITE ANYWHERE ON THIS PATH (D5)     │                   │                    │
       │  edit, then Save   │                    │                     │                   │                    │
       ├───────────────────>│  PATCH /admin/products/{id} ─────────────>│  UpdateProductUseCase -> products      │

Generate alt text (image input, DD1):

    POST .../images/{image_id}/alt-text/generate
        │ 401 / 503 db / 503 storage / 503 gemini
        ├─ GenerateImageAltText
        │     photo_context(product_id, image_id)  ──> list_for_product -> pick image  (None = 404, IDOR guard)
        │     ObjectStorage.get(storage_path)      ──> StoredObject(bytes, "image/webp")
        │     generate_json(instruction, schema, ImagePart(...))  ──> Gemini inline_data
        └─ 200 {alt_text}   -- draft only; persisted later by PATCH .../images/{image_id} (DD3)

## File Changes

| File | Action | Description |
|---|---|---|
| `supabase/migrations/<ts>_products_short_description.sql` | Create | D3/DD7: `alter table products add column short_description text` + `create or replace view catalog_products` appending it |
| `backend/src/gcell/products/domain/product.py` | Modify | `description: str \| None = None`, `short_description: str \| None = None`, appended after `variants` (which already has a default). No length invariant (DD4) |
| `backend/src/gcell/products/application/{create,update}_product.py`, `register_product.py` | Modify | Carry both fields through; `UpdateProductUseCase` treats them as full-replacement scalars, like `name`/`model` |
| `backend/src/gcell/products/application/repository.py` | Modify | Docstring only — `update` now persists both text fields |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Modify | Add `p.description, p.short_description` to `_SELECT_COLUMNS`, `_INSERT_PRODUCT`, `_UPDATE_PRODUCT_FIELDS`, `_rows_to_product` |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Modify | Adapter parity |
| `backend/src/gcell/products/application/image_repository.py` | Modify | New `update_alt_text(image_id, alt_text)` port method |
| `backend/src/gcell/products/infrastructure/{postgres,in_memory}_product_image_repository.py` | Modify | Implement `update_alt_text`; 0 rows → `ImageNotFoundError` |
| `backend/src/gcell/products/application/update_product_image_alt_text.py` | Create | DD3 use case + ownership guard |
| `backend/src/gcell/shared/application/object_storage.py` | Modify | DD1: `StoredObject` + `get(path) -> StoredObject` |
| `backend/src/gcell/shared/infrastructure/supabase_storage.py` | Modify | DD1: `GET /object/{bucket}/{path}`, non-2xx → `ObjectStorageError` |
| `backend/src/gcell/shared/infrastructure/config.py` | Modify | `gemini_api_key()`, `gemini_model()` — backend-only, no `NEXT_PUBLIC_` twin (D7) |
| `backend/src/gcell/shared/infrastructure/dependencies.py` | Modify | `GeminiCredentials` + `require_gemini()` → 503 `gemini_unavailable` |
| `backend/src/gcell/ai/domain/generation.py` | Create | Pure: `ImagePart`, `SUPPORTED_IMAGE_MIMES`. Zero banned imports |
| `backend/src/gcell/ai/application/content_generator.py` | Create | `ContentGenerator` port, `GenerationError`, `GenerationRefusedError` |
| `backend/src/gcell/ai/infrastructure/gemini_content_generator.py` | Create | Thin `httpx` adapter, injectable transport (D8, DD4) |
| `backend/src/gcell/content/domain/copy_draft.py` | Create | `ProductCopyDraft`, `AltTextDraft`, the three caps, `trim_to_cap` |
| `backend/src/gcell/content/application/product_context_reader.py` | Create | DD2 ports + `ProductCopyContext`/`ProductPhotoContext` DTOs (no price) |
| `backend/src/gcell/content/application/{generate_product_copy,generate_image_alt_text}.py` | Create | The two use cases. Prompt building + schema + per-field cap trimming |
| `backend/src/gcell/content/infrastructure/products_context_reader.py` | Create | DD2 adapter over `ProductRepository`/`ProductImageRepository`. No SQL (D4) |
| `backend/src/gcell/api/admin.py` | Modify | Both text fields on the write/response models (`Field(max_length=160/4000)`); `PATCH .../images/{image_id}`; the two generate routes; `GenerationError` → 502 in `_execute_or_raise` |
| `backend/tests/architecture/test_domain_dependencies.py` | Create | DD5 directionality check |
| `backend/tests/architecture/test_frontend_service_role_boundary.py` | Modify | Parametrize the guard over `("SERVICE_ROLE", "GEMINI")` — proposal's risk row |
| `.env.example` | Create | First one in the repo; `config.py` already references it. Names only, never values |
| `frontend/src/lib/catalog/columns.ts` | Modify | DD7 allowlist |
| `frontend/src/lib/catalog/types.ts` | Modify | `CatalogProductRow.short_description` |
| `frontend/src/lib/catalog/derive.ts` | Modify | `CatalogListingCard.shortDescription` |
| `frontend/src/app/api/catalog/route.ts` | Modify | `CatalogListItem.shortDescription` — the client-side listing shares this shape |
| `frontend/src/app/(public)/catalog-listing-content.tsx`, `components/catalog/product-card.tsx` | Modify | Render the blurb with `line-clamp-2` (never assumes the 160 cap — DD4) |
| `frontend/src/app/(admin)/admin/products/{product-form,actions,image-manager}.tsx/.ts` | Modify | Two copy fields + one "Generate copy" trigger; editable alt text + "Generate alt text" |
| `frontend/src/app/(public)/product/[slug]/page.tsx` | **Unchanged** | Already renders `description` |
| `backend/src/gcell/recommendation/**` | **Unchanged** | D1 |
| `supabase/migrations/2026081*` (existing) | **Unchanged** | No policy, grant, or other view touched |

## Interfaces / Contracts

### Migration (DD7 / D3)

```sql
-- Nullable, no default => metadata-only ALTER, no table rewrite,
-- exactly like 20260811000000_products_soft_delete.sql's deleted_at.
alter table products add column short_description text;

-- CREATE OR REPLACE can only APPEND, which is why short_description lands
-- after created_at. It preserves the anon/authenticated GRANT from
-- 20260810000458_public_catalog_rls.sql -- DROP ... CASCADE would not.
create or replace view catalog_products
with (security_invoker = false) as
select
  id,
  slug,
  name,
  description,
  created_at,
  short_description
from products
where deleted_at is null;
```

### `shared/application/object_storage.py` (DD1)

```python
@dataclass(frozen=True)
class StoredObject:
    data: bytes
    content_type: str  # from the response header -- Gemini needs the exact mime


class ObjectStorage(Protocol):
    async def put(self, path: str, data: bytes, content_type: str) -> None: ...
    async def get(self, path: str) -> StoredObject:
        """Read an object's bytes. NOT idempotent-on-404 like `delete` --
        a missing object raises `ObjectStorageError` (maps to 502), because
        a caller asking for bytes cannot proceed without them."""
    async def delete(self, path: str) -> None: ...
```

### `ai/application/content_generator.py` (D9 — domain-agnostic)

```python
class ContentGenerator(Protocol):
    async def generate_json(
        self,
        *,
        instruction: str,
        response_schema: Mapping[str, Any],
        image: ImagePart | None = None,
        max_output_tokens: int = 1024,
    ) -> Mapping[str, Any]:
        """Raises GenerationError (transport/status/timeout/malformed) or
        GenerationRefusedError (safety block / no usable candidate)."""


class GenerationError(Exception): ...            # -> 502 generation_failed
class GenerationRefusedError(GenerationError): ...  # -> 502 generation_refused
```

Gemini request shape the adapter produces (`POST
{base}/v1beta/models/{model}:generateContent`, header `x-goog-api-key`):

```json
{
  "contents": [{"parts": [{"text": "<instruction>"},
                          {"inline_data": {"mime_type": "image/webp", "data": "<base64>"}}]}],
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseSchema": {"type": "OBJECT",
                       "properties": {"short_description": {"type": "STRING"},
                                      "description": {"type": "STRING"}},
                       "required": ["short_description", "description"]},
    "temperature": 0.4,
    "maxOutputTokens": 1024
  }
}
```

Read back from `candidates[0].content.parts[0].text` → `json.loads`. The
image part is omitted entirely when `image is None`.

### `content/application/product_context_reader.py` (DD2)

```python
@dataclass(frozen=True)
class ProductCopyContext:
    name: str
    model: str
    colors: list[str]      # NO price/cost field exists -- OQ2 made structural


@dataclass(frozen=True)
class ProductPhotoContext:
    storage_path: str
    product_name: str
    product_model: str
    variant_color: str | None   # None = hero image


class ProductContextReader(Protocol):
    async def product_context(self, product_id: UUID) -> ProductCopyContext | None: ...
    async def photo_context(
        self, product_id: UUID, image_id: UUID
    ) -> ProductPhotoContext | None:
        """`None` = unknown OR not owned by `product_id` -- resolved via
        `list_for_product(product_id)`, so ownership is a consequence of a
        product-scoped query, never a re-implemented predicate. Route maps
        `None` to 404 `not_found`, never 403."""
```

### New / changed endpoints

| Method | Path | Guards | Success | Writes? |
|---|---|---|---|---|
| `PATCH` | `/admin/products/{product_id}/images/{image_id}` | jwt, db | `200 AdminProductImageResponse` | Yes — `alt_text` only |
| `POST` | `/admin/products/{product_id}/copy/generate` | jwt, db, gemini | `200 {short_description, description}` (each nullable) | **No** |
| `POST` | `/admin/products/{product_id}/images/{image_id}/alt-text/generate` | jwt, db, storage, gemini | `200 {alt_text}` | **No** |

Both generate routes are `POST` (never `GET`): they are non-idempotent and
cost money, so they must never be cacheable, prefetchable, or
browser-retried. The verb-suffixed sub-path follows the existing
`PUT .../images/order` non-CRUD precedent.

## Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Architecture | D9 directionality: `ai` imports no domain; nothing imports `content`; `content -> {ai, products}` only; `shared` imports no domain | New `test_domain_dependencies.py`, `ast` walk + `ALLOWED_EDGES` (DD5) |
| Architecture | `content/domain/` and `ai/domain/` stay pure | Existing `test_domain_boundary.py` — passes unchanged |
| Architecture | No `GEMINI` token anywhere under `frontend/src/` | Parametrize `test_frontend_service_role_boundary.py` |
| Unit (ai adapter) | Request body carries the schema + `inline_data`; success parse; 4xx/5xx → `GenerationError`; timeout → `GenerationError`; `blockReason` → `GenerationRefusedError`; non-JSON text → `GenerationError`; **no retry** (handler call count == 1) | `httpx.MockTransport`, mirroring `test_supabase_storage.py`. Zero network |
| Unit (storage adapter) | `get` returns bytes + `content_type`; 404 → `ObjectStorageError` (not silent, unlike `delete`) | `httpx.MockTransport` |
| Unit (content use cases) | Both fields → draft; one blank → draft with `null`; both blank → `GenerationError`; over-cap → word-boundary trim; **prompt string contains no price** | Fake `ContentGenerator` + fake `ProductContextReader` |
| Unit (content adapter) | `photo_context` returns `None` for another product's image id and for an unknown id | In-memory products/image repositories |
| Unit (products) | `Product` round-trips both text fields, defaults `None`; alt-text use case 404s on cross-parent id | Existing use-case test style |
| Integration (adapter parity) | Postgres and in-memory repositories round-trip `description`, `short_description`, and `update_alt_text` identically | Existing parity suite — extend, do not fork |
| Integration (API) | `PATCH .../images/{id}` 200/404/422; generate routes 503 with `GEMINI_API_KEY` unset; **no DB row changes on any generate call** (assert before/after) | `fastapi.testclient` + dependency overrides |
| Integration (RLS) | `anon` still reads `catalog_products` after the view replacement, and the new column is visible | Archived `test_rls_policies.py` — extend the catalog-view assertion |
| Frontend unit | Blurb renders on the card and truncates; `CATALOG_PRODUCT_COLUMNS` matches `CatalogProductRow` key-for-key; no `select("*")` | Vitest; the existing `queries.test.ts` grep guard bites here |
| E2E | Live Gemini call | **Not automated.** Manual, once, with a real key (proposal's Dependencies) |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED test |
|---|---|---|---|
| Documentation-like paths | **N/A** — no file classification or executable-content decision | — | — |
| Git repository selection | **N/A** — no `git` invocation | — | — |
| Commit state | **N/A** — no VCS automation | — | — |
| Push state | **N/A** — no VCS automation | — | — |
| PR commands | **N/A** — no `gh` automation | — | — |
| **Routing (3 new routes)** | **Applicable** | All three sit under the router-level `verify_admin_jwt` (D6). Guard order 401 → db 503 → storage 503 → gemini 503, matching `admin.py`'s documented ordering so an unauthenticated caller can never probe config availability | Unauthenticated request to each new route → 401, asserted *before* any 503 case |
| **IDOR on the two image-scoped routes** | **Applicable** — a new write route and a new read route keyed by `(product_id, image_id)` | Ownership checked at the use-case/reader layer against a product-scoped query; unknown and cross-parent are indistinguishable (404 `not_found`, never 403) | Cross-parent `image_id` → 404 with the same body as an unknown id, for both PATCH and generate |
| **Secret exposure (`GEMINI_API_KEY`)** | **Applicable** — first non-Supabase secret | Backend-only, `os.environ`, no `NEXT_PUBLIC_` twin, never logged, never in a response body or error detail (`502 generation_failed` is opaque) | `test_frontend_service_role_boundary.py` parametrized over `GEMINI`; adapter test asserts the key appears only in the request header |
| **Process integration (paid external API)** | **Applicable** — first outbound third-party call | D6: admin-JWT-gated, one item per call, no bulk, no public/automatic trigger, no retry (DD4) | Assert the mock transport receives exactly one request per use-case invocation |
| **Prompt injection via product data** | **Applicable** — `name`/`model`/`color` are admin-typed free text interpolated into the instruction | Blast radius is bounded by construction: the output is a **draft with no write path** (D5), the response schema constrains the shape to two strings, and caps bound the length. Worst case is bad suggested copy an admin must approve | Use-case test with a product whose `name` contains instruction-like text: output is still schema-shaped and still writes nothing |
| **SSRF / third-party object exposure** | **Applicable** — DD1 was the fork | Chose (a): the backend reads bytes through its own port; no user-controlled URL is ever constructed, fetched, or handed out. Only `storage_path` values the repository already owns reach `ObjectStorage.get` | Covered by construction — `get` takes a bucket-relative path, never a URL |

## Migration / Rollout

One additive migration (D3), metadata-only, no rewrite, no policy or grant
change. Ships in slice 1 with the frontend column allowlist and
`CatalogProductRow` in the **same commit** — those three drifting apart
breaks every public catalog read, not just the blurb.

Rollout order matches the proposal's slices; 1 and 2 have zero Gemini
dependency and are safe to land before any key exists. Slice 3 (`ai`) is
wired to nothing and is inert until slice 4.

Rollback: forward-preferred. Leave the column (a nullable column nothing
reads costs nothing), `create or replace view` back to the
`20260811000000_products_soft_delete.sql` definition verbatim. Unsetting
`GEMINI_API_KEY` is a no-deploy kill switch that leaves everything else
working (D7).

## Open Questions

- [ ] **Gemini model id and Files-API/URL behaviour** (DD4/DD1 reason 2) —
      verify `gemini-2.5-flash` and the image-input contract against
      current docs at apply time, before writing the adapter. Neither
      decision flips: the `GEMINI_MODEL` env override absorbs a rename, and
      DD1 holds on reasons 1/3/4 regardless.
- [ ] **Catalog search over `short_description`** — deliberately excluded
      (DD7). Follow-up change if a blurb-only match ever matters.
- [ ] **PATCH full-replacement semantics for the two text fields** — they
      behave exactly like `name`/`model` today: a PATCH body omitting them
      clears them. Consistent with the existing route, and the admin form
      always renders and submits both. Flagged because any non-form API
      client can wipe copy by omission.
- [ ] **`api/admin.py` size** — now hosting every admin route including
      three new ones. Splitting it is a follow-up refactor, deliberately
      not bundled here (one status-mapping table must not become two).
