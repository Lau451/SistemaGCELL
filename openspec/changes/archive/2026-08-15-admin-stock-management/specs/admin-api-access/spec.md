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
- THEN the read route handler MUST invoke `StockLevelReader.quantity_on_hand`
  directly, and the write route handler MUST invoke
  `RecordVariantStockMovementUseCase.execute` (which itself resolves
  ownership before delegating to the existing `RecordStockMovementUseCase`),
  introducing no new port and no `stock/` domain or infrastructure change

### Requirement: Unknown Variant Errors Map To 404

`_execute_or_raise` MUST map `UnknownVariantError` to `404 "not_found"` on
every admin route that resolves a `variant_id`, so a stale or foreign
`variant_id` surfaces as `404` rather than the previously unmapped `500`.
On the stock record-movement route specifically, `RecordVariantStockMovementUseCase`'s
ownership scan already rejects a foreign or unknown `variant_id` with
`VariantNotFoundError`/`ProductNotFoundError` before the repository's `record`
call is ever reached, so `UnknownVariantError` is unreachable end-to-end
through that route; the mapping is defense-in-depth and MUST be proven at
the `_execute_or_raise` mapper directly, not as an API-level scenario.

#### Scenario: UnknownVariantError maps to 404, not 500, at the mapper
- GIVEN an operation that raises `UnknownVariantError`
- WHEN `_execute_or_raise` handles it
- THEN it MUST translate it to `404 "not_found"`
- AND the response MUST NOT be a `500`
