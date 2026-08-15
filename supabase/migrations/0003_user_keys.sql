-- youtube_manager.ai — P1: per-user encrypted key storage (hosted SaaS)
-- Run once in Supabase: Dashboard → SQL Editor → New query → paste → Run.
--
-- Stores each user's LLM API keys (and, later, their own YouTube OAuth creds)
-- ENCRYPTED with the backend master key (TM_MASTER_KEY). These tables are
-- BACKEND-ONLY: there are deliberately no RLS policies, so the public anon key
-- can never read a key row — only the service_role key (backend) can, and even a
-- leak yields ciphertext that's useless without the master key.

create table if not exists public.user_keys (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  provider       text not null,          -- 'gemini'|'openai'|'anthropic'|'groq'|'custom'
  ext_id         text,                   -- stable app id for custom providers
  label          text,                   -- display name for custom providers
  model          text,                   -- optional (custom / override)
  base_url       text,                   -- custom OpenAI-compatible base
  key_ciphertext text not null,          -- Fernet(TM_MASTER_KEY, api_key)
  position       int  not null default 0,
  created_at     timestamptz not null default now()
);
create index if not exists user_keys_user_pos on public.user_keys (user_id, position);

alter table public.user_keys enable row level security;
-- No policies on purpose → anon/authenticated keys get zero rows. Backend uses service_role.

create table if not exists public.user_prefs (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  engine_order text[] not null default '{}',   -- provider preference tokens
  updated_at   timestamptz not null default now()
);

alter table public.user_prefs enable row level security;
-- Backend-only, same as user_keys.
