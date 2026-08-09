# Design: Initial Scaffolding

## Technical Approach

Two independent toolchains under one repo root, each scaffolded by its official generator and pruned to scope. Frontend = Next.js App Router + Serwist service worker whose runtime-caching matrix is decided now (spec: *PWA Runtime-Caching Strategy Decision*). Backend = uv + FastAPI with a screaming/hexagonal package tree for 6 domains and one worked domain (`products`). `supabase init` only. `openspec/config.yaml` gains two pinned commands, which is what actually unblocks Strict TDD.

## Architecture Decisions

### Decision: Serwist runtime-caching matrix (per asset class, order-sensitive)

**Choice**: not one strategy — a matcher list evaluated in order, prepended to `defaultCache`.

| Request class | Strategy | Rationale |
|---|---|---|
| `/admin/*` or any non-GET | `NetworkOnly` | Authenticated/private responses must never land in a shared cache. Must be **first** or later matchers would capture them. |
| Catalog navigations `/`, `/catalog/*`, `/product/*` (HTML + RSC) | `NetworkFirst`, `networkTimeoutSeconds: 3` | Price/stock correctness beats instant paint while online; the 3s timeout still yields the cached page on a bad mobile link, and the cache is the offline fallback. |
| `/api/catalog/*` JSON reads | `StaleWhileRevalidate` | Small payloads, instant render, background refresh; staleness window is one navigation. |
| Supabase Storage public objects | `CacheFirst` + expiration (120 entries / 30d) + `CacheableResponsePlugin({statuses:[0,200]})` | Product images are large and effectively immutable per URL; re-uploads get new paths. Status `0` is required for opaque cross-origin responses. |
| `/_next/static`, `/_next/image`, fonts | inherited `defaultCache` | Already correct (content-hashed immutable / SWR); do not re-implement. |

**Alternatives considered**: `StaleWhileRevalidate` for catalog pages (rejected — can paint a stale price to an online buyer); `CacheFirst` for pages (rejected — needs manual invalidation the app has no signal for); `defaultCache` only (rejected — leaves `/admin` and Supabase Storage unhandled, exactly the rework this change must avoid).

**Rationale**: offline catalog browsing is a confirmed near-term goal, so the cache must be page-shaped, not shell-shaped; freshness-first with cache fallback delivers offline reads without ever showing a stale price online.

```
fetch event
  ├─ /admin/* or method != GET ─────────► NetworkOnly            (never cached)
  ├─ /, /catalog/*, /product/* ─────────► NetworkFirst(3s) ──► catalog-pages
  ├─ /api/catalog/* ────────────────────► StaleWhileRevalidate ─► catalog-api
  ├─ *.supabase.co/storage/v1/object/public/* ► CacheFirst ────► catalog-images
  └─ (fallthrough) ─────────────────────► defaultCache          (_next/*, fonts)
```

Placeholder-safe: matchers reference URL contracts (`/catalog`, `/product`, `/admin`), not files, so they hold when real routes land. **Admin URL contract pinned here**: the `(admin)` route group serves under `/admin/*`; `(public)` serves catalog at `/` and `/catalog/*`.

### Decision: Supabase migration naming = CLI default, not `0001-0004`

**Choice**: `supabase migration new <snake_name>` → `supabase/migrations/<YYYYMMDDHHMMSS>_<name>.sql`.
**Alternatives considered**: hand-numbered `0001_*.sql` (rejected — the CLI does not generate it, ordering breaks across branches, and `db diff`/`db push` fight it).
**Rationale**: `0001-0004` was informal chat notation, never a requirement. Mapping for the future schema change:

| Chat shorthand | `migration new` name | Contents |
|---|---|---|
| 0001 | `products_catalog` | products + variants + images |
| 0002 | `stock_movements` | stock + movements |
| 0003 | `content_styles` | content + styles |
| 0004 | `rls_public_views` | RLS policies + public views |

### Decision: `serwist` v9 replaces `@serwist/sw`

The proposal named `@serwist/sw`; in Serwist v9 that package was folded into `serwist`. Install `serwist` + `@serwist/next` only.

### Decision: `shared/` also gets `application/`

The spec requires all 6 domains to expose all three layers. `shared/application/` ships as an empty package (`__init__.py`) so the scenario passes; real shared code lives in `shared/domain/` and `shared/infrastructure/`.

## Pinned Versions

Design-time pins (best known stable). **`sdd-tasks`/`sdd-apply` MUST re-verify latest stable at install time and record the exact resolved versions in `package.json`/`pyproject.toml` + lockfiles** — these are a drift baseline, not frozen forever.

