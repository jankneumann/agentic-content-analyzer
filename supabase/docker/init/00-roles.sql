-- Create Supabase-required PostgreSQL roles
-- These roles are expected by PostgREST, Storage API, and other Supabase services
-- IMPORTANT: supabase_admin must be created first — the supabase/postgres image
-- has built-in event triggers that reference it when creating extensions.

DO $$ BEGIN
  -- Internal admin role (required by supabase/postgres image triggers)
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_admin') THEN
    CREATE ROLE supabase_admin LOGIN PASSWORD 'postgres' SUPERUSER CREATEROLE CREATEDB REPLICATION BYPASSRLS;
    COMMENT ON ROLE supabase_admin IS 'Supabase internal admin role (required by image event triggers)';
  END IF;

  -- Auth admin role (required by auth service and storage)
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_auth_admin') THEN
    CREATE ROLE supabase_auth_admin LOGIN PASSWORD 'postgres' NOINHERIT CREATEROLE;
    COMMENT ON ROLE supabase_auth_admin IS 'Admin role for Supabase Auth service';
  END IF;

  -- Storage admin role (required by storage API)
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'supabase_storage_admin') THEN
    CREATE ROLE supabase_storage_admin LOGIN PASSWORD 'postgres' NOINHERIT CREATEROLE;
    COMMENT ON ROLE supabase_storage_admin IS 'Admin role for Supabase Storage API';
  END IF;

  -- API roles for PostgREST JWT-based auth
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
    COMMENT ON ROLE anon IS 'Role for unauthenticated API requests';
  END IF;

  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
    COMMENT ON ROLE authenticated IS 'Role for authenticated API requests';
  END IF;

  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    COMMENT ON ROLE service_role IS 'Role for service-level API access (bypasses RLS)';
  END IF;

  -- PostgREST login role that switches to anon/authenticated/service_role
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticator') THEN
    CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'postgres';
    COMMENT ON ROLE authenticator IS 'PostgREST login role';
  END IF;
END $$;

-- Grant role switching to authenticator (PostgREST needs this)
GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;

-- Grant admin roles to postgres (so it can operate as these roles)
GRANT supabase_admin TO postgres;
GRANT supabase_storage_admin TO postgres;
GRANT supabase_auth_admin TO postgres;
GRANT service_role TO postgres;

-- Grant database-level permissions for service roles to run migrations
GRANT CREATE ON DATABASE postgres TO supabase_storage_admin;
GRANT CREATE ON DATABASE postgres TO supabase_auth_admin;
