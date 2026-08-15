# Delta for Product Media Storage

## ADDED Requirements

### Requirement: Backend Service Role Upload And Delete Contract

The backend MUST hold a `service_role` Storage client, configured from
backend-only `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` environment
variables that MUST NEVER be exposed as `NEXT_PUBLIC_*` or shipped in any
frontend bundle, and MUST use it as the sole writer for product photo
objects. The Storage client MUST expose put and delete operations used
exclusively by backend image use cases.

#### Scenario: Backend uploads using service_role, never the frontend
- GIVEN a validated, normalized image ready to persist
- WHEN the upload use case writes it to Storage
- THEN the write MUST use the backend's `service_role` client
- AND no service-role credential MUST exist in frontend code or the client
  bundle

#### Scenario: Missing service-role configuration fails closed
- GIVEN `SUPABASE_SERVICE_ROLE_KEY` is absent from the backend environment
- WHEN an image write use case attempts to run
- THEN the request MUST fail with `503 Service Unavailable`
- AND no partial Storage or DB write MUST occur

### Requirement: Stored Objects Are Normalized To Bucket-Legal Constraints

Every object written to the product-photos bucket via the backend upload
path MUST already satisfy the bucket's jpeg/png/webp mime constraint and
5MiB size ceiling at write time; normalization MUST happen server-side
before the Storage `put` call, never left to Storage-side enforcement alone.

#### Scenario: Normalized object satisfies bucket constraints
- GIVEN a source image accepted past validation
- WHEN the backend writes the normalized object to Storage
- THEN the written object's mime type MUST be one of jpeg/png/webp and its
  size MUST be at or under 5MiB

### Requirement: Storage Path Follows The Seed Convention With A Uniqueness Suffix

Objects written by the upload use case MUST use the same `storage_path`
convention as pre-seeded rows, extended with a uniqueness suffix so a
re-upload for the same product/variant never collides with an existing
object path.

#### Scenario: Re-upload does not collide with a prior object
- GIVEN a product/variant already has one stored image
- WHEN a second image is uploaded for the same product/variant
- THEN the new object's `storage_path` MUST differ from the existing one
- AND both objects MUST remain independently addressable
