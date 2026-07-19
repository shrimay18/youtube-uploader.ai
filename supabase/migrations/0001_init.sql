-- youtube_manager.ai — cloud layer schema
-- Run this once in Supabase: Dashboard → SQL Editor → New query → paste → Run.
--
-- WHAT THIS STORES (admin-visible, NON-secret only):
--   profiles      : one row per user (identity + activity)
--   usage_events  : lightweight telemetry (what happened, when) — NO content, NO keys
--
-- WHAT IT NEVER STORES: API keys, transcripts, video content, titles/descriptions.
-- Those stay encrypted on the user's own device and are never uploaded.
--
-- SECURITY: Row Level Security is ON. A signed-in user can only read/write THEIR OWN
-- rows. Only the service_role key (which lives only in your admin backend, never on a
-- user device) can read across all users for the admin dashboard.

-- ---------------------------------------------------------------------------
-- profiles: mirror of auth.users with the fields your admin view needs
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  email       text,
  name        text,
  avatar_url  text,
  created_at  timestamptz not null default now(),
  last_active timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "own profile read"   on public.profiles;
drop policy if exists "own profile write"  on public.profiles;
drop policy if exists "own profile update" on public.profiles;

create policy "own profile read"   on public.profiles
  for select using (auth.uid() = id);
create policy "own profile write"  on public.profiles
  for insert with check (auth.uid() = id);
create policy "own profile update" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- Auto-create a profile row the moment a user first signs in with Google.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'),
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do update
    set email = excluded.email,
        name  = coalesce(excluded.name, public.profiles.name),
        last_active = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- usage_events: metadata-only telemetry
-- ---------------------------------------------------------------------------
create table if not exists public.usage_events (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  type        text not null,                 -- e.g. 'generate', 'publish', 'app_open'
  model       text,                          -- e.g. 'gemini', 'groq' (optional)
  video_count int  not null default 1,
  meta        jsonb not null default '{}'::jsonb,  -- small, non-sensitive extras only
  created_at  timestamptz not null default now()
);

create index if not exists usage_events_user_time
  on public.usage_events (user_id, created_at desc);
create index if not exists usage_events_type_time
  on public.usage_events (type, created_at desc);

alter table public.usage_events enable row level security;

drop policy if exists "own events read"   on public.usage_events;
drop policy if exists "own events insert" on public.usage_events;

create policy "own events read"   on public.usage_events
  for select using (auth.uid() = user_id);
create policy "own events insert" on public.usage_events
  for insert with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Admin dashboard helper (query with the service_role key from your backend):
--
--   select date_trunc('week', created_at) wk,
--          count(distinct user_id) active_users,
--          sum(video_count)       videos
--   from public.usage_events
--   group by 1 order by 1 desc;
--
--   select p.email, p.created_at, p.last_active,
--          count(e.*) filter (where e.type='generate') generations
--   from public.profiles p
--   left join public.usage_events e on e.user_id = p.id
--   group by 1,2,3 order by p.last_active desc;
-- ---------------------------------------------------------------------------
