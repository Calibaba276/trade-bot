-- broker_accounts.plan + enabled_markets — per-account plan & market access
--
-- Plans gate which markets an account may trade. Signals are broadcast to every
-- worker over one Redis channel; each worker filters by its account's
-- enabled_markets (see backend/config/markets.py + backend/services/worker.py).
--
--   plan            : 'starter' | 'pro' — the access ceiling
--   enabled_markets : the markets the user actually wants traded. Defaults to
--                     ALL markets the plan permits; the user can opt out of any.
--
-- Market sets (mirror backend/config/markets.py):
--   starter -> EURUSD, XAUUSD
--   pro     -> EURUSD, XAUUSD, NAS100, US30, SPX500, BTCUSD, ETHUSD
--
-- Non-breaking: both columns are added with safe defaults. A backfill seeds the
-- FIRST account created as 'pro' and every other existing account as 'starter'
-- (per current product decision while billing is not yet live).

alter table public.broker_accounts
  add column if not exists plan text not null default 'starter';

alter table public.broker_accounts
  add column if not exists enabled_markets text[] not null default '{}';

-- Constrain plan to known values (guarded so re-running the migration is safe).
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'broker_accounts_plan_check'
  ) then
    alter table public.broker_accounts
      add constraint broker_accounts_plan_check
      check (plan in ('starter', 'pro'));
  end if;
end $$;

-- One-time backfill of existing rows: first account -> pro, the rest -> starter.
-- Ordered by created_at when that column exists, else by id, so "first" is the
-- earliest-added account. Only touches rows still on the default empty market
-- set, so it never clobbers a user's later opt-out choices on re-run.
do $$
declare
  order_col text;
  first_id  uuid;
begin
  select case
           when exists (
             select 1 from information_schema.columns
             where table_schema = 'public'
               and table_name = 'broker_accounts'
               and column_name = 'created_at'
           ) then 'created_at'
           else 'id'
         end
    into order_col;

  execute format(
    'select id from public.broker_accounts order by %I asc nulls last limit 1',
    order_col
  ) into first_id;

  if first_id is null then
    return;  -- no accounts yet; new rows handled by the app at creation time
  end if;

  -- First account -> Pro, all Pro markets enabled.
  update public.broker_accounts
     set plan = 'pro',
         enabled_markets = array['EURUSD','XAUUSD','NAS100','US30','SPX500','BTCUSD','ETHUSD']
   where id = first_id
     and enabled_markets = '{}';

  -- Every other existing account -> Starter, all Starter markets enabled.
  update public.broker_accounts
     set plan = 'starter',
         enabled_markets = array['EURUSD','XAUUSD']
   where id <> first_id
     and enabled_markets = '{}';
end $$;
