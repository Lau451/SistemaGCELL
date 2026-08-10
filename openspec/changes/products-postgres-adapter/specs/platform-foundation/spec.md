# Delta for platform-foundation

## ADDED Requirements

### Requirement: Backend Boot Establishes Database Connection Pool Lifecycle

The backend application MUST establish an asyncpg connection pool during
FastAPI lifespan startup, configured via a `DB_URL` value, and MUST close
that pool during lifespan shutdown. Pool creation MUST NOT be required for
endpoints, such as `/health`, that do not touch the database.

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

Note: the existing "Hexagonal Domain Boundary Enforcement" requirement
already prohibits `domain/` from importing "FastAPI, Pydantic, or any DB
client library" — this already covers banning `asyncpg` from `domain/`.
No MODIFIED delta is needed for that requirement; only the
`BANNED_MODULES` test fixture list needs the literal `asyncpg` entry added
to enforce the existing spec text, which is an implementation detail of
tasks/apply, not a spec change.
