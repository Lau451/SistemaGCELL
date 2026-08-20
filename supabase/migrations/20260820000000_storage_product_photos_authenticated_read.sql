-- Extend product-photos read access to the `authenticated` role.
--
-- 20260810000502_storage_product_photos.sql granted SELECT to `anon` only.
-- Postgres RLS policies are role-scoped, never inherited between roles, so
-- a logged-in (authenticated) request against storage.objects for this
-- bucket was denied by default -- there was no gap in enforcement, just a
-- missing grant for a role the public catalog didn't use yet. Flagged
-- during ci-and-rls-tests' design phase and deferred to its own change.

create policy "Authenticated read access for product photos"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'product-photos');
