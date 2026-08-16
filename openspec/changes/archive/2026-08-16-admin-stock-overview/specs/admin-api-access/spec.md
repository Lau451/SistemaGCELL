# Delta for Admin API Access

## ADDED Requirements

### Requirement: GET /admin/products Response Includes Per-Variant Current Stock

`GET /admin/products` MUST compose `ProductRepository.list_all()` with
exactly one bulk current-stock read from the stock capability, and MUST
include each variant's current quantity in the corresponding
`AdminProductResponse` variant, sourced from that single bulk query —
never a per-variant loop. Stock is part of the response contract: if the
bulk stock read fails, the entire `GET /admin/products` request MUST fail
with an error response. It MUST NOT return a `200` with a partial or
degraded list carrying missing or `null` stock values.

#### Scenario: Response includes per-variant stock for every returned product

- GIVEN a catalog with multiple products, each with one or more variants
- WHEN an authenticated admin requests `GET /admin/products`
- THEN every variant in the response MUST carry a current stock quantity
- AND exactly one stock query MUST back that response, regardless of
  variant count

#### Scenario: Bulk stock read failure fails the whole request

- GIVEN the bulk current-stock read raises an error
- WHEN an authenticated admin requests `GET /admin/products`
- THEN the response MUST be an error, not a `200`
- AND no product list MUST be returned, whether complete or partial
