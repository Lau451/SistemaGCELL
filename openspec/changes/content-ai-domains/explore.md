# Exploration: content/ai/recommendation domains (Gemini AI integration)

## Current State

- Backend `backend/src/gcell/{content,ai,recommendation}/{domain,application,infrastructure}/` exist as EMPTY scaffolds (only `__init__.py` files, zero logic) since `2026-08-09-initial-scaffolding`. That change's proposal explicitly listed "Gemini AI integration" as Out of Scope and its design.md pinned only `products`/`stock` as worked domains.
- `openspec/config.yaml` (always-loaded project context) already bakes in: `AI: Google Gemini API (image + text), backend-only calls`, plus rules requiring proposals to "note any new Gemini API usage" and apply guidelines to "keep AI (Gemini) calls backend-only, never from the Next.js client." This is a pre-existing architectural commitment, not something to invent.
- No Gemini/`google-generativeai` dependency, key, or `.env.example` exists anywhere in the repo yet (`backend/pyproject.toml` has no AI SDK). No third-party AI API client precedent exists; the only external-API adapter precedent is `shared/infrastructure/supabase_storage.py` — a thin hand-rolled `httpx` adapter over a REST API (rejected the official SDK to avoid extra deps), config resolved via `shared/infrastructure/config.py` (`os.environ` reads, no dotenv lib) and gated via a `require_*` FastAPI dependency pattern (`shared/infrastructure/dependencies.py`, e.g. `require_storage` -> 503 if unconfigured). A Gemini adapter would naturally follow this exact shape: `shared/infrastructure/gemini_client.py` (or under `ai/infrastructure/`) + `GEMINI_API_KEY` in `config.py` + a `require_gemini` guard.
- Concrete gap already in the DB schema: `products.description` (nullable `text`) exists since `20260810000449_products_catalog.sql`, is exposed through the public catalog view, and IS rendered on `/product/[slug]` (`frontend/src/app/(public)/product/[slug]/page.tsx`) via `CatalogProductRow.description`. But it is completely unwired on the write side: absent from the backend `Product` domain dataclass (`products/domain/product.py`), absent from `create_product.py`/`update_product.py` use cases, and absent from the admin `ProductForm` (`frontend/src/app/(admin)/admin/products/product-form.tsx` has Name/Model/Variants only, no description field). Today the only way to populate it is direct DB access. This is a real, pre-existing hole a "content" domain could close.
- No "similar products" / "customers also viewed" UI exists anywhere in the frontend catalog (grep for recommend/similar/related found no such surface) — a "recommendation" domain would be additive, not replacing anything.
- Domain dependency convention: `stock -> products` is the only legal cross-domain direction, documented via code docstrings (e.g. `stock/application/create_stocked_product.py`) and referencing `backend/tests/architecture/test_domain_boundary.py`. That test currently only enforces the `domain/` layer import-purity rule (`DOMAINS = ["products","stock","content","ai","recommendation","shared"]`, `BANNED_MODULES` = fastapi/pydantic/supabase/sqlalchemy/httpx/asyncpg/PIL) — it does NOT currently enforce cross-domain directionality as an automated check; that rule lives only in docstrings/convention today. A new `content`/`recommendation` domain reading from `products` would need the same "depends on products, never reverse" convention, and possibly a follow-up hardening of that architecture test to check directionality automatically.

## Affected Areas

