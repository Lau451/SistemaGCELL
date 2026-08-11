# Design: Admin Product CRUD

## Technical Approach

Four layers, one new invariant. (1) A **single additive migration** puts `deleted_at timestamptz` on `products` and `product_variants` and rewrites the three public catalog views with `CREATE OR REPLACE VIEW` — **same column lists, added `WHERE`** — so `lib/catalog/columns.ts` and its pinned conformance test stay byte-untouched and `stock_movements` is never referenced. (2) The `products` **application layer** gains a pure `slugify` + a repository-probing dedupe loop, and update/soft-delete use cases; the domain model is unchanged and remains the only validation authority. (3) `api/admin.py` grows `POST`/`PATCH`/`DELETE` under the *existing* router-level `Depends(verify_admin_jwt)` — the trust boundary is reused verbatim, not re-implemented. (4) The frontend writes exclusively through **Server Actions** over one shared server-only relay (`lib/admin/backend-fetch.ts`), which is the same relay the read Route Handlers use.

The load-bearing rule everywhere: **soft-delete is a read-time filter, never a second write.** Retiring a product stamps exactly one row.

## Architecture Decisions

### Decision: `deleted_at timestamptz NULL`, not `is_active boolean`

| Option | Tradeoff | Decision |
|---|---|---|
| `deleted_at timestamptz null` | Nullable, no default → metadata-only `ALTER`, no table rewrite; records *when*; `WHERE deleted_at IS NULL` is the single idiom on tables and views; supports a future restore/purge with zero schema change | **Chosen** |
| `is_active boolean not null default true` | Needs a default → rewrite-ish on older PG, and loses the retirement timestamp that a future purge tool or audit needs | Rejected |
| Status enum (`draft`/`active`/`retired`) | Encodes a publishing workflow nobody asked for; the proposal scopes retirement only | Rejected |

Both tables get the column. `stock_movements` gets nothing — it is only ever read.

### Decision: retired slugs stay reserved (global unique index kept)

`products_slug_key` stays a **plain global** unique constraint; it is NOT converted to a partial index `unique (slug) where deleted_at is null`.

**Rationale**: freeing a retired slug lets a *different* product silently inherit a live public URL that browsers, the PWA runtime cache, and search engines already hold. With slug frozen on rename (proposal Q1) and no restore UI (Q2), URL identity is permanent by construction — so retiring `funda-iphone-15` and then creating another "Funda iPhone 15" must yield `funda-iphone-15-2`, not a reused slug.

**Consequence, and the reason a new port method exists**: `get_by_slug` will filter out retired products, so it can no longer answer "is this slug taken?". The port therefore gains a distinct `slug_exists(slug) -> bool` that **deliberately ignores `deleted_at`**, mirroring exactly what the unique index sees. Reusing `get_by_slug` for the collision probe would generate a candidate the DB then rejects — a guaranteed 500 on the very first name reuse after a retirement.

### Decision: product retirement cascades at read time, not by stamping variants

