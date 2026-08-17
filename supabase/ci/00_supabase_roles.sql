-- CI ONLY. NOT a migration. Never applied to a real Supabase project.
-- Recreates the three Data API roles Supabase provisions outside
-- supabase/migrations/, so replay's GRANT statements resolve.
create role anon           nologin noinherit;
create role authenticated  nologin noinherit;
-- BYPASSRLS is load-bearing: the base tables have RLS enabled with zero
-- policies, so without it every service_role assertion would invert.
create role service_role    nologin noinherit bypassrls;

grant usage on schema public to anon, authenticated, service_role;
