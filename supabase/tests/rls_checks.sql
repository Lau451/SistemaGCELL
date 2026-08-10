-- supabase/tests/rls_checks.sql
--
-- RED-first assertion script for the supabase-schema change. Plain psql +
-- PL/pgSQL asserts were chosen over pgTAP because pgTAP needs
-- `create extension pgtap` shipped in a migration; these asserts add no
-- extension. Run with:
--
--   psql "<connection-string>" -v ON_ERROR_STOP=1 -f supabase/tests/rls_checks.sql
--
-- Expected outcome BEFORE the supabase-schema migrations exist: this script
-- FAILS immediately (undefined_table) — that is the genuine RED state.
-- Expected outcome AFTER all four migrations apply cleanly: every assertion
-- passes and the script exits 0 — that is the GREEN state.
--
-- The script is idempotent: it reuses its own fixture rows (keyed by a
-- `rls-check-*` slug/color) instead of failing on unique-constraint
-- conflicts if run more than once against the same database.

\set ON_ERROR_STOP on

-- =============================================================================
-- Fixture: two products, three variants (one net-positive stock, one
-- net-zero stock, one with zero movements), images, and stock movements
-- proving `+10, -3, +2 => 9` and a net-zero => out-of-stock case.
-- Runs as the connecting role (expected: postgres / superuser), which
-- bypasses RLS so the fixture can always be written regardless of the
-- policies under test.
-- =============================================================================
DO $$
DECLARE
  v_product_id uuid;
  v_in_stock_variant_id uuid;
  v_out_of_stock_variant_id uuid;
BEGIN
  SELECT id INTO v_product_id FROM products WHERE slug = 'rls-check-product';

  IF v_product_id IS NULL THEN
    INSERT INTO products (slug, name, model, description)
    VALUES ('rls-check-product', 'RLS Check Phone', 'RLS-1', 'Fixture row for rls_checks.sql')
    RETURNING id INTO v_product_id;

    INSERT INTO product_variants (product_id, color, price, cost)
    VALUES (v_product_id, 'rls-check-in-stock', 100.00, 60.00)
    RETURNING id INTO v_in_stock_variant_id;

    INSERT INTO product_variants (product_id, color, price, cost)
    VALUES (v_product_id, 'rls-check-out-of-stock', 100.00, 60.00)
    RETURNING id INTO v_out_of_stock_variant_id;

    INSERT INTO product_images (product_id, variant_id, storage_path, alt_text, sort_order)
    VALUES (v_product_id, v_in_stock_variant_id, 'rls-check/in-stock.jpg', 'RLS check fixture image', 0);

    -- +10, -3, +2 => 9 in stock (Requirement: Stock reflects sum of movements)
    INSERT INTO stock_movements (variant_id, movement_type, quantity_delta, reason) VALUES
      (v_in_stock_variant_id, 'restock', 10, 'rls_checks fixture'),
      (v_in_stock_variant_id, 'sale', -3, 'rls_checks fixture'),
      (v_in_stock_variant_id, 'restock', 2, 'rls_checks fixture');

    -- net-zero => out of stock (Requirement: in_stock flips via INSERT only)
    INSERT INTO stock_movements (variant_id, movement_type, quantity_delta, reason) VALUES
      (v_out_of_stock_variant_id, 'restock', 5, 'rls_checks fixture'),
      (v_out_of_stock_variant_id, 'sale', -5, 'rls_checks fixture');
  ELSE
    SELECT id INTO v_in_stock_variant_id FROM product_variants
      WHERE product_id = v_product_id AND color = 'rls-check-in-stock';
    SELECT id INTO v_out_of_stock_variant_id FROM product_variants
      WHERE product_id = v_product_id AND color = 'rls-check-out-of-stock';
  END IF;

  DROP TABLE IF EXISTS rls_check_fixture;
  CREATE TEMP TABLE rls_check_fixture (product_id uuid, in_stock_variant_id uuid, out_of_stock_variant_id uuid);
  INSERT INTO rls_check_fixture VALUES (v_product_id, v_in_stock_variant_id, v_out_of_stock_variant_id);

  RAISE NOTICE 'FIXTURE READY: product=%, in_stock_variant=%, out_of_stock_variant=%',
    v_product_id, v_in_stock_variant_id, v_out_of_stock_variant_id;
END $$;

