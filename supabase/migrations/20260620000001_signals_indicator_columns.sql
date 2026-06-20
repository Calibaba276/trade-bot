-- Add ICT indicator columns to signals table.
-- These are captured from strategy state at the moment build_verdict() fires
-- and stored for Glass Box dashboard replay and audit.

ALTER TABLE public.signals
  ADD COLUMN IF NOT EXISTS pdh            numeric,
  ADD COLUMN IF NOT EXISTS pdl            numeric,
  ADD COLUMN IF NOT EXISTS swept_high     numeric,
  ADD COLUMN IF NOT EXISTS swept_low      numeric,
  ADD COLUMN IF NOT EXISTS mss_swing_high numeric,
  ADD COLUMN IF NOT EXISTS mss_swing_low  numeric,
  ADD COLUMN IF NOT EXISTS fvg_top        numeric,
  ADD COLUMN IF NOT EXISTS fvg_bottom     numeric,
  ADD COLUMN IF NOT EXISTS fvg_confirmed  boolean,
  ADD COLUMN IF NOT EXISTS sweep_point    numeric,
  ADD COLUMN IF NOT EXISTS daily_bias     text,
  ADD COLUMN IF NOT EXISTS london_high    numeric,
  ADD COLUMN IF NOT EXISTS london_low     numeric;
