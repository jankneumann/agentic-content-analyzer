-- Enable PostgreSQL extensions required by Supabase services

-- Create extensions schema for cleaner organization
CREATE SCHEMA IF NOT EXISTS extensions;

-- Core extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS "pgcrypto" SCHEMA extensions;

-- Make extensions schema accessible to all roles
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;

-- Add extensions schema to search path so functions are accessible without schema prefix
ALTER DATABASE postgres SET search_path TO public, extensions;
