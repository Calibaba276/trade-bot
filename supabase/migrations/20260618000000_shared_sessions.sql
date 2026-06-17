-- Glass Box frontend — server-side shareable audit trails
--
-- Replaces the URL-encoded share payload (utils/share.ts) with a server-stored
-- row. The B2B2C trust mechanism only holds if a recipient cannot fabricate or
-- tamper with the data: the snapshot is written once by an authenticated user
-- and served read-only from here, so the link is `/share/:uuid` and the
-- recipient can never craft a fake one or modify what they were sent.
--
-- The snapshot itself lives in `payload` (jsonb): trades are derived from the
-- raw trade_event stream client-side, so there is no trades table to reference
-- by id. Storing the immutable snapshot tied to user_id is the audit guarantee.

create table if not exists public.shared_sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  title      text not null default 'Shared Audit',
  payload    jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists shared_sessions_user_id_idx on public.shared_sessions(user_id);

alter table public.shared_sessions enable row level security;

-- Anyone (including anonymous visitors) may read a share by its uuid — that is
-- the whole point of a public audit link. The uuid is the unguessable capability.
drop policy if exists "public_read" on public.shared_sessions;
create policy "public_read" on public.shared_sessions
  for select using (true);

-- Only the authenticated owner may create a share, and only for themselves.
drop policy if exists "owner_insert" on public.shared_sessions;
create policy "owner_insert" on public.shared_sessions
  for insert with check (auth.uid() = user_id);

-- Owners may delete their own shares (revoke a link). No update policy: a share
-- snapshot is immutable once created — that immutability is the trust property.
drop policy if exists "owner_delete" on public.shared_sessions;
create policy "owner_delete" on public.shared_sessions
  for delete using (auth.uid() = user_id);
