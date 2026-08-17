-- CI ONLY. Minimal stand-in for the `storage` schema owned by the Supabase
-- Storage service. Only what 20260810000502_storage_product_photos.sql and
-- test_rls_policies.py actually touch is reproduced.
create schema if not exists storage;

create table storage.buckets (
  id text primary key,
  name text not null,
  public boolean not null default false,
  created_at timestamptz not null default now()
);

create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets (id),
  name text,
  owner uuid,
  metadata jsonb,
  created_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now()
);

alter table storage.buckets enable row level security;
alter table storage.objects enable row level security;

-- Supabase grants table privileges broadly here and lets RLS restrict.
-- Reproduced so the anon-read test proves the POLICY, not a missing GRANT.
grant usage on schema storage to anon, authenticated, service_role;
grant select on storage.buckets to anon, authenticated;
grant all    on storage.buckets to service_role;
grant all    on storage.objects to anon, authenticated, service_role;
