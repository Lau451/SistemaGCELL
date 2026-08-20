# Gemini Generation Specification

## Purpose

The `ai` domain's Gemini port/adapter: backend-only text and image-input
generation, key configuration, graceful degradation, and error/timeout
mapping. `ai` is a leaf domain (D9), invoked only by `content`.

## Requirements

### Requirement: Ai Domain Exposes A Text And Image-Input Generation Port

`ai/application/` MUST expose a port covering both text generation (product
copy) and image-input generation (alt text) for `content` to call.
`ai/domain/` MUST remain pure and MUST NOT import `httpx` or any
infrastructure/framework symbol.

#### Scenario: Domain boundary test passes for ai

- GIVEN the `ai` domain layer
- WHEN `test_domain_boundary.py` runs
- THEN no banned import MUST be found in `ai/domain/`

#### Scenario: Only content imports ai

- GIVEN the fixed dependency direction `content -> ai`
- WHEN the import graph is inspected
- THEN nothing other than `content` MUST import from `ai/application` or
  `ai/infrastructure`

### Requirement: Every Gemini Call Is Backend-Only And Admin-Gated

No Gemini key, SDK reference, or call MUST exist under `frontend/`. Every
route that triggers a Gemini call MUST run behind the same admin JWT guard
as other `/admin` routes.

#### Scenario: Frontend has zero Gemini references

- GIVEN the frontend source tree
- WHEN searched for a Gemini key, SDK, or client call
- THEN none MUST be found

#### Scenario: Unauthenticated generate request is rejected

- GIVEN a generate request with no `Authorization` header
- WHEN it reaches an ai-backed admin route
- THEN the request MUST be rejected `401` before any Gemini call is made

### Requirement: Missing API Key Degrades Only AI Endpoints

When `GEMINI_API_KEY` is unset, a `require_gemini`-style guard MUST reject
only the AI-backed endpoints with `503`, while `/health`, the full public
catalog, and the rest of the admin panel remain unaffected.

#### Scenario: Generate endpoint returns 503 without a key

- GIVEN `GEMINI_API_KEY` is unset
- WHEN an admin calls a generate endpoint
- THEN the response MUST be `503`
- AND no Gemini call MUST be attempted

#### Scenario: Rest of the app is unaffected by a missing key

- GIVEN `GEMINI_API_KEY` is unset
- WHEN `/health`, the public catalog, and non-AI admin routes are exercised
- THEN all MUST behave exactly as with a key configured

### Requirement: Gemini Failures Map To A Deterministic Error, Never A Silent Success

A failed, timed-out, or malformed Gemini response MUST surface as an error
response distinguishable from a successful draft; it MUST NOT be treated as
an empty-but-successful draft.

#### Scenario: Gemini call failure surfaces as an error

- GIVEN a configured key and a Gemini call that fails or times out
- WHEN the generate route handles the response
- THEN it MUST return an error status, not `200` with an empty draft

### Requirement: Adapter Is Mock-Transport Testable With No Live Network

The Gemini adapter MUST be testable end-to-end using a mock HTTP transport,
and no test MUST perform a live network call to Gemini.

#### Scenario: Adapter tests run offline

- GIVEN the `ai` adapter test suite
- WHEN it runs in CI (no secrets present)
- THEN it MUST pass using a mocked transport with zero external network
  calls
