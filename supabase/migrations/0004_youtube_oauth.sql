-- youtube_manager.ai — P2: hosted YouTube OAuth (per-user clients + channel connections)
-- Run once in Supabase: Dashboard → SQL Editor → New query → paste → Run.
--
-- Backend-only tables (no RLS policies): only the service_role key reads them, and
-- secrets/refresh-tokens are stored ENCRYPTED (Fernet, TM_MASTER_KEY) — a leak yields
-- nothing usable.

-- A user's OWN Google OAuth client (from their own GCP project) → their own quota.
create table if not exists public.user_oauth_clients (
  user_id                 uuid primary key references auth.users(id) on delete cascade,
  client_id               text not null,
  client_secret_ciphertext text not null,   -- Fernet(TM_MASTER_KEY, client_secret)
  created_at              timestamptz not null default now()
);
alter table public.user_oauth_clients enable row level security;   -- backend-only

-- One authorization of one channel by one client kind. A channel can have BOTH an
-- 'app' row (shared quota) and a 'user' row (own quota) → powers the single-upload
-- shared→BYO fallback.
create table if not exists public.channel_connections (
  id                       uuid primary key default gen_random_uuid(),
  user_id                  uuid not null references auth.users(id) on delete cascade,
  channel_id               text not null,
  client_kind              text not null check (client_kind in ('app','user')),
  title                    text,
  handle                   text,
  thumbnail                text,
  refresh_token_ciphertext text not null,   -- Fernet(TM_MASTER_KEY, refresh_token)
  created_at               timestamptz not null default now(),
  unique (user_id, channel_id, client_kind)  -- powers upsert (merge-duplicates)
);
create index if not exists channel_conn_user on public.channel_connections (user_id);
alter table public.channel_connections enable row level security;  -- backend-only
