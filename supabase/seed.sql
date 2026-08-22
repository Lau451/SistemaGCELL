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

-- Additional local dev catalog fixtures: 25 fundas + 9 accessories
-- with AI-generated hero product photos (appended by seed_catalog.py run).

insert into products (slug, name, model, short_description) values
  ('funda-iphone-16', 'Funda iPhone 16', 'iPhone 16', 'Funda protectora de silicona para iPhone 16.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 15990.00, 6000.00 from products where slug = 'funda-iphone-16'
union all
select id, 'Azul', 15990.00, 6000.00 from products where slug = 'funda-iphone-16';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 20, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-16' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 12, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-16' and v.color = 'Azul';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-16/hero.png', 'Funda iPhone 16 - foto principal', 0
from products where slug = 'funda-iphone-16';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-16-pro-magsafe', 'Funda iPhone 16 Pro MagSafe', 'iPhone 16 Pro', 'Funda transparente compatible con MagSafe para iPhone 16 Pro.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 21990.00, 9000.00 from products where slug = 'funda-iphone-16-pro-magsafe';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 8, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-16-pro-magsafe' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-16-pro-magsafe/hero.png', 'Funda iPhone 16 Pro MagSafe - foto principal', 0
from products where slug = 'funda-iphone-16-pro-magsafe';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-16-plus', 'Funda iPhone 16 Plus', 'iPhone 16 Plus', 'Funda transparente antigolpe para iPhone 16 Plus.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 16990.00, 6500.00 from products where slug = 'funda-iphone-16-plus';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-16-plus/hero.png', 'Funda iPhone 16 Plus - foto principal', 0
from products where slug = 'funda-iphone-16-plus';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-15-plus', 'Funda iPhone 15 Plus', 'iPhone 15 Plus', 'Funda protectora de silicona para iPhone 15 Plus.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 15990.00, 6000.00 from products where slug = 'funda-iphone-15-plus'
union all
select id, 'Blanco', 15990.00, 6000.00 from products where slug = 'funda-iphone-15-plus';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 18, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-15-plus' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 10, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-15-plus' and v.color = 'Blanco';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-15-plus/hero.png', 'Funda iPhone 15 Plus - foto principal', 0
from products where slug = 'funda-iphone-15-plus';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-14', 'Funda iPhone 14', 'iPhone 14', 'Funda protectora de silicona para iPhone 14.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 13990.00, 5200.00 from products where slug = 'funda-iphone-14'
union all
select id, 'Verde', 13990.00, 5200.00 from products where slug = 'funda-iphone-14';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 25, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-14' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 6, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-14' and v.color = 'Verde';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-14/hero.png', 'Funda iPhone 14 - foto principal', 0
from products where slug = 'funda-iphone-14';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-14-pro-max-magsafe', 'Funda iPhone 14 Pro Max MagSafe', 'iPhone 14 Pro Max', 'Funda compatible con MagSafe para iPhone 14 Pro Max.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 22990.00, 9500.00 from products where slug = 'funda-iphone-14-pro-max-magsafe'
union all
select id, 'Azul', 22990.00, 9500.00 from products where slug = 'funda-iphone-14-pro-max-magsafe';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 5, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-14-pro-max-magsafe' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-14-pro-max-magsafe/hero.png', 'Funda iPhone 14 Pro Max MagSafe - foto principal', 0
from products where slug = 'funda-iphone-14-pro-max-magsafe';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-13-pro-cuero', 'Funda iPhone 13 Pro de cuero', 'iPhone 13 Pro', 'Funda de cuero premium para iPhone 13 Pro.');

insert into product_variants (product_id, color, price, cost)
select id, 'Marrón', 24990.00, 11000.00 from products where slug = 'funda-iphone-13-pro-cuero'
union all
select id, 'Negro', 24990.00, 11000.00 from products where slug = 'funda-iphone-13-pro-cuero';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 7, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-13-pro-cuero' and v.color = 'Marrón';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 9, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-13-pro-cuero' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-13-pro-cuero/hero.png', 'Funda iPhone 13 Pro de cuero - foto principal', 0
from products where slug = 'funda-iphone-13-pro-cuero';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-12', 'Funda iPhone 12', 'iPhone 12', 'Funda transparente para iPhone 12.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 12990.00, 4500.00 from products where slug = 'funda-iphone-12';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 15, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-12' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-12/hero.png', 'Funda iPhone 12 - foto principal', 0
from products where slug = 'funda-iphone-12';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-11-antigolpe', 'Funda iPhone 11 antigolpe', 'iPhone 11', 'Funda antigolpe reforzada para iPhone 11.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 13990.00, 5000.00 from products where slug = 'funda-iphone-11-antigolpe'
union all
select id, 'Negro', 13990.00, 5000.00 from products where slug = 'funda-iphone-11-antigolpe';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 11, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-11-antigolpe' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-11-antigolpe/hero.png', 'Funda iPhone 11 antigolpe - foto principal', 0
from products where slug = 'funda-iphone-11-antigolpe';

insert into products (slug, name, model, short_description) values
  ('funda-iphone-se', 'Funda iPhone SE', 'iPhone SE', 'Funda protectora de silicona para iPhone SE.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 11990.00, 4200.00 from products where slug = 'funda-iphone-se'
union all
select id, 'Rojo', 11990.00, 4200.00 from products where slug = 'funda-iphone-se';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 14, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-se' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 3, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-iphone-se' and v.color = 'Rojo';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-iphone-se/hero.png', 'Funda iPhone SE - foto principal', 0
from products where slug = 'funda-iphone-se';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-s24-ultra-antigolpe', 'Funda Galaxy S24 Ultra antigolpe', 'Galaxy S24 Ultra', 'Funda antigolpe reforzada para Samsung Galaxy S24 Ultra.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 19990.00, 8000.00 from products where slug = 'funda-galaxy-s24-ultra-antigolpe'
union all
select id, 'Transparente', 19990.00, 8000.00 from products where slug = 'funda-galaxy-s24-ultra-antigolpe';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 13, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-s24-ultra-antigolpe' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-s24-ultra-antigolpe/hero.png', 'Funda Galaxy S24 Ultra antigolpe - foto principal', 0
from products where slug = 'funda-galaxy-s24-ultra-antigolpe';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-s23', 'Funda Galaxy S23', 'Galaxy S23', 'Funda protectora de silicona para Samsung Galaxy S23.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 14990.00, 5800.00 from products where slug = 'funda-galaxy-s23'
union all
select id, 'Violeta', 14990.00, 5800.00 from products where slug = 'funda-galaxy-s23';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 16, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-s23' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 4, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-s23' and v.color = 'Violeta';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-s23/hero.png', 'Funda Galaxy S23 - foto principal', 0
from products where slug = 'funda-galaxy-s23';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-s22', 'Funda Galaxy S22', 'Galaxy S22', 'Funda protectora de silicona para Samsung Galaxy S22.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 13990.00, 5300.00 from products where slug = 'funda-galaxy-s22';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 9, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-s22' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-s22/hero.png', 'Funda Galaxy S22 - foto principal', 0
from products where slug = 'funda-galaxy-s22';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-s21', 'Funda Galaxy S21', 'Galaxy S21', 'Funda protectora de silicona para Samsung Galaxy S21.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 12990.00, 4800.00 from products where slug = 'funda-galaxy-s21'
union all
select id, 'Azul', 12990.00, 4800.00 from products where slug = 'funda-galaxy-s21';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 6, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-s21' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-s21/hero.png', 'Funda Galaxy S21 - foto principal', 0
from products where slug = 'funda-galaxy-s21';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-a55', 'Funda Galaxy A55', 'Galaxy A55', 'Funda protectora de silicona para Samsung Galaxy A55.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 13990.00, 5200.00 from products where slug = 'funda-galaxy-a55'
union all
select id, 'Lila', 13990.00, 5200.00 from products where slug = 'funda-galaxy-a55';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 20, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a55' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 8, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a55' and v.color = 'Lila';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-a55/hero.png', 'Funda Galaxy A55 - foto principal', 0
from products where slug = 'funda-galaxy-a55';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-a54', 'Funda Galaxy A54', 'Galaxy A54', 'Funda protectora de silicona para Samsung Galaxy A54.');

insert into product_variants (product_id, color, price, cost)
select id, 'Azul', 12990.00, 4800.00 from products where slug = 'funda-galaxy-a54'
union all
select id, 'Negro', 12990.00, 4800.00 from products where slug = 'funda-galaxy-a54';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 17, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a54' and v.color = 'Azul';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 12, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a54' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-a54/hero.png', 'Funda Galaxy A54 - foto principal', 0
from products where slug = 'funda-galaxy-a54';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-a34-transparente', 'Funda Galaxy A34 transparente', 'Galaxy A34', 'Funda transparente para Samsung Galaxy A34.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 11990.00, 4200.00 from products where slug = 'funda-galaxy-a34-transparente';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 22, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a34-transparente' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-a34-transparente/hero.png', 'Funda Galaxy A34 transparente - foto principal', 0
from products where slug = 'funda-galaxy-a34-transparente';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-a14', 'Funda Galaxy A14', 'Galaxy A14', 'Funda protectora para Samsung Galaxy A14.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 10990.00, 3800.00 from products where slug = 'funda-galaxy-a14'
union all
select id, 'Negro', 10990.00, 3800.00 from products where slug = 'funda-galaxy-a14';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 19, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-a14' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-a14/hero.png', 'Funda Galaxy A14 - foto principal', 0
from products where slug = 'funda-galaxy-a14';

insert into products (slug, name, model, short_description) values
  ('funda-galaxy-note-20-cuero', 'Funda Galaxy Note 20 de cuero', 'Galaxy Note 20', 'Funda de cuero premium para Samsung Galaxy Note 20.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 23990.00, 10500.00 from products where slug = 'funda-galaxy-note-20-cuero';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 4, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-galaxy-note-20-cuero' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-galaxy-note-20-cuero/hero.png', 'Funda Galaxy Note 20 de cuero - foto principal', 0
from products where slug = 'funda-galaxy-note-20-cuero';

insert into products (slug, name, model, short_description) values
  ('funda-redmi-note-13', 'Funda Redmi Note 13', 'Redmi Note 13', 'Funda protectora de silicona para Redmi Note 13.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 11990.00, 4300.00 from products where slug = 'funda-redmi-note-13'
union all
select id, 'Celeste', 11990.00, 4300.00 from products where slug = 'funda-redmi-note-13';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 24, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-redmi-note-13' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 9, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-redmi-note-13' and v.color = 'Celeste';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-redmi-note-13/hero.png', 'Funda Redmi Note 13 - foto principal', 0
from products where slug = 'funda-redmi-note-13';

insert into products (slug, name, model, short_description) values
  ('funda-redmi-note-12-antigolpe', 'Funda Redmi Note 12 antigolpe', 'Redmi Note 12', 'Funda antigolpe reforzada para Redmi Note 12.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 11990.00, 4300.00 from products where slug = 'funda-redmi-note-12-antigolpe';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-redmi-note-12-antigolpe/hero.png', 'Funda Redmi Note 12 antigolpe - foto principal', 0
from products where slug = 'funda-redmi-note-12-antigolpe';

insert into products (slug, name, model, short_description) values
  ('funda-xiaomi-13-cuero', 'Funda Xiaomi 13 de cuero', 'Xiaomi 13', 'Funda de cuero premium para Xiaomi 13.');

insert into product_variants (product_id, color, price, cost)
select id, 'Marrón', 22990.00, 10000.00 from products where slug = 'funda-xiaomi-13-cuero';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 6, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-xiaomi-13-cuero' and v.color = 'Marrón';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-xiaomi-13-cuero/hero.png', 'Funda Xiaomi 13 de cuero - foto principal', 0
from products where slug = 'funda-xiaomi-13-cuero';

insert into products (slug, name, model, short_description) values
  ('funda-poco-x6-antigolpe', 'Funda POCO X6 antigolpe', 'POCO X6', 'Funda antigolpe reforzada para POCO X6.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 12990.00, 4800.00 from products where slug = 'funda-poco-x6-antigolpe'
union all
select id, 'Verde', 12990.00, 4800.00 from products where slug = 'funda-poco-x6-antigolpe';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 13, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-poco-x6-antigolpe' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 5, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-poco-x6-antigolpe' and v.color = 'Verde';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-poco-x6-antigolpe/hero.png', 'Funda POCO X6 antigolpe - foto principal', 0
from products where slug = 'funda-poco-x6-antigolpe';

insert into products (slug, name, model, short_description) values
  ('funda-moto-g84', 'Funda Moto G84', 'Moto G84', 'Funda protectora de silicona para Motorola Moto G84.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 10990.00, 3900.00 from products where slug = 'funda-moto-g84'
union all
select id, 'Rosa', 10990.00, 3900.00 from products where slug = 'funda-moto-g84';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 18, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-moto-g84' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 7, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-moto-g84' and v.color = 'Rosa';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-moto-g84/hero.png', 'Funda Moto G84 - foto principal', 0
from products where slug = 'funda-moto-g84';

insert into products (slug, name, model, short_description) values
  ('funda-moto-edge-40-transparente', 'Funda Moto Edge 40 transparente', 'Moto Edge 40', 'Funda transparente para Motorola Moto Edge 40.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 11990.00, 4200.00 from products where slug = 'funda-moto-edge-40-transparente';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 10, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'funda-moto-edge-40-transparente' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'funda-moto-edge-40-transparente/hero.png', 'Funda Moto Edge 40 transparente - foto principal', 0
from products where slug = 'funda-moto-edge-40-transparente';

insert into products (slug, name, model, short_description) values
  ('cargador-rapido-20w', 'Cargador rápido USB-C 20W', 'Cargador', 'Cargador rápido USB-C de 20W, compatible con múltiples dispositivos.');

insert into product_variants (product_id, color, price, cost)
select id, 'Blanco', 9990.00, 4000.00 from products where slug = 'cargador-rapido-20w'
union all
select id, 'Negro', 9990.00, 4000.00 from products where slug = 'cargador-rapido-20w';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 30, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'cargador-rapido-20w' and v.color = 'Blanco';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 22, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'cargador-rapido-20w' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'cargador-rapido-20w/hero.png', 'Cargador rápido USB-C 20W - foto principal', 0
from products where slug = 'cargador-rapido-20w';

insert into products (slug, name, model, short_description) values
  ('cable-usbc-lightning-1m', 'Cable USB-C a Lightning 1m', 'Cable', 'Cable USB-C a Lightning de 1 metro, carga y transferencia de datos.');

insert into product_variants (product_id, color, price, cost)
select id, 'Blanco', 6990.00, 2800.00 from products where slug = 'cable-usbc-lightning-1m';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 40, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'cable-usbc-lightning-1m' and v.color = 'Blanco';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'cable-usbc-lightning-1m/hero.png', 'Cable USB-C a Lightning 1m - foto principal', 0
from products where slug = 'cable-usbc-lightning-1m';

insert into products (slug, name, model, short_description) values
  ('cable-usbc-usbc-1m', 'Cable USB-C a USB-C 1m', 'Cable', 'Cable USB-C a USB-C de 1 metro, carga rápida.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 6490.00, 2500.00 from products where slug = 'cable-usbc-usbc-1m';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 35, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'cable-usbc-usbc-1m' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'cable-usbc-usbc-1m/hero.png', 'Cable USB-C a USB-C 1m - foto principal', 0
from products where slug = 'cable-usbc-usbc-1m';

insert into products (slug, name, model, short_description) values
  ('vidrio-templado-iphone-15', 'Vidrio templado iPhone 15', 'iPhone 15', 'Vidrio templado de protección para iPhone 15.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 7990.00, 2800.00 from products where slug = 'vidrio-templado-iphone-15';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 50, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'vidrio-templado-iphone-15' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'vidrio-templado-iphone-15/hero.png', 'Vidrio templado iPhone 15 - foto principal', 0
from products where slug = 'vidrio-templado-iphone-15';

insert into products (slug, name, model, short_description) values
  ('vidrio-templado-galaxy-s24', 'Vidrio templado Galaxy S24', 'Galaxy S24', 'Vidrio templado de protección para Samsung Galaxy S24.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 7990.00, 2800.00 from products where slug = 'vidrio-templado-galaxy-s24';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 45, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'vidrio-templado-galaxy-s24' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'vidrio-templado-galaxy-s24/hero.png', 'Vidrio templado Galaxy S24 - foto principal', 0
from products where slug = 'vidrio-templado-galaxy-s24';

insert into products (slug, name, model, short_description) values
  ('vidrio-templado-redmi-note-13', 'Vidrio templado Redmi Note 13', 'Redmi Note 13', 'Vidrio templado de protección para Redmi Note 13.');

insert into product_variants (product_id, color, price, cost)
select id, 'Transparente', 6990.00, 2500.00 from products where slug = 'vidrio-templado-redmi-note-13';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 38, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'vidrio-templado-redmi-note-13' and v.color = 'Transparente';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'vidrio-templado-redmi-note-13/hero.png', 'Vidrio templado Redmi Note 13 - foto principal', 0
from products where slug = 'vidrio-templado-redmi-note-13';

insert into products (slug, name, model, short_description) values
  ('power-bank-10000mah', 'Power bank 10000mAh', 'Power bank', 'Batería externa de 10000mAh, carga rápida para celular.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 29990.00, 14000.00 from products where slug = 'power-bank-10000mah'
union all
select id, 'Blanco', 29990.00, 14000.00 from products where slug = 'power-bank-10000mah';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 15, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'power-bank-10000mah' and v.color = 'Negro';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 8, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'power-bank-10000mah' and v.color = 'Blanco';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'power-bank-10000mah/hero.png', 'Power bank 10000mAh - foto principal', 0
from products where slug = 'power-bank-10000mah';

insert into products (slug, name, model, short_description) values
  ('auriculares-bluetooth-tws', 'Auriculares Bluetooth TWS', 'Auriculares', 'Auriculares inalámbricos Bluetooth con estuche de carga.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 39990.00, 19000.00 from products where slug = 'auriculares-bluetooth-tws'
union all
select id, 'Blanco', 39990.00, 19000.00 from products where slug = 'auriculares-bluetooth-tws';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 12, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'auriculares-bluetooth-tws' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'auriculares-bluetooth-tws/hero.png', 'Auriculares Bluetooth TWS - foto principal', 0
from products where slug = 'auriculares-bluetooth-tws';

insert into products (slug, name, model, short_description) values
  ('soporte-auto-magnetico', 'Soporte para auto magnético', 'Soporte para auto', 'Soporte magnético para celular, para auto.');

insert into product_variants (product_id, color, price, cost)
select id, 'Negro', 8990.00, 3500.00 from products where slug = 'soporte-auto-magnetico';

insert into stock_movements (variant_id, movement_type, quantity_delta, reason)
select v.id, 'restock', 20, 'Seed: initial stock'
from product_variants v join products p on p.id = v.product_id
where p.slug = 'soporte-auto-magnetico' and v.color = 'Negro';

insert into product_images (product_id, variant_id, storage_path, alt_text, sort_order)
select id, NULL, 'soporte-auto-magnetico/hero.png', 'Soporte para auto magnético - foto principal', 0
from products where slug = 'soporte-auto-magnetico';

-- The 34 products above only set short_description; the public product
-- detail page reads `description`, so backfill it for this batch (the
-- original 2 seed products already set `description` directly and are
-- unaffected since their `description` is never NULL).
update products
set description = short_description
where description is null and short_description is not null;