-- =============================================================================
-- Requirement: Public Catalog Reads Exclude Cost and Raw Rows
-- Requirement: Public Visibility Is a Boolean Only
-- anon MUST be denied on every base table (zero rows or an authorization
-- error — the design grants anon nothing at all on base tables, so this
-- always surfaces as an authorization error).
-- =============================================================================
SET ROLE anon;

DO $$
DECLARE
  v_cnt int;
BEGIN
  SELECT count(*) INTO v_cnt FROM products;
  IF v_cnt > 0 THEN
    RAISE EXCEPTION 'ASSERTION FAILED: anon SELECT on products returned % rows, expected 0 or an authorization error', v_cnt;
  END IF;
  RAISE NOTICE 'PASS: anon sees 0 rows on products (no privilege error raised)';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: anon denied on products (%)', SQLERRM;
END $$;

DO $$
DECLARE
  v_cnt int;
BEGIN
  SELECT count(*) INTO v_cnt FROM product_variants;
  IF v_cnt > 0 THEN
    RAISE EXCEPTION 'ASSERTION FAILED: anon SELECT on product_variants returned % rows, expected 0 or an authorization error', v_cnt;
  END IF;
  RAISE NOTICE 'PASS: anon sees 0 rows on product_variants (no privilege error raised)';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: anon denied on product_variants (%)', SQLERRM;
END $$;

DO $$
DECLARE
  v_cnt int;
BEGIN
  SELECT count(*) INTO v_cnt FROM product_images;
  IF v_cnt > 0 THEN
    RAISE EXCEPTION 'ASSERTION FAILED: anon SELECT on product_images returned % rows, expected 0 or an authorization error', v_cnt;
  END IF;
  RAISE NOTICE 'PASS: anon sees 0 rows on product_images (no privilege error raised)';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: anon denied on product_images (%)', SQLERRM;
END $$;

DO $$
DECLARE
  v_cnt int;
BEGIN
  SELECT count(*) INTO v_cnt FROM stock_movements;
  IF v_cnt > 0 THEN
    RAISE EXCEPTION 'ASSERTION FAILED: anon SELECT on stock_movements returned % rows, expected 0 or an authorization error', v_cnt;
  END IF;
  RAISE NOTICE 'PASS: anon sees 0 rows on stock_movements (no privilege error raised)';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: anon denied on stock_movements (%)', SQLERRM;
END $$;

RESET ROLE;

-- =============================================================================
-- Requirement: Public Catalog Reads Exclude Cost and Raw Rows
-- Column-list asserts: the public catalog views must never expose `cost`
-- or a raw stock quantity column.
-- =============================================================================
DO $$
DECLARE
  v_cols text;
BEGIN
  SELECT string_agg(column_name, ',' ORDER BY column_name) INTO v_cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'catalog_products';

  IF v_cols IS NULL THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_products view does not exist';
  END IF;
  IF v_cols ILIKE '%cost%' THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_products exposes a cost-like column: %', v_cols;
  END IF;
  RAISE NOTICE 'PASS: catalog_products columns = %', v_cols;
END $$;

DO $$
DECLARE
  v_cols text;
BEGIN
  SELECT string_agg(column_name, ',' ORDER BY column_name) INTO v_cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'catalog_variants';

  IF v_cols IS NULL THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_variants view does not exist';
  END IF;
  IF v_cols ILIKE '%cost%' THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_variants exposes a cost-like column: %', v_cols;
  END IF;
  IF v_cols ILIKE '%quantity%' THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_variants exposes a raw quantity column: %', v_cols;
  END IF;
  IF v_cols NOT ILIKE '%in_stock%' THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_variants must expose a derived in_stock column: %', v_cols;
  END IF;
  RAISE NOTICE 'PASS: catalog_variants columns = %', v_cols;
END $$;

DO $$
DECLARE
  v_cols text;
BEGIN
  SELECT string_agg(column_name, ',' ORDER BY column_name) INTO v_cols
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'catalog_product_images';

  IF v_cols IS NULL THEN
    RAISE EXCEPTION 'ASSERTION FAILED: catalog_product_images view does not exist';
  END IF;
  RAISE NOTICE 'PASS: catalog_product_images columns = %', v_cols;
END $$;

-- =============================================================================
-- Requirement: anon reads catalog via public view
-- =============================================================================
SET ROLE anon;

