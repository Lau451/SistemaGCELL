-- Base catalog schema: products, product_variants, product_images.
-- Public reads happen only through views defined in a later migration;
-- these base tables stay private (RLS enabled with zero anon policies
-- once RLS is turned on in public_catalog_rls).

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table products (
  id uuid primary key default gen_random_uuid(),
  slug text not null,
  name text not null,
  model text not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint products_slug_key unique (slug),
  constraint products_slug_format_check check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  constraint products_slug_length_check check (char_length(slug) between 1 and 80),
  constraint products_name_not_blank_check check (btrim(name) <> ''),
  constraint products_model_not_blank_check check (btrim(model) <> '')
);

create trigger products_set_updated_at
  before update on products
  for each row execute function set_updated_at();

create table product_variants (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references products (id) on delete cascade,
  color text not null,
  price numeric(10, 2) not null,
  cost numeric(10, 2) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint product_variants_color_not_blank_check check (btrim(color) <> ''),
  constraint product_variants_price_nonnegative_check check (price >= 0),
  constraint product_variants_cost_nonnegative_check check (cost >= 0),
  -- Composite unique target for product_images' composite FK below.
  constraint product_variants_product_id_id_key unique (product_id, id)
);

create index product_variants_product_id_idx on product_variants (product_id);

create trigger product_variants_set_updated_at
  before update on product_variants
  for each row execute function set_updated_at();

create table product_images (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references products (id) on delete cascade,
  -- NULL variant_id = product hero image; non-NULL = colour-specific image.
  variant_id uuid references product_variants (id) on delete cascade,
  storage_path text not null,
  alt_text text,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  constraint product_images_storage_path_not_blank_check check (btrim(storage_path) <> ''),
  -- MATCH SIMPLE (default) skips this check when variant_id IS NULL, so a
  -- product-hero image needs no variant while a variant image is still
  -- forbidden from referencing a variant that belongs to a different product.
  constraint product_images_variant_fk
    foreign key (product_id, variant_id)
    references product_variants (product_id, id)
    on delete cascade
);

create index product_images_product_id_idx on product_images (product_id);
create index product_images_variant_id_idx on product_images (variant_id);