`soft_delete(product_id)` issues one `UPDATE products SET deleted_at = now()`. Variants are hidden because every read joins on `p.deleted_at IS NULL` (proposal Q5's cascade).

**Alternatives rejected**: stamping every child variant too (two writes, and it destroys the distinction between "hidden because its parent retired" and "retired individually" — a future restore could not tell which variants to bring back); a DB trigger (invisible cascade, and this repo already reserves triggers for `updated_at` and the append-only ledger).

### Decision: the `LEFT JOIN` filter goes in `ON`, never in `WHERE`

```sql
LEFT JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
WHERE p.deleted_at IS NULL
```

Moving `v.deleted_at IS NULL` into `WHERE` silently degrades the `LEFT JOIN` to an inner join, and every product whose variants were all retired **disappears from the admin list**. Proposal Q4 explicitly permits zero active variants, so that product must still be listed and editable. This gets a dedicated RED test; it is the single easiest way to break this change.

### Decision: slug generated in `application/`, validated only by the domain

New module `products/application/slug.py`:

```python
def slugify(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not hyphenated:
        raise UnslugifiableProductNameError(name)     # never fabricate a slug
    return hyphenated[:_MAX_BASE_LENGTH].rstrip("-")  # 76, leaves room for "-999"
```

`"Funda iPhone 15 Pro Máx"` → `funda-iphone-15-pro-max`; `"Fundas & Cases!!"` → `fundas-cases`; `"Niño"` → `nino`. NFKD + combining-mark strip is the right transform for a Spanish catalog: it is the standard, lossless-for-ASCII path and needs no transliteration table.

A name with **no** latin-alphanumeric content (`"🎁🎁"`) raises rather than inventing `product-1` — fabricating a slug hides a data-entry error behind a meaningless permanent URL.

**Collision resolution** (`generate_unique_slug(repository, name)`): `base`, then `base-2`, `base-3`, … The first product keeps the bare slug and the second gets `-2` (Django/WordPress convention, matches "the second one"). Probe with `slug_exists`, bounded at 100 attempts. If a candidate would exceed 80 chars, shorten `base` by the overflow and `rstrip("-")` before appending.

The domain's `_SLUG_PATTERN` stays the **only** validator — `Product.__post_init__` re-checks whatever the generator produced, so a generator bug fails loudly at construction instead of reaching Postgres.

**Race handling**: the probe is advisory only. `repository.add` remains the single source of truth (the `register_product` doctrine: no TOCTOU pre-check duplicated in two places), so a lost race surfaces as `DuplicateProductSlugError` → `409`. A regenerate-and-retry loop was rejected: single admin, last-write-wins is already an accepted proposal constraint, and retry machinery for an unreachable race is dead code.

### Decision: `PATCH` never retires; retirement has its own URL

`update(product)` **adds and updates** variants and never deletes one. Variant retirement is `DELETE /admin/products/{id}/variants/{variant_id}`.

**Rationale**: removal-by-omission means a truncated form post, a stale tab, or a dropped field **silently retires stock-bearing variants with no explicit intent** — and `last-write-wins` (accepted in the proposal) makes that strictly worse. Destructive actions get their own explicit, effect-idempotent URL. Atomicity is preserved where the success criteria demand it (field edits + variant additions are one transaction); retirement is one row, so it needs no transaction at all.

**Rejected**: reconciling the full variant list inside `update` via `id <> ALL($ids)` — one elegant statement, one silent data-loss vector.

### Decision: no write Route Handlers — Server Actions relay directly (**deviates from proposal scope**)

The proposal's Affected Areas lists `frontend/src/app/api/admin/products/**` as the write-proxy surface. This design **narrows that to reads only**.

**Rationale**: (a) the existing GET proxy exists because an *RSC page* needs a same-origin URL — a Server Action already runs on the server and needs no HTTP hop, and routing writes through one would force hand-forwarding the cookie header exactly as `products/page.tsx` does today; (b) a cookie-authenticated JSON Route Handler is a **CSRF surface** (`request.json()` does not check `Content-Type`, so a cross-site `text/plain` POST parses fine) and would need a hand-rolled `Origin`/`Sec-Fetch-Site` guard, whereas Next's Server Actions enforce origin matching natively; (c) a write route nothing calls is dead, untested-in-anger surface.

The proposal's *intent* — "session-gate, then relay with a Bearer token" — is preserved and in fact centralized: `lib/admin/backend-fetch.ts` becomes the one implementation, used by the read Route Handlers **and** the Server Actions. This is the same class of correction `admin-panel-auth`'s design made to its own proposal (`middleware.ts` → `proxy.ts`). Flagged in Open Questions: `sdd-spec` is running in parallel and may spec write proxy routes.

### Decision: `422` for every rejected body; no `400`

| Failure | Code | Body |
|---|---|---|
| Missing/malformed field, extra field (`slug`), non-numeric price | `422` | FastAPI/Pydantic native `{"detail": [...]}` |
| Domain invariant (`ValueError`/`TypeError` from `Product`/`ProductVariant`) | `422` | `{"detail": "ProductVariant.price cannot be negative"}` |
| Unknown/retired product, unknown variant, variant of another product | `404` | `{"detail": "not_found"}` |
| `DuplicateProductSlugError` escaping the generator | `409` | `{"detail": "slug_conflict"}` |
| No/invalid token | `401` | unchanged, router-level |
| No pool | `503` | unchanged, `require_db_pool` |

Every rejection here is a well-formed request with unprocessable content, so `422` is correct and there is never a second code meaning the same thing. Duplicating the money/blank rules as Pydantic constraints was rejected — the domain must stay the single authority (proposal's stated approach for slug, applied consistently). The cost is two `detail` shapes (string vs list), absorbed by one frontend helper `extractAdminError`.

A variant belonging to a *different* product returns `404`, not `403`: never confirm existence across a wrong parent.

## Data Flow

Create, the only flow with non-trivial sequencing:

```
new-product-form.tsx (client, useActionState)
        │ FormData: name, model, variant-color[], variant-price[], variant-cost[]
        ▼
createProductAction  [Server Action — origin-checked by Next]
        │ adminBackendFetch("POST", "/admin/products", body)
        │   getClaims() ─none─▶ redirect("/admin/login")   (backend NEVER called)
        │   getSession().access_token → Authorization: Bearer
        ▼
FastAPI  POST /admin/products    Depends(verify_admin_jwt) ← trust boundary (unchanged)
        └─▶ Depends(require_db_pool) ─None─▶ 503
                ▼
        CreateProductUseCase
          1. slugify(name)                       ── pure, no I/O
          2. slug_exists(base) ──taken──▶ base-2, base-3 …  (sees RETIRED rows too)
          3. Product(id=uuid4(), slug=…, …)      ── domain re-validates the slug
          4. repository.add(product)             ── one transaction
                ▼                                      │ UniqueViolation → 409
        201 {id, slug, name, model, variants}
                ▼
   revalidatePath("/admin/products") → redirect("/admin/products")
```

Retire, and why `stock_movements` is untouched:

```
retireProductAction ─DELETE /admin/products/{id}─▶ soft_delete(product_id)
        UPDATE products SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL
        └─ 0 rows → ProductNotFoundError → 404
   product_variants: NOT written   stock_movements: NOT read, NOT written
   catalog_products / catalog_variants / catalog_product_images: rows vanish via WHERE
```

## File Changes

| File | Action | Description |
|---|---|---|
| `supabase/migrations/2026081100XXXX_products_soft_delete.sql` | Create | `alter table … add column deleted_at timestamptz`; `create or replace view` ×3 with identical column lists + `WHERE`; two partial indexes |
| `backend/.../products/application/slug.py` | Create | `slugify`, `generate_unique_slug` |
| `backend/.../products/application/exceptions.py` | Modify | `ProductNotFoundError`, `VariantNotFoundError`, `UnslugifiableProductNameError` |
| `backend/.../products/application/repository.py` | Modify | `update`, `soft_delete`, `soft_delete_variant`, `slug_exists` |
| `backend/.../products/application/create_product.py` | Create | Slug generation + `add` (wraps, does not replace, `RegisterProductUseCase`) |
| `backend/.../products/application/update_product.py` | Create | Field edit + variant add/update; slug never touched |
| `backend/.../products/application/retire_product.py` | Create | Product and variant soft-delete use cases |
| `backend/.../infrastructure/postgres_product_repository.py` | Modify | `deleted_at` filters on all 3 SELECTs (`ON` clause for variants), 4 new methods |
| `backend/.../infrastructure/in_memory_product_repository.py` | Modify | Same 4 methods; a `_deleted: set[UUID]` mirror, `slug_exists` ignoring it |
| `backend/src/gcell/api/admin.py` | Modify | `GET {id}`, `POST`, `PATCH {id}`, `DELETE {id}`, `DELETE {id}/variants/{vid}` + request models |
| `frontend/src/lib/admin/backend-fetch.ts` | Create | The one session-gate-then-relay implementation |
| `frontend/src/lib/admin/api-error.ts` | Create | `extractAdminError` — normalizes both `422` shapes |
| `frontend/src/app/api/admin/products/route.ts` | Modify | Refactor onto `adminBackendFetch` (GET only; **no** POST) |
| `frontend/src/app/api/admin/products/[id]/route.ts` | Create | GET one, for the edit page |
| `frontend/src/app/(admin)/admin/products/actions.ts` | Create | `createProductAction`, `updateProductAction`, `retireProductAction`, `retireVariantAction` |
| `frontend/src/app/(admin)/admin/products/product-form.tsx` | Create | Client component; variant rows in `useState`; `useActionState` |
| `frontend/src/app/(admin)/admin/products/new/page.tsx` | Create | Create page |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Create | Edit page (RSC → `/api/admin/products/{id}`) |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Modify | "New product" link, Edit link + Retire form per row |

**Zero changes** to `lib/pwa/runtime-caching.ts` (new pages are under `/admin/`, the new API route under `/api/admin` — both already matched), to `lib/catalog/columns.ts` (view column lists unchanged), and to `products/domain/product.py`.

## Interfaces / Contracts

### Migration (the only view-safe shape)

`CREATE OR REPLACE VIEW` requires identical column names, types, and order — satisfied, because only a `WHERE` is added. Existing `GRANT`s survive a replace.

```sql
alter table products add column deleted_at timestamptz;
alter table product_variants add column deleted_at timestamptz;

create index products_active_idx on products (created_at, id) where deleted_at is null;
create index product_variants_active_product_idx on product_variants (product_id) where deleted_at is null;

create or replace view catalog_products with (security_invoker = false) as
select id, slug, name, description, created_at from products
where deleted_at is null;

create or replace view catalog_variants with (security_invoker = false) as
select v.id, v.product_id, p.model as phone_model, v.color, v.price,
       coalesce(sl.quantity_on_hand, 0) > 0 as in_stock
from product_variants v
join products p on p.id = v.product_id
left join variant_stock_levels sl on sl.variant_id = v.id
where v.deleted_at is null and p.deleted_at is null;   -- Q5 cascade

create or replace view catalog_product_images with (security_invoker = false) as
select i.id, i.product_id, i.variant_id, i.storage_path, i.alt_text, i.sort_order
from product_images i
join products p on p.id = i.product_id
where p.deleted_at is null
  and (i.variant_id is null                              -- hero image: no variant
       or exists (select 1 from product_variants v
                  where v.id = i.variant_id and v.deleted_at is null));
```

`EXISTS`, not a second join: a join on a nullable `variant_id` either drops hero images or risks row multiplication. `variant_stock_levels` is untouched — stock history must survive retirement.

Filename must sort **after** `20260810000502`. No down-migration file: this repo has no `down` convention; rollback is the proposal's manual `drop column` + re-running the two prior view definitions.

### Port additions

```python
class ProductRepository(Protocol):
    async def update(self, product: Product) -> None: ...
    """Persist field edits and add/update the given variants, in ONE transaction.
    NEVER deletes or retires a variant. Raises ProductNotFoundError if no
    ACTIVE product with that id exists."""

    async def soft_delete(self, product_id: UUID) -> None: ...
    async def soft_delete_variant(self, product_id: UUID, variant_id: UUID) -> None: ...

    async def slug_exists(self, slug: str) -> bool: ...
    """Ignores `deleted_at` ON PURPOSE — mirrors the global unique index, so a
    retired product's slug is never handed to a different product."""
```

Postgres `update` body: one `UPDATE products SET name=$2, model=$3` (slug absent — frozen), then per variant `INSERT INTO product_variants (…) VALUES (…) ON CONFLICT (id) DO UPDATE SET color=…, price=…, cost=…` — `deleted_at` is **never** in the `SET` list, so a retired variant cannot be resurrected by a replayed body.

### Request models (`api/admin.py`)

```python
class AdminVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")   # a client sending `slug` gets 422, not silence
    id: UUID | None = None                      # None = new variant
    color: str
    price: Decimal
    cost: Decimal

class AdminProductWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    model: str
    variants: list[AdminVariantInput] = []      # empty allowed — proposal Q4
```

No `slug` field on any request model, ever. `POST` → `201` + `AdminProductResponse`; `PATCH` → `200` + `AdminProductResponse`; both `DELETE`s → `204` with no body.

### Frontend relay

```ts
export type AdminBackendResult =
  | { outcome: "response"; status: number; body: unknown }   // body null on 204
  | { outcome: "unauthenticated" }                            // fetch NEVER called
  | { outcome: "backend_unavailable" };

export async function adminBackendFetch(
  path: string, init?: { method?: string; body?: unknown },
): Promise<AdminBackendResult>;
```

`getClaims()` gates; `getSession().access_token` is read only afterwards purely to relay (unchanged posture from `admin-panel-auth`). The helper must **not** call `.json()` on a `204`/empty body — the current `route.ts` does it unconditionally, which is safe for GET only.

**Money never becomes a JS `number`.** Form inputs are `type="number" step="0.01" min="0"`; `FormData` yields a string; that string is relayed verbatim and parsed by Pydantic into `Decimal`. A single `parseFloat` would reintroduce exactly the precision loss `_validate_money` exists to prevent.

Variant rows are submitted as **parallel repeated fields** (`variant-id`, `variant-color`, `variant-price`, `variant-cost`), zipped positionally via `formData.getAll()`; a blank `variant-id` means "new". No bracket-notation parser, no JSON in a hidden field. Next 16 dynamic routes take `params: Promise<{ id: string }>` (verified in `node_modules/next/dist/docs/.../route.md:87`).

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (BE) | `slugify` | Table-driven: `"Funda iPhone 15 Pro Máx"`→`funda-iphone-15-pro-max`; `"Niño"`→`nino`; `"Fundas & Cases!!"`→`fundas-cases`; `" --x-- "`→`x`; 200-char name → ≤76 and no trailing `-`; `"🎁"` → `UnslugifiableProductNameError` |
| Unit (BE) | Collision scheme | `InMemoryProductRepository`: same name ×3 → `base`, `base-2`, `base-3`; **retired** product still reserves its slug → next is `base-2`; 100-attempt bound raises |
| Unit (BE) | Use cases | Rename does NOT change `slug` (explicit assert); `update` on a retired id → `ProductNotFoundError`; retiring the **last** variant succeeds (Q4); variant of another product → `VariantNotFoundError` |
| Integration (BE, `db_conn`) | The `ON`-vs-`WHERE` trap | Product with every variant retired still returned by `list_all`, with `variants == []` |
| Integration (BE, `db_conn`) | Ledger safety | Retire a product whose variant has `stock_movements` rows → succeeds; `count(*)` and `sum(quantity_delta)` on `stock_movements` unchanged (the headline success criterion) |
| Integration (BE, `db_conn`) | Views | Raw SQL after a retire: `catalog_products` loses the row; `catalog_variants` loses variants of a retired product AND an individually retired variant; `catalog_product_images` loses both, hero image included; a live product is unaffected |
| Integration (BE, `db_conn`) | Adapter | `update` reconciles in one transaction (failure mid-way leaves nothing); `slug_exists` is `True` for a retired slug; `ON CONFLICT` never clears `deleted_at` |
| Integration (BE, `TestClient`) | Routes | Per endpoint: no token → `401` **and** repository spy never called; valid token + no pool → `503`; `slug` in body → `422`; unknown id → `404`; `POST` → `201` with a server-generated slug the client never sent |
| Unit (FE) | `adminBackendFetch` | Stubbed `createSessionClient` + spied `fetch`: no claims → `unauthenticated`, `fetch` never called; relays method/body/`Bearer`; `204` → `body: null`; thrown fetch → `backend_unavailable` |
| Unit (FE) | `extractAdminError` | Pydantic list shape, string shape, and an unrecognized body → generic fallback |
| Unit (FE) | Server Actions | `adminBackendFetch` mocked: `201`→`revalidatePath`+`redirect`; `422`→ returns `{error}` and does NOT redirect; `unauthenticated`→ redirect to `/admin/login` |
| Component (FE) | `product-form.tsx` | Add row; removing an **unsaved** row is client-only (no request); removing a **saved** row submits the retire action; error rendered with `role="alert"` |
| Regression | No collateral damage | `api/admin/products/__tests__/route.test.ts`, `columns.test.ts`, `queries.test.ts`, `catalog-route-conformance.test.ts` all run **unmodified** and stay green (the existing route test mocks `@/lib/supabase/server` + `@/lib/admin/env`, which the new helper also imports — so the refactor is invisible to it) |
| Conformance (FE) | New paths | Extend `catalog-route-conformance.test.ts` with `/admin/products/new`, `/admin/products/{id}`, `/api/admin/products/{id}` → `NetworkOnly`, with **zero** source change to `runtime-caching.ts` |
| E2E | Full chain | One documented manual pass on the live local stack (create → edit → retire → confirm gone from the public catalog). No Playwright exists. |

Strict TDD: every row above is RED first. The three highest-value RED tests are the `ON`-vs-`WHERE` trap, the retired-slug reservation, and the untouched `stock_movements` count.

## Threat Matrix

| Boundary | Applicability | Design response |
|---|---|---|
| Documentation-like paths | N/A — no file classification or execution-from-file logic ships | — |
| Git repository selection | N/A — no VCS invocation at runtime | — |
| Commit state | N/A | — |
| Push state | N/A | — |
| PR commands | N/A — no shell/subprocess/PR automation | — |

Routing changes here are additive HTTP paths under an already-gated router. The real adversarial boundaries, carried as RED tests above:

1. **IDOR across parents** — `DELETE /admin/products/{A}/variants/{v_of_B}` must be `404`, never a successful retire and never a `403` that confirms `v_of_B` exists.
2. **Client-supplied slug** — any request body carrying `slug` must be `422` (`extra="forbid"`), never a silently ignored field that lets an admin believe they set a URL.
3. **Soft-delete leakage** — a retired product/variant must vanish from all three public views AND the admin list; the view filter is the enforcement point, not per-query discipline.
4. **Ledger immutability** — no code path may `UPDATE`/`DELETE` `stock_movements`; asserted by count/sum invariance, not by inspection.
5. **Money precision** — no `float`/`parseFloat` anywhere in the write path; `Decimal` from Pydantic straight into the domain validator.

## Migration / Rollout

One forward migration, purely additive (nullable column, no default, `CREATE OR REPLACE VIEW`). Existing rows read as "not deleted" with no backfill. Applied by `npx supabase migration up` (or a local `db reset`) before the backend read filters ship — otherwise every `SELECT` errors on an unknown column, so **the migration slice must land first**.

Rollback: revert the commits, then `alter table … drop column deleted_at` and re-run the two prior view definitions from `20260810000458_public_catalog_rls.sql`. Only the retirement flag is lost; no product, variant, image, or stock row is ever destroyed by the forward path.

## Review Workload Forecast (advisory — `sdd-tasks` decides)

Honest estimate: **~1400–1600 authored lines**, well past the 400-line budget. `2–3` PRs (the proposal's guess) is optimistic; a realistic, individually shippable split is **4**:

1. **Migration + read filters** (~200) — column, three views, adapter `SELECT` filters, view/`ON`-vs-`WHERE` tests. Green on its own, no behavior change for the admin.
2. **Port + adapters + slug** (~450) — `slugify`, dedupe, 4 port methods, both adapters, unit + db-integration tests.
3. **API routes** (~300) — 5 endpoints, request models, error mapping, `TestClient` tests.
4. **Frontend** (~550) — relay helper, 4 Server Actions, form, 3 pages, tests. Possibly splits again (helper+actions / pages+form) if it overruns.

`400-line budget risk: High`. Order is forced: 1 → 2 → 3 → 4.

## Open Questions

- [x] **`sdd-spec` divergence risk — RESOLVED, no reconciliation needed**: orchestrator read the completed `admin-product-management/spec.md` in full after both parallel phases finished. Every requirement/scenario is written at the behavior level ("the form MUST persist...", "the admin MUST see...") with zero mention of Route Handlers or any specific transport mechanism — the spec does not lock in write proxy routes as the implementation. This design's Server-Actions-only decision satisfies every scenario without contradiction. Only `proposal.md`'s informal "Affected Areas" table assumed proxy routes; that table has been corrected to match this design (the same class of self-correction as `admin-panel-auth`'s `middleware.ts`→`proxy.ts` fix).
- [ ] Exact migration filename timestamp is picked at apply time; it MUST sort after `20260810000502`.
