-- Product photos bucket: public read, service_role-only write.
-- service_role bypasses storage.objects RLS entirely, so an explicit
-- service_role write policy would be dead code implying anon writes were
-- ever considered — deliberately omitted.

insert into storage.buckets (id, name, public)
values ('product-photos', 'product-photos', true)
on conflict (id) do nothing;

create policy "Public read access for product photos"
  on storage.objects for select
  to anon
  using (bucket_id = 'product-photos');
