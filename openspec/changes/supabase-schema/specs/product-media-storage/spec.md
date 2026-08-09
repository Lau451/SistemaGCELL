# Product Media Storage Specification

## Purpose

Defines a single Supabase Storage bucket for product photos: public read
access for the catalog, write access restricted to `service_role`.

## Requirements

### Requirement: Product Photos Bucket Is Publicly Readable

The product-photos bucket MUST be declared in `config.toml` and MUST allow
any client, including `anon`, to read/download objects without
authentication.

#### Scenario: anon fetches a public photo URL

- GIVEN a product photo object exists in the bucket
- WHEN an unauthenticated client requests its public URL
- THEN the object MUST be returned successfully

### Requirement: Photo Writes Are Restricted to Service Role

Only `service_role` MUST be able to upload, update, or delete objects in the
product-photos bucket; `anon` and any authenticated non-admin client MUST be
denied these operations.

#### Scenario: anon upload rejected

- GIVEN the `anon` role
- WHEN it attempts to upload an object to the product-photos bucket
- THEN the operation MUST fail on a storage policy denial

#### Scenario: service_role upload succeeds

- GIVEN the `service_role` role
- WHEN it uploads a new product photo object
- THEN the operation MUST succeed and the object MUST become publicly
  readable immediately
