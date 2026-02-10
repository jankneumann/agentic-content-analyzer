-- Set up storage schema and permissions for Supabase Storage API
-- The storage service runs its own migrations, but needs the schema and grants to exist

CREATE SCHEMA IF NOT EXISTS storage;

-- Grant schema access to storage admin and service role
GRANT ALL ON SCHEMA storage TO supabase_storage_admin;
GRANT USAGE ON SCHEMA storage TO anon, authenticated, service_role;

-- Grant table access (storage service creates its own tables via migrations)
ALTER DEFAULT PRIVILEGES IN SCHEMA storage
  GRANT ALL ON TABLES TO supabase_storage_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA storage
  GRANT SELECT ON TABLES TO anon, authenticated, service_role;

-- Grant sequence access
ALTER DEFAULT PRIVILEGES IN SCHEMA storage
  GRANT USAGE ON SEQUENCES TO supabase_storage_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA storage
  GRANT USAGE ON SEQUENCES TO anon, authenticated, service_role;