| Frontend | Pin | Backend | Pin |
|---|---|---|---|
| Next.js | 16.x (React 19.2) | Python | 3.13 (floor 3.12) |
| TypeScript | 5.9.x | uv | 0.9.x |
| Tailwind CSS | 4.1.x | FastAPI | 0.118+ |
| shadcn CLI | `shadcn@latest` (3.x) | pytest | 8.4.x |
| serwist / @serwist/next | 9.2.x | pytest-asyncio | 1.2.x (`asyncio_mode=auto`) |
| Vitest / @vitejs/plugin-react | 3.2.x / 5.x | httpx | 0.28.x |
| @testing-library/react / jest-dom / jsdom | 16.3.x / 6.6.x / 26.x | ruff | 0.14.x |

## File Changes

| File | Action | Description |
|---|---|---|
| `frontend/next.config.ts` | Create | `withSerwist({ swSrc: "src/app/sw.ts", swDest: "public/sw.js" })` |
| `frontend/src/app/sw.ts` | Create | `new Serwist({ precacheEntries: self.__SW_MANIFEST, skipWaiting, clientsClaim, navigationPreload, runtimeCaching: [...catalogRuntimeCaching, ...defaultCache] })` |
| `frontend/src/lib/pwa/runtime-caching.ts` | Create | The matcher matrix above (`RuntimeCaching[]`) |
| `frontend/public/manifest.webmanifest` | Create | Installable shell metadata |
| `frontend/src/app/layout.tsx` | Modify | `metadata.manifest` + theme color |
| `frontend/vitest.config.ts`, `vitest.setup.ts` | Create | jsdom env, `@testing-library/jest-dom` |
| `frontend/src/components/ui/__tests__/button.test.tsx` | Create | RTL example test on the shadcn Button |
| `backend/pyproject.toml`, `uv.lock` | Create | uv project, deps, `[tool.pytest.ini_options]`, ruff |
| `backend/src/gcell/main.py` | Create | FastAPI app + `GET /health` → `200 {"status":"ok"}` |
| `backend/src/gcell/{products,stock,content,ai,recommendation,shared}/{domain,application,infrastructure}/__init__.py` | Create | 6 domains × 3 layers |
| `backend/src/gcell/products/domain/product.py` | Create | Pure dataclass + invariants, zero framework imports |
| `backend/src/gcell/products/application/`, `infrastructure/` | Create | Use-case + in-memory repo adapter |
| `backend/tests/products/test_product_domain.py` | Create | Pure-domain unit test |
| `backend/tests/test_health.py` | Create | `TestClient` integration test |
| `supabase/config.toml` | Create | `supabase init` output, no SQL |
| `openspec/config.yaml` | Modify | `testing:` block + `rules.apply.test_command` / `rules.verify.*` |
| `.gitignore` | Modify | Node + Python + Supabase entries |

## Interfaces / Contracts

- `GET /health` → `200 application/json {"status": "ok"}`. No auth, no DB dependency (must stay green before Supabase exists).
- Hexagonal rule: `**/domain/**` imports only stdlib + same-domain `domain`. No `fastapi`, `pydantic`, `supabase`, `sqlalchemy`, `httpx`.

## Pinned Test Commands (`openspec/config.yaml`)

```yaml
testing:
  status: implemented
  runner_command: "npm --prefix frontend test && uv run --project backend pytest -q"
  frameworks:
    frontend: "Vitest + @testing-library/react (jsdom)"
    backend: "pytest + pytest-asyncio + httpx (fastapi.testclient)"
  layers: { unit: available, integration: available, e2e: unavailable }
  coverage: { available: false, command: null }
  quality_tools: { linter: "eslint / ruff", type_checker: "tsc --noEmit", formatter: "ruff format" }
```

Frontend: `npm --prefix frontend test` (script = `vitest run`). Backend: `uv run --project backend pytest -q`. Both are root-relative and PowerShell-safe.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit (FE) | shadcn Button renders | Vitest + RTL |
| Unit (BE) | `products` domain invariants | pytest, no fixtures/framework |
| Integration (BE) | `/health` = 200 `{"status":"ok"}` | `fastapi.testclient.TestClient` |
| Boundary | `domain/` import purity | pytest walking `domain/` ASTs for banned imports |
| E2E | — | Out of scope (no Playwright) |

## Threat Matrix

N/A — the delivered code contains no shell commands, subprocesses, git/PR automation, or executable-file classification. Generator commands run once at apply time, not at runtime. The one security-relevant boundary is service-worker request routing, handled by the `NetworkOnly` `/admin/*` + non-GET rule above, which `sdd-tasks` MUST carry as a RED test (an `/admin` request never writes to a cache).

## Migration / Rollout

No data migration. Purely additive; rollback is deleting the three new directories and reverting two files.

## Open Questions

None blocking.
