# Delta for Admin API Access

## ADDED Requirements

### Requirement: Multipart Image Endpoints On The Admin Router

The `/admin` router MUST expose exactly four image endpoints — list (`GET
/admin/products/{id}/images`), upload (`POST
/admin/products/{id}/images`), delete (`DELETE
/admin/products/{id}/images/{image_id}`), and reorder (`PUT
/admin/products/{id}/images/order`, taking the product's full ordered image
id list, never a partial/delta payload) — each gated by the same
router-level `Depends(verify_admin_jwt)` dependency as every other admin
route, with no separate or weaker verification path for multipart requests.
There is no replace endpoint: replacing an image's file is a delete
followed by an upload, composed by the caller, not a single server-side
route.

#### Scenario: Unauthenticated multipart upload is rejected before Storage
- GIVEN a `POST /admin/products/{id}/images` request with no valid admin
  JWT
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no Storage write and no repository call MUST occur

#### Scenario: Authenticated upload reaches the image use case
- GIVEN a `POST /admin/products/{id}/images` request with a valid admin JWT
  and a valid multipart file
- WHEN the route handler executes
- THEN it MUST invoke the image upload use case and return the persisted
  image's metadata

#### Scenario: Image endpoint on an unowned image returns 404
- GIVEN an image id that belongs to a different product than the one in
  the URL path
- WHEN a delete or reorder request targets that combination with a valid
  admin JWT
- THEN the response MUST be `404`, matching the ownership-check behavior
  already required of the image use cases
