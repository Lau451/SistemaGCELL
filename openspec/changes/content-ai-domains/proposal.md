# Proposal: Content + AI Domains (Gemini-Assisted Product Copy)

## Intent

Two of the six hexagonal domains have been **empty scaffolds since
`2026-08-09-initial-scaffolding`** — `backend/src/gcell/{content,ai}/` contain
nothing but `__init__.py`. Meanwhile `openspec/config.yaml` has committed the
project to "AI: Google Gemini API (image + text), backend-only calls" since day
one, with **zero** Gemini code, key, dependency, or precedent anywhere in the
repo.

Two concrete product-copy holes exist today, both verified against the schema:

- **`products.description`** (nullable `text`, `20260810000449_products_catalog.sql`)
  is exposed through `catalog_products` and **is already rendered** on
  `/product/[slug]`. But it is completely unwired on the write side: absent from
  the `Product` dataclass, absent from `create_product.py`/`update_product.py`,
  absent from the admin `ProductForm`. **Today the only way to populate it is
  direct DB access** — so every product detail page ships with an empty
  description.
- **The catalog listing has no product copy at all.** `catalog-listing-content.tsx`
  renders no description of any kind, and `catalog_products` carries only the
  single long-form `description` column. A listing card and a detail page need
  different copy, so the store needs **two** fields, not one (D3, OQ1).
- **`product_images.alt_text`** exists and *is* wired (domain, both repositories,
  upload use case, admin `image-manager.tsx`) — but **write-once at upload
  only**. There is no update route, use case, or port method. An image uploaded
  without alt text is permanently inaccessible, and every catalog image renders
  `alt=""`.

Writing good copy for every product and every photo by hand is exactly the
operational cost an admin panel should remove. This change closes both holes and
lands the first real code in `content` and `ai`.

## Scope

### In Scope

- **`ai` domain** — a Gemini port (`ai/application/`) plus a thin `httpx`
  adapter (`ai/infrastructure/`) covering **both** text and image-input
  generation, mirroring the `shared/application/object_storage.py` port +
  `shared/infrastructure/supabase_storage.py` adapter precedent. `GEMINI_API_KEY`
  in `shared/infrastructure/config.py` and a `require_gemini`-style 503 guard in
  `dependencies.py`, mirroring `require_storage`.
- **`content` domain** — two admin-triggered use cases: *generate product copy*
  (one text call returning **both** the blurb and the body — D10) and *generate
  alt text for one existing product photo* (image input). Both return
  **drafts**, never publish (D5).
- **One small additive migration** (D3) — adds `products.short_description`
  (nullable `text`) and appends it to the `catalog_products` view. The existing
  `products.description` is repurposed in *meaning only* (no rename, no
  backfill) as the long detail body.
- **Two-field product copy write path** — `Product.description` and
  `Product.short_description`, create/update use cases, admin API, and two
  editable fields in `ProductForm`. Works with or without Gemini configured.
- **Catalog listing renders the blurb** — `short_description` flows through the
  pinned column allowlist (`lib/catalog/columns.ts`), `CatalogProductRow`, and
  `catalog-listing-content.tsx`.
- **Alt-text update path** — a way to change `alt_text` on an *existing* image
  (does not exist today), plus the "Generate" trigger in `image-manager.tsx`.

### Out of Scope

| Deferred | Rationale |
|---|---|
| **`recommendation` domain** | D1. Explicitly deferred to a later "dominios part 2" change. Not scaffolded, not touched, not specced here. |
| **Any `content` table, content-authoring audit table, or draft/version history table** | D3 (surviving half) + OQ3. The migration adds **product-facing text columns only**. Generated drafts are transient client state until an admin saves them. |
| **Any change to `product_images`** | `alt_text` already exists — that half of the change stays migration-free (D3). |
| **Any change to `catalog_variants`, `catalog_product_images`, RLS policies, or grants** | Only `catalog_products` is replaced, and `CREATE OR REPLACE VIEW` preserves its existing grants. |
| Bulk / batch / "generate for all products" | D6. Cost and review-load guardrail. |
| Automatic generation on create, upload, or any public read path | D6. Public pages keep reading persisted columns exactly as today. |
| Gemini image *generation* (creating new images) | D2 covers image **input** (analysing an existing photo). Producing synthetic product photos is not in scope. |
| Any new runtime Python dependency (`google-generativeai` et al.) | D8. `httpx` is already in `backend/pyproject.toml`. |
| Live Gemini calls in CI | CI carries zero secrets (`ci-and-rls-tests` D2). Adapter is mock-transport tested. |
| Frontend-side AI calls | Forbidden by `openspec/config.yaml`. |

