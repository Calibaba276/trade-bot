# Glass Box — Frontend Reference

Condensed from ARCHITECTURE.md + IMPLEMENTATION-GUIDE.md. Source of truth for frontend engineers.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React 18 + TypeScript |
| State | Zustand |
| Charts | TradingView Lightweight Charts v5 |
| Styling | Tailwind CSS + shadcn/ui |
| Data Fetching | React Query + Supabase SDK |
| Auth | Supabase Auth (JWT, email/password) |
| Database | Supabase (Postgres + Realtime) |
| Server Logic | Supabase Edge Functions |

---

## Core TypeScript Types

```typescript
interface TradeEvent {
  id: string;
  user_id: string;
  account_id: string;
  timestamp: number;           // ms UTC
  timeframe: "1m" | "5m" | "15m" | "1h";
  type: "pattern_detected" | "entry" | "exit" | "invalidated";
  pattern?: "FVG" | "OB" | "MSS" | "BOS";
  price: number;
  high: number;
  low: number;
  volume: number;
  ohlcv: { o: number; h: number; l: number; c: number; v: number };
  confidence?: number;
  metadata?: { parentTimeframeConfirm?: string; entryReason?: string };
}

interface ReplaySession {
  id: string;
  user_id: string;
  trade_id: string;
  pair: string;
  start_time: number;
  end_time: number;
  events: TradeEvent[];
  current_time: number;
  playback_speed: number;
  created_at: string;
}
```

---

## Supabase Schema

```sql
-- Existing tables (do NOT recreate): broker_accounts, signals, executions
-- Tables below are for frontend chart/replay feature only

create table trade_events (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  account_id   uuid references broker_accounts(id) on delete cascade,
  pair         text not null,
  timestamp    bigint not null,
  timeframe    text not null,
  type         text not null,
  pattern      text,
  price        numeric,
  high         numeric,
  low          numeric,
  volume       numeric,
  ohlcv        jsonb,
  confidence   numeric,
  metadata     jsonb,
  created_at   timestamptz default now()
);

create table candles (
  id          bigserial primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  pair        text not null,
  timeframe   text not null,
  time        bigint not null,
  open        numeric,
  high        numeric,
  low         numeric,
  close       numeric,
  volume      numeric,
  unique(pair, timeframe, time)
);

create table replay_sessions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users(id) on delete cascade,
  trade_id        uuid references trade_events(id),
  pair            text,
  start_time      bigint,
  end_time        bigint,
  current_time    bigint,
  playback_speed  int default 1,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

-- Indexes
create index idx_trade_events_user_pair_time on trade_events(user_id, pair, timestamp);
create index idx_candles_pair_tf_time on candles(pair, timeframe, time);

-- RLS (user sees only their rows)
alter table trade_events enable row level security;
alter table candles enable row level security;
alter table replay_sessions enable row level security;
create policy "user_isolation" on trade_events for all using (auth.uid() = user_id);
create policy "user_isolation" on candles for all using (auth.uid() = user_id);
create policy "user_isolation" on replay_sessions for all using (auth.uid() = user_id);
```

---

## Supabase Client

```typescript
// lib/supabase.ts
import { createClient } from "@supabase/supabase-js";
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
```

---

## Live Data Subscription

```typescript
// Subscribe to new trade events in real time
function useLiveTradeEvents(pair: string) {
  const { addEvent } = useReplayStore();
  useEffect(() => {
    const channel = supabase
      .channel("live-trade-events")
      .on("postgres_changes", {
        event: "INSERT",
        schema: "public",
        table: "trade_events",
        filter: `pair=eq.${pair}`,
      }, (payload) => addEvent(payload.new as TradeEvent))
      .subscribe();
    return () => supabase.removeChannel(channel);
  }, [pair]);
}
```

Python backend inserts via `supabase-py` service role key → Realtime fires to frontend within ~100ms.

---

## Zustand State

```typescript
interface ReplayStore {
  selectedTimeframe: "1m" | "5m" | "15m" | "1h";
  currentTime: number;
  isPlaying: boolean;
  playbackSpeed: number;
  events: TradeEvent[];
  priceDataByTimeframe: Record<string, Candle[]>;
  setCurrentTime: (time: number) => void;
  togglePlayback: () => void;
  loadEventsForDateRange: (start: Date, end: Date) => Promise<void>;
}
```

---

## Pattern Color Coding

| Element | Color | ICT Meaning |
|---------|-------|-------------|
| FVG | Amber | Fair value gap (imbalance) |
| OB | Blue | Order block |
| MSS | Teal | Market structure shift |
| Entry | Green | Long / bullish |
| Exit | Red | Short / bearish |
| Invalidated | Gray | Pattern broke before entry |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Chart render | < 16ms (60 FPS) |
| Scrubber drag | Smooth 60 FPS |
| Event log scroll | Virtualized (visible rows only) |
| Historical load | < 2s for one week of data |
| Live event latency | < 100ms (Supabase Realtime) |

---

## Backend → Frontend Data Flow

```python
# Python strategy runner emits candle + event on each bar close
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def emit_candle(pair: str, timeframe: str, ohlcv: dict):
    supabase.table("candles").upsert({
        "pair": pair, "timeframe": timeframe,
        "time": ohlcv["time"], **ohlcv
    }).execute()

def emit_trade_event(event: dict):
    supabase.table("trade_events").insert(event).execute()
```

---

## UI Layout Reference

```
┌─────────────────────────────────────────────────────────┐
│ CHART (70% of screen)                                   │
│  TradingView Lightweight Charts + pattern overlays      │
│  FVG: amber rectangles | OB: blue zones | MSS: teal lines│
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ PLAYBACK CONTROLS (Replay Mode only)                    │
│  [⏮] ── scrubber ── [⏭]  [⏯] 1x/2x/4x  TF selector  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ EVENT LOG (right sidebar or below chart)                │
│  14:32 | ENTRY    | FVG+MSS @ 1.0875 | +52p            │
│  14:31 | DETECTED | FVG (5m)                            │
└─────────────────────────────────────────────────────────┘
```
