-- Glass Box frontend — schema additions
-- Strategy: reuse existing tables (broker_accounts = "accounts"); create only what's missing.
-- RLS is enabled ONLY on the new tables here. Existing backend tables (broker_accounts,
-- signals, executions, execution_events) are left without RLS until we confirm the backend's
-- Supabase key is the service_role key (otherwise enabling RLS would break the live bot).
-- Ownership model: account-scoped — new rows carry user_id; auth.uid() = user_id.

------------------------------------------------------------------------------
-- 1. Account ownership prep (non-breaking: nullable column, no RLS change here)
------------------------------------------------------------------------------
alter table public.broker_accounts
  add column if not exists user_id uuid references auth.users(id) on delete set null;

------------------------------------------------------------------------------
-- 2. candles — OHLCV market data for the chart
------------------------------------------------------------------------------
create table if not exists public.candles (
  id          bigserial primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  pair        text   not null,
  timeframe   text   not null,            -- '1m' | '5m' | '15m' | '1h'
  "time"      bigint not null,            -- ms UTC, candle open time
  open        numeric,
  high        numeric,
  low         numeric,
  close       numeric,
  volume      numeric,
  created_at  timestamptz default now(),
  unique (user_id, pair, timeframe, "time")
);
create index if not exists idx_candles_user_pair_tf_time
  on public.candles(user_id, pair, timeframe, "time");

------------------------------------------------------------------------------
-- 3. trade_events — granular per-timeframe pattern-detection stream
------------------------------------------------------------------------------
create table if not exists public.trade_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  account_id  uuid references public.broker_accounts(id) on delete set null,
  signal_id   uuid references public.signals(id) on delete set null,
  pair        text   not null,
  "timestamp" bigint not null,            -- ms UTC
  timeframe   text   not null,            -- '1m' | '5m' | '15m' | '1h'
  type        text   not null,            -- pattern_detected | entry | exit | invalidated
  pattern     text,                       -- FVG | OB | MSS | BOS
  price       numeric,
  high        numeric,
  low         numeric,
  volume      numeric,
  ohlcv       jsonb,
  confidence  numeric,
  metadata    jsonb,
  created_at  timestamptz default now()
);
create index if not exists idx_trade_events_user_pair_time
  on public.trade_events(user_id, pair, "timestamp");
create index if not exists idx_trade_events_tf_time
  on public.trade_events(timeframe, "timestamp");

------------------------------------------------------------------------------
-- 4. replay_sessions — user-owned scrub/playback state
------------------------------------------------------------------------------
create table if not exists public.replay_sessions (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid references auth.users(id) on delete cascade,
  trade_id           uuid references public.trade_events(id) on delete set null,
  pair               text,
  start_time         bigint,
  end_time           bigint,
  "current_time"     bigint,
  playback_speed     int  default 1,
  selected_timeframe text default '5m',
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);
create index if not exists idx_replay_sessions_user
  on public.replay_sessions(user_id);

------------------------------------------------------------------------------
-- 5. Row-Level Security — NEW tables only (backend tables untouched)
------------------------------------------------------------------------------
alter table public.candles         enable row level security;
alter table public.trade_events    enable row level security;
alter table public.replay_sessions enable row level security;

drop policy if exists "user_isolation" on public.candles;
create policy "user_isolation" on public.candles
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "user_isolation" on public.trade_events;
create policy "user_isolation" on public.trade_events
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "user_isolation" on public.replay_sessions;
create policy "user_isolation" on public.replay_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

------------------------------------------------------------------------------
-- 6. Realtime — let the frontend subscribe to live trade events
------------------------------------------------------------------------------
alter publication supabase_realtime add table public.trade_events;
