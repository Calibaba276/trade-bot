-- broker_accounts.force_spawn — manual respawn override
--
-- The orchestrator (backend/services/orchestrator.py) selects accounts that are
-- either in a runnable status OR have force_spawn = true, and clears the flag
-- after the worker is spawned (_clear_force_spawn_flag). The column was being
-- read/written by the backend but never existed in the schema — add it.
--
-- Non-breaking: nullable-with-default boolean, defaults to false so existing rows
-- are unaffected and only accounts explicitly flagged are force-respawned.

alter table public.broker_accounts
  add column if not exists force_spawn boolean not null default false;

-- Partial index so the orchestrator's `force_spawn.eq.true` filter stays cheap
-- as the table grows (only the rare flagged rows are indexed).
create index if not exists idx_broker_accounts_force_spawn
  on public.broker_accounts (force_spawn)
  where force_spawn = true;
