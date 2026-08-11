# Delta for platform-foundation

## MODIFIED Requirements

### Requirement: Backend Boot Establishes Database Connection Pool Lifecycle

The backend application MUST establish an asyncpg connection pool during
FastAPI lifespan startup, configured via a `DB_URL` value, and MUST close
that pool during lifespan shutdown. Pool creation MUST NOT be required for
endpoints, such as `/health`, that do not touch the database. Once any
router that consumes the pool (including the `/admin` router) is
registered, a request to one of that router's endpoints MUST fail fast
with `503 Service Unavailable` when the pool is missing or unavailable,
instead of proceeding with a `None` pool.
(Previously: tolerated `db_pool is None` indefinitely with no fail-fast
behavior for any consumer; this change adds the fail-fast/503 clause for
DB-touching endpoints, scoped as a per-request dependency guard rather than
a startup abort, so `/health` and other non-DB endpoints remain unaffected.)

#### Scenario: Pool opens on startup and closes on shutdown

- GIVEN a configured `DB_URL` pointing at a reachable Postgres instance
- WHEN the FastAPI app starts via its lifespan context
- THEN a connection pool MUST be created
- AND WHEN the app shuts down THEN the pool MUST be closed cleanly

#### Scenario: Health check still passes under the lifespan

- GIVEN the app is started through a context-managed `TestClient` so the
  lifespan runs
- WHEN `GET /health` is requested
- THEN the response MUST still return a successful status

#### Scenario: Admin request fails fast when the pool is unavailable

- GIVEN `DB_URL` is unset or the connection pool failed to initialize, so
  `app.state.db_pool` is `None`
- WHEN a request reaches a `/admin` router endpoint that requires the pool
  (after passing JWT verification)
- THEN the request MUST be rejected with `503 Service Unavailable`
- AND `ProductRepository.list_all` MUST NOT be invoked with a `None` pool

Note: the existing "Hexagonal Domain Boundary Enforcement" requirement
already prohibits `domain/` from importing "FastAPI, Pydantic, or any DB
client library" — this already covers banning `asyncpg` from `domain/`.
No MODIFIED delta is needed for that requirement; only the
`BANNED_MODULES` test fixture list needs the literal `asyncpg` entry added
to enforce the existing spec text, which is an implementation detail of
tasks/apply, not a spec change.
