-- Tables this repository reads but does not own, in the shape the test suite
-- and the staging bootstrap run on (ash-template's priv/repo/shared_tables.sql).
-- Production has the real table: regent_names.platform_human_users is owned by
-- Regents. Nothing here runs against production. Every statement is idempotent,
-- so the suite loads this file on every run.
CREATE SCHEMA IF NOT EXISTS regent_names;
CREATE TABLE IF NOT EXISTS regent_names.platform_human_users (
    id bigserial PRIMARY KEY,
    privy_user_id varchar(255) NOT NULL UNIQUE,
    wallet_address varchar(255),
    wallet_addresses varchar(255)[] NOT NULL DEFAULT '{}',
    world_human_id varchar(255) UNIQUE,
    world_verified_at timestamp(0) without time zone,
    display_name varchar(80),
    avatar jsonb,
    created_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);
