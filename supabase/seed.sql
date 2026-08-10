-- supabase/seed.sql
--
-- Local development fixture: 2 products, 4 variants, 4 images, and stock
-- movements that prove in_stock derivation both ways — one variant nets
-- positive stock (in_stock = true), one nets to zero (in_stock = false),
-- and two receive no movements at all (in_stock = false via COALESCE).

insert into products (slug, name, model, description) values
  ('fundas-iphone-15', 'Funda iPhone 15', 'iPhone 15', 'Funda protectora para iPhone 15'),
  ('fundas-galaxy-s24', 'Funda Galaxy S24', 'Galaxy S24', 'Funda protectora para Samsung Galaxy S24');

insert into product_variants (product_id, color, price, cost)
select id, 'negro', 15990.00, 6000.00 from products where slug = 'fundas-iphone-15'
union all
select id, 'transparente', 12990.00, 4500.00 from products where slug = 'fundas-iphone-15'
union all
select id, 'negro', 14990.00, 5500.00 from products where slug = 'fundas-galaxy-s24'
union all
select id, 'azul', 14990.00, 5500.00 from products where slug = 'fundas-galaxy-s24';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select v.product_id, v.id, 'fundas-iphone-15/negro.jpg', 'Funda iPhone 15 negra', 0
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'negro'
union all
select v.product_id, v.id, 'fundas-iphone-15/transparente.jpg', 'Funda iPhone 15 transparente', 0
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'transparente'
union all
select v.product_id, v.id, 'fundas-galaxy-s24/negro.jpg', 'Funda Galaxy S24 negra', 0
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-galaxy-s24' and v.color = 'negro'
union all
select v.product_id, v.id, 'fundas-galaxy-s24/azul.jpg', 'Funda Galaxy S24 azul', 0
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-galaxy-s24' and v.color = 'azul';

-- In-stock variant: net +15 => in_stock = true
insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 20, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'negro'
union all
select v.id, 'sale', -5, 'Seed: initial sales'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'negro';

-- Out-of-stock variant: net-zero movements => in_stock = false
insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 8, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'transparente'
union all
select v.id, 'sale', -8, 'Seed: sold out'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'fundas-iphone-15' and v.color = 'transparente';

-- Galaxy S24 negro/azul intentionally receive no movements: in_stock =
-- false via COALESCE(quantity_on_hand, 0) > 0, proving the no-history path.
