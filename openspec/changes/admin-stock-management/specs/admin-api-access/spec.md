# Delta for Admin API Access

## ADDED Requirements

### Requirement: Stock Endpoints On The Admin Router

The `/admin` router MUST expose exactly two stock endpoints — read (`GET
/admin/products/{product_id}/stock`, returning `quantity_on_hand` for every
active variant of the product) and record (`POST
/admin/products/{product_id}/variants/{variant_id}/stock/movements`, taking
`movement_type`, `quantity_delta`, and optional `reason`) — each gated by the
same router-level `Depends(verify_admin_jwt)` dependency as every other admin
route, with no separate or weaker verification path.

#### Scenario: Unauthenticated stock read is rejected before the repository
- GIVEN a `GET /admin/products/{product_id}/stock` request with no valid
  admin JWT
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no repository call MUST occur

#### Scenario: Unauthenticated movement write is rejected before the repository
- GIVEN a `POST
  /admin/products/{product_id}/variants/{variant_id}/stock/movements`
  request with no valid admin JWT
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` insert MUST occur

#### Scenario: Authenticated request reaches the stock use cases
- GIVEN a valid admin JWT
- WHEN an admin issues the stock read or record-movement request
- THEN the route handler MUST invoke `StockLevelReader.quantity_on_hand` or
  `RecordStockMovementUseCase.execute` respectively, calling only the
  existing `stock/` use cases with no new port or use case

### Requirement: Unknown Variant Errors Map To 404

`_execute_or_raise` MUST map `UnknownVariantError` to `404 "not_found"` on
every admin route that resolves a `variant_id`, including the stock
record-movement route, so a stale or foreign `variant_id` surfaces as `404`
rather than the previously unmapped `500`.

#### Scenario: UnknownVariantError on the stock route yields 404, not 500
- GIVEN a record-movement request referencing a `variant_id` that does not
  belong to the addressed `product_id`
- WHEN the use case raises `UnknownVariantError`
- THEN `_execute_or_raise` MUST translate it to `404 "not_found"`
- AND the response MUST NOT be a `500`
