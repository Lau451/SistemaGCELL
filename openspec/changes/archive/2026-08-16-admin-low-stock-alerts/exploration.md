## Exploration: admin-low-stock-alerts

### Current State
- `GET /admin/stock` (`backend/src/gcell/api/admin.py:542-561`) composes `ListCatalogStockLevelsUseCase` (`backend/src/gcell/stock/application/list_catalog_stock_levels.py`), flattening the catalog into per-variant rows with an optional `?below=N` clamp (`max(0, below)`) and optional case-insensitive substring search (AND-combined), sorted ascending by quantity. No pagination, no default threshold — `admin-stock-page`'s D1 explicitly rejected a fixed default.
- `CatalogStockLevelsReader.quantities_for_variants()` (`backend/src/gcell/stock/application/catalog_stock_levels_reader.py`) is the reusable bulk-read port with a totality contract (one entry per requested id, `0` for zero-movement variants).
- Frontend: `frontend/src/app/(admin)/admin/stock/page.tsx` (Server Component) fetches `frontend/src/app/api/admin/stock/route.ts` (proxy forwarding only `below`/`search`), renders a filterable table, zero-stock rows styled destructive with "Out of stock" label. Entirely passive — admin must navigate there manually.
- `frontend/src/app/(admin)/admin/layout.tsx` nav has two static links (Products, Stock), no badge/count mechanism.
- `frontend/src/app/(admin)/admin/page.tsx` (landing page) is explicitly minimal — its own comment states "no dashboard widgets" by design.

### Affected Areas
- `backend/src/gcell/api/admin.py` — `GET /admin/stock` route, reusable as-is
- `backend/src/gcell/stock/application/list_catalog_stock_levels.py` — reusable use case, already supports `below`
- `backend/src/gcell/stock/application/catalog_stock_levels_reader.py` — reusable bulk-read port
- `frontend/src/app/(admin)/admin/layout.tsx` — nav, candidate location for a badge
- `frontend/src/app/(admin)/admin/page.tsx` — landing page, explicitly "no dashboard widgets" today
- `frontend/src/app/api/admin/stock/route.ts` — proxy, only forwards `below`/`search`
- `supabase/config.toml` — Inbucket/`local_smtp` is Supabase Auth-only, not reusable transactional email

### Infra Check (concrete grep evidence)
- **Email**: grep for `smtp|nodemailer|sendgrid|resend|mailgun|inbucket` (case-insensitive) across the repo hits ONLY `supabase/config.toml` — `[local_smtp]` and a commented-out `[auth.email.smtp]` production SendGrid block. Both configure Supabase Auth's own email flow (magic links/password resets) via local Inbucket — not a general transactional email sender the app backend can call. `backend/pyproject.toml` dependencies: `asyncpg, fastapi, httpx, pillow, pyjwt[crypto], python-multipart` — no email SDK. `frontend/package.json` has no email dependency.
- **Cron/scheduler/queue**: grep for `cron|scheduler|APScheduler|celery|queue|worker|BackgroundTasks|pg_cron` (case-insensitive) across backend/frontend/supabase source returns zero real hits — matches were only in vendored skill tooling and PWA Service Worker files (unrelated "worker"). No `pg_cron` in `supabase/config.toml`, no FastAPI `BackgroundTasks` usage anywhere, no external queue.
- **Conclusion**: any periodic/push notification (email digest or similar) requires building BOTH an email integration and a scheduling mechanism from scratch. Nothing today is reusable for that.

### Approaches
1. **In-app badge/banner** — compute a low-stock count on admin page load, reusing `ListCatalogStockLevelsUseCase`/`CatalogStockLevelsReader` with `below=<threshold>`, render "Stock (3)" on the nav link.
   - Pros: zero new infra; reuses the existing bulk-read port/use case 100%; admin sees it passively on every panel visit (proactive relative to today); small, reviewable diff.
   - Cons: still panel-bound, not a true push notification; needs a threshold-default decision (see tension below); naive placement in `admin/layout.tsx` adds a DB round trip to every `/admin/*` route including ones that don't need it.
   - Effort: Low.
2. **Email digest (scheduled job)** — new cron/scheduler periodically emails a low-stock summary.
   - Pros: true push notification, works even when the admin isn't in the panel; matches the literal meaning of "alert."
   - Cons: requires building email sending AND job scheduling from scratch — secrets management, deliverability, retry/failure handling, rate-limiting — disproportionate infrastructure for a single-admin, low-traffic system.
   - Effort: High.
3. **On-demand "check now" trigger** — manual button/modal showing current low-stock rows without navigating to `/admin/stock`.
   - Pros: no new infra beyond (1).
   - Cons: still fundamentally reactive — doesn't solve "proactive"; marginal value over the already-shipped `/admin/stock?below=N` page.
   - Effort: Low.

### Recommendation
Option 1 (in-app badge). It's the only approach both genuinely more proactive than today's page and proportionate to a single-admin system with zero email/scheduler infrastructure — reuses 100% of what `admin-stock-page` already shipped, no new port/adapter, small diff. Option 2 satisfies "alert" literally but should be proposed as its own separately-scoped change later if genuinely wanted, given the real new-infrastructure cost. Option 3 barely improves on what already exists.

### Threshold-Default Tension (flag for proposal, not decided here)
`admin-stock-page`'s D1 rejected a fixed default threshold for the **triage page's list rendering**: "No fixed default threshold. Every variant is listed, sorted ascending by quantity. `?below=N` narrows further and is purely optional." That's correct for a browse view. A badge/alert concept is different — it needs SOME numeric cutoff to decide what counts as "low" without the admin specifying `?below=N` on every visit. This is a genuine reopening of the threshold framing, but scoped differently (badge default vs. page filter default), and must be surfaced as an explicit new decision — not silently decided here, and not framed as reversing D1.

### Open Questions for Proposal
1. What threshold defines "low stock" for the badge — a fixed number, an admin-configurable setting, or reuse of `below=0` (out-of-stock only)?
2. Does the badge live only on the "Stock" nav link, or also on `/admin` landing (currently explicitly "no dashboard widgets" by design)?
3. Compute the count on every admin page load (all `/admin/*` routes via `layout.tsx`) or scope it narrower to avoid an unconditional DB round trip?
4. Is email/push notification a real near-term requirement, or is an in-app badge sufficient for now?
5. Exact count ("Stock (3)") or a capped/qualitative indicator, given concurrent stock movements could make an exact count stale between render and click-through?

### Risks
- Reopening D1's threshold framing without explicitly framing it as a new, distinct decision risks scope conflict with the already-archived `admin-stock-page` change.
- Naive badge computation in `admin/layout.tsx` (wraps every `/admin/*` route) adds an unconditional DB round trip to pages that don't need it.
- If email is chosen later, it introduces the project's first outbound-email dependency and first scheduling mechanism — a materially larger surface than anything shipped since `admin-stock-page`.

### Ready for Proposal
Yes — recommend proposing Option 1 (in-app badge) as `admin-low-stock-alerts`.
