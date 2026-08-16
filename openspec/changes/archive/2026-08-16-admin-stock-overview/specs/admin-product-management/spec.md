# Delta for Admin Product Management

## ADDED Requirements

### Requirement: Admin Product List Displays Per-Variant Current Stock

The admin product list MUST render each variant's current stock quantity,
sourced entirely from the existing `GET /admin/products` response, without
issuing any additional per-product or per-variant stock request to render
the list.

#### Scenario: Admin list displays each variant's current stock quantity

- GIVEN the `GET /admin/products` response includes a current stock
  quantity for every variant
- WHEN the admin product list page renders
- THEN each variant row MUST display its current stock quantity
- AND no additional network request for stock MUST be issued to render
  the list