DO $$
DECLARE
  v_row record;
BEGIN
  SELECT * INTO v_row FROM catalog_products
    WHERE slug = 'rls-check-product';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'ASSERTION FAILED: anon could not read rls-check-product via catalog_products';
  END IF;
  RAISE NOTICE 'PASS: anon reads catalog_products row (slug=%)', v_row.slug;
END $$;

RESET ROLE;

-- =============================================================================
-- Requirement: Stock reflects sum of movements (+10, -3, +2 => 9)
-- Requirement: Public Visibility Is a Boolean Only (in_stock derivation,
-- both the true and false case)
-- =============================================================================
DO $$
DECLARE
  v_qty int;
  v_in_stock boolean;
  v_variant_id uuid;
BEGIN
  SELECT in_stock_variant_id INTO v_variant_id FROM rls_check_fixture;

  SELECT quantity_on_hand INTO v_qty FROM variant_stock_levels WHERE variant_id = v_variant_id;
  IF v_qty IS DISTINCT FROM 9 THEN
    RAISE EXCEPTION 'ASSERTION FAILED: expected derived stock 9 for +10,-3,+2 movements, got %', v_qty;
  END IF;
  RAISE NOTICE 'PASS: variant_stock_levels derives 9 from +10,-3,+2';

  SELECT in_stock INTO v_in_stock FROM catalog_variants WHERE id = v_variant_id;
  IF v_in_stock IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'ASSERTION FAILED: expected in_stock=true for a variant with quantity 9, got %', v_in_stock;
  END IF;
  RAISE NOTICE 'PASS: catalog_variants.in_stock = true for a positive-stock variant';
END $$;

DO $$
DECLARE
  v_in_stock boolean;
  v_variant_id uuid;
BEGIN
  SELECT out_of_stock_variant_id INTO v_variant_id FROM rls_check_fixture;

  SELECT in_stock INTO v_in_stock FROM catalog_variants WHERE id = v_variant_id;
  IF v_in_stock IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'ASSERTION FAILED: expected in_stock=false for a net-zero-movement variant, got %', v_in_stock;
  END IF;
  RAISE NOTICE 'PASS: catalog_variants.in_stock = false for a net-zero-movement variant (derived by INSERT only, no UPDATE)';
END $$;

-- =============================================================================
-- Requirement: Stock Movements Are Append-Only
-- No UPDATE or DELETE path exists on stock_movements, for any role
-- including service_role / the connecting superuser.
-- =============================================================================
DO $$
DECLARE
  v_variant_id uuid;
BEGIN
  SELECT in_stock_variant_id INTO v_variant_id FROM rls_check_fixture;

  UPDATE stock_movements SET quantity_delta = 999 WHERE variant_id = v_variant_id;
  RAISE EXCEPTION 'ASSERTION FAILED: UPDATE on stock_movements should be rejected by the append-only trigger';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: UPDATE on stock_movements rejected (%)', SQLERRM;
END $$;

DO $$
DECLARE
  v_variant_id uuid;
BEGIN
  SELECT in_stock_variant_id INTO v_variant_id FROM rls_check_fixture;

  DELETE FROM stock_movements WHERE variant_id = v_variant_id;
  RAISE EXCEPTION 'ASSERTION FAILED: DELETE on stock_movements should be rejected by the append-only trigger';
EXCEPTION WHEN OTHERS THEN
  IF SQLERRM LIKE 'ASSERTION FAILED%' THEN
    RAISE;
  END IF;
  RAISE NOTICE 'PASS: DELETE on stock_movements rejected (%)', SQLERRM;
END $$;

-- =============================================================================
-- Requirement: Service Role Has Full Catalog Access /
-- Service Role Reads Full Movement History
-- =============================================================================
DO $$
DECLARE
  v_cost numeric;
BEGIN
  SELECT cost INTO v_cost FROM product_variants LIMIT 1;
  IF v_cost IS NULL THEN
    RAISE EXCEPTION 'ASSERTION FAILED: service_role (connecting role) could not read cost from product_variants';
  END IF;
  RAISE NOTICE 'PASS: service_role/postgres reads cost from product_variants (cost=%)', v_cost;
END $$;

DO $$
BEGIN
  RAISE NOTICE 'ALL ASSERTIONS PASSED';
END $$;