## Capabilities

### New Capabilities

- `gemini-generation`: the `ai` domain — port/adapter contract, backend-only
  invocation, key configuration, 503-when-unconfigured degradation, error and
  timeout mapping.
- `admin-ai-content-authoring`: the `content` domain and its admin surfaces —
  generate-description and generate-alt-text as **draft-returning, on-demand,
  single-item** operations behind a mandatory human review gate.

### Modified Capabilities

- `product-catalog-schema`: adds `products.short_description` and appends it to
  the `catalog_products` view (D3). The only schema delta in this change.
- `admin-product-management`: product create/edit now carries an optional
  short blurb **and** long body (today's requirements cover name/model/variants
  only).
- `admin-product-images`: `alt_text` becomes editable after upload — today's
  spec only sets it during upload.
- `product-persistence`: `Product` gains `description` and `short_description`;
  the repository port and both adapters (postgres + in-memory) must round-trip
  both, and adapter parity tests must cover them.
- `public-catalog-ui`: the catalog listing renders the short blurb, which it
  shows **no** product copy of today.

`/product/[slug]` already renders `description`, and
`catalog_product_images.alt_text` already flows to the frontend — for those two
surfaces only the *values* stop being null.

## Approach

Exploration **Approach 4**, extended to image input per D2. `ai` ships the
Gemini seam; `content` owns generation orchestration and is its only consumer;
`products` remains the sole owner of its own tables (D4). Dependency direction is
`content -> ai` and `content -> products`, never the reverse — the same
unidirectional convention as the existing `stock -> products`.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **Scope is `content` + `ai` only.** `content` = AI-assisted product copy authoring; `ai` = the shared Gemini client adapter `content` calls. **`recommendation` is OUT** — deferred to a later "dominios part 2" change. Do not scaffold or touch it. |
| D2 | **Both Gemini capabilities are in scope**: *text* for product descriptions, and *image input* for AI-generated alt text on existing product photos. Alt text is editable/approvable on the same terms as descriptions. |
| D3 | **Exactly one small additive migration, and no `content` table.** Product copy is **two** fields (OQ1, answered by the user 2026-08-17): <br>• `products.description` — **existing column, reused as-is, NOT renamed** — is the **long detail body** rendered on `/product/[slug]`. This is exactly what it means and where it renders today, so there is no rename, no backfill, and no regression. <br>• `products.short_description` — **the one genuinely new column** (nullable `text`) — is the **short catalog-listing blurb**. <br>• `product_images.alt_text` — **existing column, unchanged.** <br>The migration is: `alter table products add column short_description text` (nullable, no default → metadata-only, no table rewrite, matching `20260811000000_products_soft_delete.sql`'s pattern) plus a `create or replace view catalog_products` that **appends** the new column. **No `content` table, no `content` schema, no draft/version/audit table** — that half of the original D3 stands (see OQ3). |
| D4 | **`products` owns persistence; `content` owns generation.** The `description` field and the alt-text update path live in the `products` domain (the aggregate owner). `content` never issues SQL against products' tables and never owns a repository for them. |
| D5 | **Human review gate is mandatory and is the whole publish gate.** A generate call MUST have **no write side effect** — it returns a draft to the admin UI. Persistence happens only through a separate, explicit admin save. No AI output ever reaches a publicly-readable column without an admin pressing save. Both fields stay fully hand-editable/typeable. |
| D6 | **On-demand, admin-triggered, one item at a time.** No bulk generate, no generation on product create or image upload, no generation from any public or unauthenticated route. Every Gemini call sits behind the existing admin JWT guard. |
| D7 | **Graceful degradation is a hard requirement.** `GEMINI_API_KEY` is read from the environment (`config.py`, `os.environ`, no dotenv lib — repo convention) and gated by a `require_gemini`-style dependency scoped to the AI endpoints **only**. With the key unset: the app starts, `/health` passes, the entire public catalog works, and the entire existing admin panel works — only the two "Generate" actions return 503. No key value in the repo; **no `NEXT_PUBLIC_` twin, ever**; calls are backend-only. |
| D8 | **No new runtime dependency.** The Gemini adapter is a thin hand-rolled `httpx` client (already a dependency), matching the repo's explicit rejection of `supabase-py` for `supabase_storage.py`. `httpx` stays confined to `infrastructure/`; `ai/domain/` stays pure and keeps passing `test_domain_boundary.py`. |
| D9 | **`ai` is a leaf domain.** `ai/` MUST NOT import from `content/`, `products/`, or `stock/`. `content -> ai` and `content -> products` are the only new legal edges; nothing imports `content`. |
| D10 | **ONE generate-copy action produces BOTH text fields in a SINGLE Gemini call**, returning a `{short_description, description}` draft pair — not two separate actions and not two calls. Rationale: (a) D6's cost guardrail — one admin click must stay one paid call, not two; (b) the blurb must be a consistent condensation of *that* body, not an independently generated second take that contradicts it. The admin can still edit either field independently, and save either one, before publishing (D5). **Alt-text generation stays a separate action** — different input modality (image), different target row, different admin surface. |

D1–D2 confirmed by the user on 2026-08-17 via AskUserQuestion.
D3's two-field shape confirmed by the user on 2026-08-17 (OQ1); OQ2 and OQ3
confirmed the same day.
D4–D10 follow from exploration plus repo conventions **verified directly against
the schema and source** during this phase.
**D1–D10 must not be reopened** by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

### Deferred to Design — must be decided **explicitly**, not silently picked

| # | Decision `sdd-design` owns |
|---|---|
| DD1 | **How the photo reaches Gemini for alt text.** `shared/application/object_storage.py` exposes **only `put` and `delete` — there is no read method**. Design must choose: (a) add `get(path) -> bytes` to the port + `SupabaseStorage`, or (b) hand Gemini the public object URL (the `product-photos` bucket already grants `anon` SELECT). Genuine tradeoff: bandwidth/coupling and mock-transport testability vs. handing a third party a direct object URL. Unresolved. |
| DD2 | **The `content -> products` seam.** Does `content` call products' use cases directly, or depend on a narrow port declared in `content/application/` and implemented by a products-backed adapter? Both respect D4 and D9; this picks the coupling shape and the test doubles. |
| DD3 | **Alt-text update route shape.** No update endpoint exists today. New `PATCH /admin/products/{id}/images/{image_id}` vs. extending an existing route; must reuse the `admin-product-images` ownership/IDOR guard ("Image Ownership Is Checked At The Use-Case Layer"). |
| DD4 | **Failure, timeout, and validation policy.** Timeout, retry-or-not, and the route-layer status mapping for a Gemini failure — the repo already has a precedent pair (`503 storage_unavailable` for unconfigured, `502 ObjectStorageError` for a failed call). Also: model/version pinning, draft length caps, and what an empty or refusal response does. Must be deterministic under `httpx.MockTransport` with no live network in CI. |
| DD5 | **Whether to harden `backend/tests/architecture/test_domain_boundary.py`** into an automated cross-domain **directionality** check. It currently enforces only banned imports inside `domain/`; the `stock -> products` rule lives in docstrings alone. This change adds two more legal edges (D9), which is the point where convention-only starts to cost. Design's call, but it must be an explicit one. |
| DD6 | **How the two-field draft pair (D10) is extracted from one model response.** Structured/JSON output mode with a response schema vs. delimiter or heading parsing. Must also define partial-output behaviour: what happens when the model returns a body but no blurb (or vice versa) — is that a 502-class failure, or a draft with one empty field the admin fills in? Interacts with DD4's validation and length caps, which now need **two** caps (a listing blurb has a much tighter budget than a detail body). |
| DD7 | **How `catalog_products` is replaced.** `CREATE OR REPLACE VIEW` can only **append** columns, so `short_description` lands after `created_at` — cosmetically odd next to `description`, but it preserves grants and matches the precedent set by `20260811000000_products_soft_delete.sql`. The alternative (`DROP VIEW ... CASCADE` + recreate for a tidy column order) **drops and must re-issue the `anon`/`authenticated` GRANTs** and is a strictly riskier operation on the only public read surface. Design must pick deliberately, and must keep `lib/catalog/columns.ts`, `CatalogProductRow`, and the new view in exact agreement — `columns.ts` documents itself as "exactly matching the columns each view actually selects", and a source-grep test enforces that no query uses `select("*")`. |

### Supabase / Gemini Impact (per `openspec/config.yaml` rules)

- **Supabase schema/migration impact: ONE small additive migration** (D3) —
  the first schema change since `20260811000000_products_soft_delete.sql`:
  - `alter table products add column short_description text` — nullable, no
    default, so it is a **metadata-only ALTER with no table rewrite**, exactly
    like the soft-delete migration's `deleted_at`.
  - `create or replace view catalog_products` appending `short_description`
    (see DD7). **No policy change, no grant change** — `CREATE OR REPLACE VIEW`
    preserves the existing `anon`/`authenticated` GRANT.
  - **No new table.** No `content` schema, no draft/version/audit table (D3,
    OQ3). `products.description` and `product_images.alt_text` are reused
    exactly as they exist today.
  - `catalog_variants`, `catalog_product_images`, `variant_stock_levels`, all
    RLS policies, and every base table other than `products` are untouched.
- **Gemini API usage: FIRST INTRODUCTION.** Invoked **backend-only**, from
  `ai/infrastructure/` via a `content` use case, reached only through
  admin-authenticated FastAPI routes (D6). Never from the Next.js client, never
  from a public route, never automatically. First external paid API and first
  non-Supabase secret in this repo (D7).

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/ai/{application,infrastructure}/` | **New** | Gemini port + thin httpx adapter. Currently empty scaffold. |
| `backend/src/gcell/content/{domain,application}/` | **New** | Generate-description and generate-alt-text use cases. Currently empty scaffold. |
| `backend/src/gcell/shared/infrastructure/config.py`, `dependencies.py` | Modified | `GEMINI_API_KEY` getter + `require_gemini` 503 guard (D7). |
| `backend/src/gcell/products/domain/product.py` | Modified | Adds `description: str \| None` and `short_description: str \| None`. |
| `backend/src/gcell/products/application/{create,update}_product.py`, `repository.py` | Modified | Carry both text fields through; alt-text update path (DD3). |
| `backend/src/gcell/products/infrastructure/postgres_product_*.py`, `in_memory_*` | Modified | Round-trip both fields; adapter parity tests must follow. |
| `backend/src/gcell/api/admin.py` | Modified | Both text fields on product read/write models; new generate + alt-text routes. |
| `frontend/src/app/(admin)/admin/products/product-form.tsx`, `actions.ts` | Modified | Two copy fields + one "Generate copy" trigger (D10). |
| `frontend/src/app/(admin)/admin/products/image-manager.tsx` | Modified | Editable alt text + "Generate alt text". |
| `supabase/migrations/<new>.sql` | **New** | **One migration** (D3): `products.short_description` + `create or replace view catalog_products`. |
| `frontend/src/lib/catalog/columns.ts` | Modified | `CATALOG_PRODUCT_COLUMNS` pins the view's column list and must gain `short_description` — a source-grep test forbids `select("*")`, so this is not optional. |
| `frontend/src/lib/catalog/types.ts` | Modified | `CatalogProductRow` mirrors the view column-for-column. |
| `frontend/src/app/(public)/catalog-listing-content.tsx` | Modified | Renders the blurb — shows no product copy today. |
| `frontend/src/app/(public)/product/[slug]/page.tsx` | **Unchanged** | Already renders `description` (the long body). |
| `frontend/src/app/api/catalog/route.ts`, `lib/catalog/queries.ts` | Possibly Modified | Only if the listing's fetch path needs the new column threaded through. |
| `backend/src/gcell/recommendation/` | **Unchanged** | Stays empty (D1). |
| `.env.example` | **New (probable)** | Does not exist today despite `config.py` referencing it; `GEMINI_API_KEY` is a good reason to add it. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hallucinated spec/price/material claims published as store copy — a real liability for an e-commerce site | **High if ungated** | D5 makes the review gate structural: generation has no write path at all. Reviewer must confirm no generate handler touches a repository. |
| `GEMINI_API_KEY` leaks into the frontend bundle or a committed file | Low, **highest severity** | D7: backend-only, no `NEXT_PUBLIC_` twin, mirrors the `SUPABASE_SERVICE_ROLE_KEY` posture already enforced by `test_frontend_service_role_boundary.py`. Consider extending that test to `GEMINI`. |
| Unbounded spend on a paid API | Medium | D6: admin-authenticated, on-demand, one item per call, no bulk, no public trigger. |
| App breaks for everyone when the key is unset or Gemini is down | Medium | D7: scoped 503 guard only on AI endpoints; public catalog and existing admin flows must be proven unaffected. |
| Flaky/expensive tests if the adapter hits the real API | Medium | DD4 must pin mock-transport testing; CI has zero secrets by prior decision. |
| Adding two text fields to `Product` silently breaks existing constructors, adapters, and ~dozens of tests | **High** | Make both optional with defaults; adapter-parity tests already exist and will catch a half-wired field. |
| The `catalog_products` view, `CATALOG_PRODUCT_COLUMNS`, and `CatalogProductRow` drift apart — a mismatch breaks **every** public catalog read, not just the blurb | Medium, **high blast radius** | DD7 makes the replacement strategy explicit. All three must change in the same slice; the existing `queries.test.ts` grep guard and `next build`'s typecheck both bite here. |
| `DROP VIEW ... CASCADE` used for a tidy column order silently drops the `anon`/`authenticated` GRANT, taking the public catalog offline | Low, **severe** | DD7 defaults to `CREATE OR REPLACE VIEW` (append-only), which preserves grants. The archived RLS suite (`test_rls_policies.py`) asserts anon can read the catalog views and would catch this in CI. |
| Scope creep: two domains, two generation flows, two admin surfaces, one new write path | **High** | See Delivery Forecast — chaining is likely mandatory here. |

## Rollback Plan

Revert the commit(s). The change is **additive**: `products.description` and
`product_images.alt_text` simply return to being null/write-once exactly as
today, and any values an admin already approved remain valid, human-reviewed
text that the public pages keep rendering.

The one migration (D3) is the only piece that is not a plain code revert, and it
is deliberately the cheapest possible kind. Rolling **forward** is preferred:
leave `products.short_description` in place (a nullable column nothing reads
costs nothing) and revert only the view. If the view must go back, that is
another `create or replace view catalog_products` restoring the
`20260811000000_products_soft_delete.sql` definition verbatim — no data loss,
grants preserved. Dropping the column is possible but pointless and would
discard any blurbs an admin already wrote.

Partial rollback is available and cheap because the seams are independent:
deleting the `ai` adapter and the generate routes removes **all** Gemini exposure
while leaving the (independently valuable) manual `description` and alt-text
editing in place. Unsetting `GEMINI_API_KEY` is an even faster kill switch that
requires no deploy of code (D7) — the generate buttons return 503 and everything
else keeps working.

## Dependencies

- **A Google Gemini API key and a billing-enabled Google account** — a real
  external prerequisite, and the first in this repo. `sdd-apply` cannot verify a
  live call without it; D7 exists precisely so the absence is not a blocker.
- `admin-authentication` / `admin-api-access` — supply the JWT guard every
  generate route sits behind (D6). Shipped.
- `product-media-storage` — supplies the stored photos alt text is generated
  from, and the bucket DD1 must read from or link to. Shipped.
- `product-catalog-schema` — supplies both target columns. Shipped; **not
  modified** (D3).

## Delivery Forecast

**High risk of exceeding the 400-line review budget**, and higher than before
the two-field answer. This change spans two new domains, a new external adapter,
a new config/secret seam, a **migration plus a public-view replacement**, two
fields threaded through domain → use case → two repository adapters → API, the
pinned frontend column allowlist, a public listing surface, a brand-new alt-text
update route, and two admin UI surfaces.

`sdd-tasks` MUST produce a real forecast and should expect to chain. The natural,
independently-green, independently-revertable slices are:

1. **Migration + both text fields end-to-end**, manual authoring only, no AI at
   all: `short_description` column, `catalog_products` replacement (DD7),
   `columns.ts`/`CatalogProductRow`, `Product` gains both fields, adapters,
   API, admin form, and the listing blurb. Closes the biggest existing hole and
   ships value even if Gemini never lands. If this alone busts the budget, the
   natural sub-split is **1a** the migration + view + pinned-column/type
   alignment (schema and frontend contract only, no behaviour), then **1b** the
   backend write path and admin form.
2. The alt-text update path (DD3), still manual.
3. `ai` domain: Gemini port + httpx adapter + config + `require_gemini` guard,
   mock-transport tested, wired to nothing.
4. `content` domain: the generate-copy use case (D10), the generate-alt-text use
   case, their routes, and the two admin "Generate" triggers.

Do not pre-commit to this shape here — but note slices 1 and 2 have **zero**
Gemini dependency, which makes them safe to land before any key exists.

## Success Criteria

- [ ] An admin can write a **short blurb** and a **long body** by hand, see the
      blurb on the catalog listing and the body on `/product/[slug]` — with
      `GEMINI_API_KEY` unset.
- [ ] An admin can edit the alt text of an **already-uploaded** image (not
      possible today at all).
- [ ] **One** "Generate copy" action returns **both** drafts from **one** Gemini
      call (D10); "Generate alt text" is a separate action.
- [ ] Every generate call returns a draft the admin can edit and must explicitly
      save; no generate call writes to the database or storage (D5).
- [ ] The migration is exactly one new nullable column plus a
      `catalog_products` replacement — no new table, no policy change, no grant
      change (D3), and `anon` can still read all three catalog views afterwards.
- [ ] `CATALOG_PRODUCT_COLUMNS`, `CatalogProductRow`, and the `catalog_products`
      view agree column-for-column; no query uses `select("*")`.
- [ ] Every Gemini call originates in `ai/infrastructure/`, is reached only
      through an admin-authenticated backend route, and no Gemini call, key, or
      SDK reference exists anywhere under `frontend/` (D6, D7).
- [ ] With `GEMINI_API_KEY` unset: app boots, `/health` passes, the full public
      catalog works, the full existing admin panel works, and only the two
      generate endpoints return 503 (D7).
- [ ] `backend/src/gcell/recommendation/` is still empty (D1).
- [ ] `test_domain_boundary.py` passes: no banned import in any `domain/` layer,
      including the new `content/domain/` and `ai/domain/`.
- [ ] `backend/pyproject.toml` gains no new runtime dependency (D8).
- [ ] Both pinned suites stay green: `npm --prefix frontend test` and
      `uv run --project backend pytest -q`.

## Open Questions

**All three are RESOLVED by the user on 2026-08-17. None remain open.**

| # | Question | Resolution |
|---|---|---|
| OQ1 | Is product copy a single free-text field, or two (short listing blurb + long detail body)? | **RESOLVED — two fields.** The user chose the two-field shape over the single-field zero-migration default. This **reopened and revised D3**: `products.description` becomes the long body, `products.short_description` is added. Folded into D3 and D10; **no longer open**. |
| OQ2 | What grounding data should the copy prompt receive — does price go in? | **RESOLVED — no price in the prompt.** Matches the proposed default, so D5/D6 stand unchanged. Name, model, and variant colors are available; price is excluded to avoid generated copy making price claims that go stale on the next variant edit. `sdd-design` may refine the remaining prompt inputs within D5/D6 but MUST NOT add price. |
| OQ3 | Does regenerating need a history/version trail? | **RESOLVED — no history.** Matches the proposed default. A draft is transient client state until the admin saves it. This is why D3's "no `content` table, no draft/version/audit table" half survives untouched. |
