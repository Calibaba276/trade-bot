-- Glass Box frontend — onboarding progress
-- Account-scoped, syncs across devices: a user who starts onboarding on one
-- device resumes at the same step on another. RLS: auth.uid() = user_id.

create table if not exists public.user_onboarding (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  step       int     not null default 0,      -- current wizard step index
  completed  boolean not null default false,  -- finished or skipped
  updated_at timestamptz default now()
);

alter table public.user_onboarding enable row level security;

drop policy if exists "user_isolation" on public.user_onboarding;
create policy "user_isolation" on public.user_onboarding
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
