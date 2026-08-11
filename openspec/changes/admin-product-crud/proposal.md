# Proposal: Admin Product CRUD

## Intent

`admin-panel-auth` shipped the gate and one read-only proof page; `products-postgres-adapter` shipped `add`/`get`/`list` and explicitly deferred update and delete because `ON DELETE RESTRICT` made delete a separate design problem. The result: the admin can *see* products but cannot create, correct, or retire one — every catalog change still needs raw SQL. This change closes that loop with write endpoints and admin forms, and resolves the deferred delete problem via soft-delete.

## Scope

### In Scope

- Backend: `ProductRepository` port gains `update` and `soft_delete`; Postgres + in-memory adapters implement both.
- New use cases: update product (fields + add/remove variants), soft-delete product, soft-delete variant.
- Server-side slug generation from `name` (kebab-case) with collision resolution; the admin never types a slug.
- `POST`/`PATCH`/`DELETE` routes on the existing `/admin` router, reusing `verify_admin_jwt` unchanged.
- **Supabase migration** (new): soft-delete column on `products` and `product_variants`; catalog views and admin reads exclude soft-deleted rows. `stock_movements` and its append-only trigger stay untouched.
- Frontend: create and edit pages with variant add/remove, delete action, plus write proxy routes; extends the existing `/admin/products` page rather than rebuilding it.

### Out of Scope

- **Product image upload** — net-new service-role storage integration, deferred to its own change (decided).
- Hard delete, restore-from-trash UI, purge tooling.
- Stock adjustment UI, `product_images` CRUD.
- Auth changes: `createSessionClient`, proxy, and JWT verification are reused as-is.
- Optimistic concurrency / version column — single admin, last-write-wins accepted.

## Capabilities

### New Capabilities

- `admin-product-management`: admin-facing create/edit/soft-delete workflows for products and variants (forms, proxy write routes, validation feedback).

### Modified Capabilities

- `product-persistence`: port and adapters gain update and soft-delete; slug becomes derived, not caller-supplied.
- `admin-api-access`: replaces "MUST NOT expose any create, update, or delete admin endpoint" with the write-endpoint contract.
- `product-catalog-schema`: adds the soft-delete column and requires public catalog views to exclude soft-deleted products/variants.

## Approach

Soft-delete over hard delete (decided): a `deleted_at`-style column makes retirement a normal `UPDATE`, so the `stock_movements` FK `RESTRICT` and its unconditional no-UPDATE/DELETE trigger are never touched and stock history stays intact. Slug is generated server-side in the application layer from `name`, deduped with a numeric suffix, so the domain's existing format regex remains the single validation authority. Frontend forms follow the only established pattern in the repo — client component + `useActionState` + Server Action + raw styled inputs — no new component kit.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/.../products/application/repository.py` | Modified | `update`, `soft_delete` on the port |
| `backend/.../products/application/` | New | Update/delete use cases, slug generator |
| `backend/.../products/infrastructure/` | Modified | Both adapters implement new port methods |
| `backend/src/gcell/api/admin.py` | Modified | POST/PATCH/DELETE routes + Pydantic models |
| `supabase/migrations/` | New | Soft-delete column + catalog view update |
| `frontend/src/app/api/admin/products/**` | Modified | Read-only proxy routes only (refactored onto a shared relay helper) |
| `frontend/src/lib/admin/` | New | Shared session-gate-then-relay helper (`adminBackendFetch`), reused by reads AND writes |
| `frontend/src/app/(admin)/admin/products/**` | New/Modified | New/edit pages, forms, Server Actions (writes go straight through Server Actions, never through a write Route Handler — see design.md "Decision: no write Route Handlers", a CSRF-motivated correction to this proposal's original assumption) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Migration changes catalog views; public catalog regresses | Med | View update spec'd; existing public-catalog tests must pass unchanged |
| Soft-deleted products leak into public catalog | Med | Filter enforced at the view layer, not per-query |
| Slug regeneration on rename breaks public URLs | Med | Open question below; default assumption is frozen-after-create |
| Variant removal on a variant with stock history | Med | Soft-delete the variant, never a row delete |
| Exceeds the 400-line review budget | High | Likely 2–3 chained PRs (backend / frontend / migration+wiring); exact split is `sdd-tasks`' call |

## Rollback Plan

Revert the change commits, then apply a down-migration dropping the soft-delete column and restoring the prior catalog view definitions. No data is destroyed by the forward migration (additive column, default "not deleted"), and no `stock_movements` row is ever touched, so rollback loses only the retirement flag. The read-only `/admin/products` page and the whole auth chain are untouched by a revert.

## Dependencies

- Local Supabase stack running; `admin-panel-auth` merged (JWT-gated `/admin` router + session proxy).
- No new runtime dependency, no new secret. **No Gemini API usage in this change.**

## Success Criteria

- [ ] Admin creates a product with variants from the UI; it persists with a server-generated slug.
- [ ] Two products with the same name yield distinct, valid slugs.
- [ ] Admin edits fields and adds/removes a variant; changes persist atomically.
- [ ] Soft-deleting a product with recorded stock movements succeeds and leaves `stock_movements` untouched.
- [ ] Soft-deleted products disappear from the public catalog and from the admin list.
- [ ] Every write endpoint returns `401` without a valid admin JWT and never reaches the repository.
- [ ] Existing public-catalog and admin-auth tests pass unchanged.

## Proposal question round — RESOLVED

All open product questions decided by the user (2026-08-11); the delete strategy, slug generation, and image-upload deferral were already decided pre-proposal and are not reopened here.

1. **Slug on rename**: frozen after create. Renaming a product changes the display name only; the slug (and its public URL) never changes after creation.
2. **Restore UI**: not in this change. Soft-delete is one-way from the admin UI here; restoring a retired product/variant is a DB-only operation until a later change.
3. **"Show retired" filter**: none. Soft-deleted products/variants are hidden entirely from the admin list — consistent with decision 2 (nothing to act on if they can't be restored yet).
4. **Removing the last variant**: **permitted** (diverges from this proposal's original suggested default). A product MAY end up with zero active variants without being itself retired — it becomes effectively invisible in the public catalog (no variants to list) but remains a distinct, editable product record. `sdd-spec`/`sdd-design` must NOT enforce a "≥1 active variant" invariant on `Product`.
5. **Cascade on product retirement**: soft-deleting a product implicitly hides all of its variants. A single variant can also be retired independently without affecting the product or its other variants.
