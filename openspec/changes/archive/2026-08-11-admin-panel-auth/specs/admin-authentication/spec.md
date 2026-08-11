# Admin Authentication Specification

## Purpose

Gate the `(admin)` route group behind Supabase Auth (email/password) session
cookies, refreshed and enforced by Next.js's `proxy` file convention
(`frontend/src/proxy.ts` — Next 16 renamed `middleware.ts`/`middleware()` to
`proxy.ts`/`proxy()`; confirmed against the installed Next 16.3.0 docs), with
UX defaults for expiry, re-visit, and logout.

## Requirements

### Requirement: Login With Email/Password
The system MUST provide a login page that authenticates against Supabase
Auth (email/password) and MUST establish a session cookie via a dedicated
session-writing Supabase client factory (distinct from the existing
`createAnonCatalogClient`/`createRequestCatalogClient` read-only factories,
which MUST NOT be modified or reused for this purpose).

#### Scenario: Valid credentials establish a session
- GIVEN the manually provisioned admin user exists in Supabase Auth
- WHEN the admin submits correct email and password on the login page
- THEN a session cookie MUST be written via the session-writing client factory
- AND the admin MUST be redirected into the `(admin)` route group

#### Scenario: Invalid credentials are rejected
- GIVEN the login page
- WHEN the admin submits an incorrect email or password
- THEN authentication MUST fail
- AND no session cookie SHALL be written
- AND the admin MUST remain on the login page with an error indication

### Requirement: Proxy Protects the Admin Route Group
`frontend/src/proxy.ts` (Next 16's renamed `middleware.ts` file convention)
MUST refresh the Supabase session and MUST block unauthenticated access to
any route under the `(admin)` group. Per the pinned URL contract from
`initial-scaffolding` (the `(admin)` route group serves under `/admin/*`),
routes live at `app/(admin)/admin/**` — including the login page at
`/admin/login` — so the group contributes no URL segment of its own and the
existing `runtime-caching.ts` `/admin/*` matcher needs no changes.

#### Scenario: Unauthenticated visit to an admin route redirects to login
- GIVEN no valid session cookie is present
- WHEN a request targets any route inside the `(admin)` group
- THEN the proxy MUST redirect the request to `/admin/login`
- AND the login page MUST NOT be reachable-bypassed by direct route access

#### Scenario: Authenticated visit to an admin route proceeds
- GIVEN a valid, unexpired session cookie
- WHEN a request targets a route inside the `(admin)` group
- THEN the proxy MUST allow the request through
- AND MUST refresh the session cookie if it is nearing expiry

### Requirement: Expired Session Redirects With Return URL
WHEN a session expires during an admin visit, the proxy MUST redirect
to `/admin/login` and MUST preserve the originally requested path so the
admin returns there after re-authenticating.

#### Scenario: Session expires mid-visit
- GIVEN the admin is on an `(admin)` route with a session that has expired
- WHEN the admin navigates or the proxy re-checks the session
- THEN the request MUST be redirected to `/admin/login`
- AND the redirect MUST include the original path as a return-URL parameter

#### Scenario: Successful re-login honors the return URL
- GIVEN the admin was redirected to login with a return-URL parameter
- WHEN the admin successfully re-authenticates
- THEN the admin MUST be redirected to the originally requested path, not
  the default admin landing page

### Requirement: Already-Authenticated Visit To Login Redirects To Landing
WHEN an already-authenticated admin visits the login page, the system MUST
redirect them to the default admin landing page instead of re-showing the
login form.

#### Scenario: Authenticated admin visits /admin/login
- GIVEN a valid, unexpired session cookie
- WHEN the admin navigates to the login page
- THEN the system MUST redirect to the default admin landing page
- AND the login form MUST NOT be rendered

### Requirement: Logout Clears The Session
The system MUST provide a logout control, reachable from within the
`(admin)` group, that invalidates the session cookie and returns the admin
to a logged-out state.

#### Scenario: Admin logs out
- GIVEN the admin is authenticated and viewing an `(admin)` route
- WHEN the admin activates the logout control
- THEN the session cookie MUST be cleared/invalidated
- AND a subsequent request to any `(admin)` route MUST redirect to login
