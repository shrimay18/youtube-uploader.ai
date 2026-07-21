-- youtube_manager.ai — feedback table
-- Run this once in Supabase: Dashboard → SQL Editor → New query → paste → Run.
--
-- Stores user feedback / reviews. Anyone (a signed-in user OR an anonymous
-- visitor on the landing page) can SUBMIT feedback. Nobody can READ it with the
-- public anon key — only the admin backend, using the service_role key (which
-- bypasses RLS and lives only on the creator's machine), can list reviews.

create table if not exists public.feedback (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  anonymous   boolean not null default true,
  rating      int,                          -- 1..5 mood (optional)
  name        text,                         -- only when not anonymous
  email       text,                         -- only when not anonymous
  mobile      text,                         -- optional, only when not anonymous
  message     text not null,
  user_id     uuid references auth.users (id) on delete set null,  -- set when signed in
  meta        jsonb not null default '{}'::jsonb
);

create index if not exists feedback_time on public.feedback (created_at desc);

alter table public.feedback enable row level security;

drop policy if exists "anyone can submit feedback" on public.feedback;

-- Allow both anonymous visitors and signed-in users to INSERT feedback.
create policy "anyone can submit feedback" on public.feedback
  for insert to anon, authenticated with check (true);

-- NOTE: there is deliberately NO select/update/delete policy, so the public keys
-- can never read feedback. The admin dashboard reads it with the service_role key.