- `backend/src/gcell/content/` — currently empty; candidate home for product description/marketing-copy generation and storage.
- `backend/src/gcell/ai/` — currently empty; candidate home for the Gemini client port/adapter shared by `content` and `recommendation` (or the Gemini adapter could live in `shared/infrastructure/` instead, mirroring `supabase_storage.py`).
- `backend/src/gcell/recommendation/` — currently empty; candidate home for "similar products" / "customers also viewed" logic.
- `backend/src/gcell/products/domain/product.py`, `products/application/{create_product,update_product}.py` — would need a `description` field if content domain writes back to `products.description` directly rather than owning a separate table.
- `frontend/src/app/(admin)/admin/products/product-form.tsx` — needs a description field (manual and/or "Generate with AI" trigger) if scope includes admin content authoring.
- `frontend/src/app/(public)/product/[slug]/page.tsx`, `catalog-listing-content.tsx` — the surfaces that would render new content/recommendation output.
- `backend/src/gcell/shared/infrastructure/config.py`, `dependencies.py` — where a `GEMINI_API_KEY` config getter + `require_gemini` guard would follow existing patterns.
- `backend/tests/architecture/test_domain_boundary.py` — the `DOMAINS` list already anticipates all three domains; may need a directionality check added.
- `supabase/migrations/` — no `content`/`ai`/`recommendation` schema exists yet at all (design.md's "0003 content_styles" was only informal chat-shorthand naming for a migration that was never authored — no such migration exists).

## Approaches

1. **Content domain = AI-assisted product description authoring** — admin writes/generates `products.description` (or a new `content` table) via Gemini text generation, editable before publish.
   - Pros: closes a real, already-schema-scaffolded gap; small, well-bounded first slice; clear backend-only Gemini call point (admin action); reuses existing `description` column with zero migration needed if scope stays at that column.
   - Cons: doesn't touch `ai`/`recommendation` domains at all in v1; "AI-generated" text needs an admin review/edit step to avoid publishing hallucinated claims (spec, price, or material claims).
   - Effort: Low–Medium.

2. **Recommendation domain = "similar products" / "customers also viewed"** — Gemini (or simple heuristic: same model/category) drives a related-products rail on `/product/[slug]` and/or catalog listing.
   - Pros: clear customer-facing catalog UX improvement; natural fit for `recommendation` domain scaffolding already present.
   - Cons: needs either interaction/view data (none currently tracked) or falls back to attribute-similarity heuristics that may not need Gemini at all (risk: "needs Gemini" may be over-scoped for this if a simple SQL/heuristic gets 80% of the value); harder to test deterministically if LLM-driven.
   - Effort: Medium.

3. **AI domain = shared Gemini client port + one or both of the above as first consumer(s)** — build the `ai` domain purely as the adapter layer (Gemini text/image client, following the `supabase_storage.py` thin-httpx-adapter pattern), with `content` and/or `recommendation` as the first callers.
   - Pros: matches `openspec/config.yaml`'s existing framing exactly ("AI: Google Gemini API (image + text), backend-only calls"); avoids duplicating Gemini wiring if both content and recommendation eventually need it; keeps `ai/domain` free of any Gemini SDK import per the hexagonal boundary test.
   - Cons: building the adapter with no concrete consumer yet risks over-engineering/YAGNI; better to build it alongside whichever of options 1/2 is chosen first.
   - Effort: Low (adapter alone) but should be paired with a consumer, not shipped standalone.

4. **Combine 1+3 as the smallest coherent v1 slice**: `ai` domain ships the Gemini text-generation adapter; `content` domain owns the description-authoring use case (admin triggers "Generate description" -> Gemini text call -> admin edits/approves -> saved to `products.description` via a `Product.description` field added to the domain); `recommendation` stays deferred to a later change.
   - Pros: single Gemini call type (text) reduces surface area vs. also doing image generation/analysis; ships all 3 domains something real without recommendation's harder "no interaction data yet" problem; still respects `stock -> products` style unidirectional dependency (`content -> products`, never reverse).
   - Cons: still leaves `recommendation` domain empty after this change (would need explicit framing as "domains, part 1" if the user wants all three touched now).
   - Effort: Medium.

## Recommendation

Ask the user to pick the concrete scope before proposing, since this is a genuine product-scope fork with real tradeoffs, not a technical detail:

1. Should this change deliver ALL THREE domains (content + ai + recommendation) or is landing `content` + `ai` (description authoring) as slice 1 acceptable, with `recommendation` explicitly deferred to a later "dominios part 2" change?
2. For Gemini's "image" capability (already named in `openspec/config.yaml`): is there an image-related use case in scope (e.g. AI-assisted alt-text generation for product photos, which already exist and are stored) or is text-only (descriptions) sufficient for this slice?
3. For `recommendation` (if included): should it be Gemini-driven, or a simpler attribute-similarity heuristic (same model/color-family) that doesn't require an LLM call at all — given no view/interaction tracking exists to feed a real recommender?

Approach 4 (content + ai, text-only, recommendation deferred) is the safest smallest-first-slice recommendation if the user wants a quick decision, because it closes a real existing schema gap (`products.description` is dead today) and matches the config.yaml's stated Gemini framing without requiring new tracked interaction data recommendation would need.

## Risks

- `openspec/config.yaml` commits to Gemini for both "image and text" — scoping only text in slice 1 needs explicit user sign-off since it's a partial delivery against that stated intent.
- No automated cross-domain directionality check exists yet (`test_domain_boundary.py` only checks banned imports in `domain/`, not the `stock -> products`-style allowed-direction rule) — a new `content -> products` or `recommendation -> products` dependency would rely on convention/docstrings alone unless `sdd-design` decides to harden that test.
- Admin-facing "Generate with AI" description flow needs an explicit human-review/edit gate before publish — publishing unreviewed LLM text as product copy is a real content-quality/liability risk for an e-commerce store.
- Gemini API key/secrets handling has zero precedent in this repo yet (first external paid API, first non-Supabase secret) — needs its own config/secrets decision in `sdd-design` (rate limiting, cost control, error/timeout fallback so `/product/[slug]` never breaks if Gemini is down).
- `recommendation` domain has no interaction/view-tracking data source today; if the user wants a real (non-heuristic) recommender, that's a bigger scope than "content" and may need its own exploration/proposal cycle.

## Ready for Proposal

No — needs one clarifying decision from the user first: which of the three domains (or which combination) this change actually delivers, and whether Gemini's "image" capability is in scope for this slice. Once that's confirmed, `sdd-propose` can proceed directly from this exploration.
