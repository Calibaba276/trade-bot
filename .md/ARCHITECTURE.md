# Glass Box Trading Engine — Frontend Architecture (Supabase Edition)

## Overview

A multi-timeframe replay system that streams live trade events and allows users to scrub backward through execution history, seeing exactly how the bot detected patterns across 1m, 5m, 15m, and 1h timeframes.

**Core philosophy:** Deterministic, transparent execution. Every trade is explained by visible pattern detection and ICT rules. Users don't trust the bot — they verify it.

---

## Data Model

### Trade Event (Backend → Frontend)

```typescript
interface TradeEvent {
  id: string;                           // UUID (Supabase primary key)
  user_id: string;                      // FK → auth.users.id (RLS enforced)
  account_id: string;                   // FK → accounts.id
  timestamp: number;                    // milliseconds UTC
  timeframe: "1m" | "5m" | "15m" | "1h";
  type: "pattern_detected" | "entry" | "exit" | "invalidated";
  pattern?: "FVG" | "OB" | "MSS" | "BOS";
  price: number;
  high: number;
  low: number;
  volume: number;
  ohlcv: { o: number; h: number; l: number; c: number; v: number };
  confidence?: number;                  // 0-1 pattern strength
  metadata?: {
    parentTimeframeConfirm?: string;    // "5m FVG confirmed by 1h OB"
    entryReason?: string;
  };
}

interface ReplaySession {
  id: string;                           // UUID
  user_id: string;                      // FK → auth.users.id
  trade_id: string;
  pair: string;
  start_time: number;
  end_time: number;
  events: TradeEvent[];
  current_time: number;                 // Scrub position
  playback_speed: number;               // 1, 2, 4, etc.
  created_at: string;                   // Supabase auto timestamp
}
```

---

## Supabase Schema

The live schema is defined by three migration files under `supabase/migrations/`. The tables below reflect what is actually deployed.

### Tables

| Table | RLS | Description |
|-------|-----|-------------|
| `broker_accounts` | `auth.uid() = user_id` | MT5 account credentials + strategy config (rr_ratio, drawdown %, breakeven buffer) per user |
| `candles` | `auth.uid() = user_id` | OHLCV bars (1m, 5m, 15m, 1h); unique on `(pair, timeframe, time)` |
| `trade_events` | `auth.uid() = user_id` | Pattern detections, entries, exits; Supabase Realtime enabled |
| `signals` | service role write / worker read | Verdicts built by ICT strategy; consumed by `worker.py` via Redis |
| `replay_sessions` | `auth.uid() = user_id` | Scrub position, playback speed, selected timeframe |
| `user_onboarding` | `auth.uid() = user_id` | Wizard step index and completion flag, synced across devices |
| `shared_sessions` | public read / owner insert+delete | Immutable audit snapshots; anyone reads by UUID, only owner creates or deletes |

> **Note on `accounts` vs `broker_accounts`:** Earlier drafts of this doc referenced a generic `accounts` table. The actual table is `broker_accounts`, which also stores per-account strategy configuration (risk amount, RR ratio, drawdown %, etc.).

### Row-Level Security

All tables have RLS enabled. Each user sees only their own rows (`auth.uid() = user_id`). `shared_sessions` uses a custom policy: public SELECT (UUID is the capability), owner-only INSERT and DELETE, no UPDATE (immutable by design).

> Supabase Auth handles JWTs natively; RLS policies reference `auth.uid()` directly. The frontend uses the **anon key**; the Python backend uses the **service role key** (from Azure Key Vault) to write rows with the correct `user_id`.

---

## UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ CHART AREA                                              │
│ ┌──────────────────────────────────────────────────────┐│
│ │ TradingView Lightweight Charts (candles)              ││
│ │ - Overlays: FVG boxes, OB rectangles, MSS lines      ││
│ │ - Entry/exit markers (color-coded by reason)          ││
│ │ - Updates as currentTime advances                     ││
│ └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PLAYBACK CONTROLS                                       │
│ [⏮] ─── SCRUBBER (hover = timestamp) ─── [⏭]        │
│ [⏯] Play | Speed: 1x▼ | Timeframe: 5m▼ | [Log]       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ EVENT LOG (Right sidebar or below)                      │
│ 14:32 │ ENTRY       │ FVG + MSS @ 1.0875   (+52p)      │
│ 14:31 │ DETECTED    │ Fair Value Gap (5m)              │
│ 14:30 │ DETECTED    │ Order Block (1h confirm)        │
│ 14:29 │ DETECTED    │ Market Struct Shift (15m)       │
└─────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Chart Component

Responsibility: Render candles + pattern overlays for selected timeframe.

```typescript
function TradeReplayChart({ events, currentTime, selectedTimeframe }) {
  const visibleCandles = priceData[selectedTimeframe]
    .filter(c => c.time <= currentTime);

  const visiblePatterns = events.filter(
    e => e.timeframe === selectedTimeframe &&
         e.timestamp <= currentTime
  );

  // On each render:
  // 1. Update candle series
  // 2. Clear old overlays
  // 3. Draw FVG rectangles
  // 4. Draw OB zones
  // 5. Draw MSS lines
  // 6. Mark entry/exit with pins
}
```

**Pattern rendering:**
- **FVG:** Semi-transparent rectangle between high and low
- **OB:** Thicker rectangle, more saturated color
- **MSS:** Dashed horizontal line at swing point
- **Entry/Exit:** Vertical pin with label + reason

### 2. Playback Controls

**A. Timeframe Selector**

```typescript
const [selectedTimeframe, setSelectedTimeframe] =
  useState<"1m" | "5m" | "15m" | "1h">("5m");
// Chart re-renders candles for new TF
// Event log filters to new TF
```

**B. Time Scrubber**

```typescript
const [currentTime, setCurrentTime] = useState(startTime);

// On play: increment currentTime by (deltaMs × playbackSpeed) every 100ms
// On scrub: set currentTime directly (pause playback)
// Chart re-renders to show patterns up to currentTime

const handleScrub = (position: number) => {
  setCurrentTime(position);
  setIsPlaying(false);  // Pause on manual scrub
};
```

**C. Speed Control**

```typescript
const [playbackSpeed, setPlaybackSpeed] = useState(1);
// Options: 1x, 2x, 4x
// Affects interval tick rate in play loop
```

### 3. Event Log (Timeline)

Display: Chronological list of all events up to `currentTime`.

```typescript
function EventLog({ events, currentTime, selectedTimeframe }) {
  const visibleEvents = events
    .filter(e => e.timestamp <= currentTime)
    .sort((a, b) => b.timestamp - a.timestamp);  // newest first

  return (
    <div>
      {visibleEvents.map(event => (
        <EventCard key={event.id}>
          <time>{formatTime(event.timestamp)}</time>
          <type>{event.type}</type>
          <pattern>{event.pattern}</pattern>
          <reason>{event.metadata?.entryReason}</reason>
          <pnl>{event.pnl}</pnl>
        </EventCard>
      ))}
    </div>
  );
}
```

### 4. Context Cascade (Advanced)

```typescript
function ContextCascade({ event, allEvents }) {
  if (event.type !== "entry") return null;

  const parentEvent = allEvents.find(e =>
    e.timestamp <= event.timestamp &&
    e.pattern === event.metadata?.parentTimeframeConfirm &&
    e.timeframe > event.timeframe
  );

  return (
    <div>
      <p>Entry triggered on {event.timeframe}</p>
      {parentEvent && (
        <p>✓ Confirmed by {parentEvent.pattern} on {parentEvent.timeframe}</p>
      )}
    </div>
  );
}
```

---

## State Management (Zustand)

```typescript
interface ReplayStore {
  // UI State
  selectedTimeframe: "1m" | "5m" | "15m" | "1h";
  currentTime: number;
  isPlaying: boolean;
  playbackSpeed: number;
  showEventLog: boolean;

  // Data
  events: TradeEvent[];
  priceDataByTimeframe: Record<string, Candle[]>;

  // Actions
  setSelectedTimeframe: (tf: string) => void;
  setCurrentTime: (time: number) => void;
  togglePlayback: () => void;
  setPlaybackSpeed: (speed: number) => void;
  loadEventsForDateRange: (start: Date, end: Date) => Promise<void>;
  persistReplaySession: () => Promise<void>;       // NEW: save to Supabase
}

const useReplayStore = create<ReplayStore>((set, get) => ({
  selectedTimeframe: "5m",
  currentTime: 0,
  isPlaying: false,
  playbackSpeed: 1,
  showEventLog: true,
  events: [],
  priceDataByTimeframe: {},

  setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),
  setCurrentTime: (time) => set({ currentTime: time }),
  togglePlayback: () => set(s => ({ isPlaying: !s.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),

  loadEventsForDateRange: async (start, end) => {
    // Supabase query — RLS ensures only the authed user's rows are returned
    const { data, error } = await supabase
      .from("trade_events")
      .select("*")
      .gte("timestamp", start.getTime())
      .lte("timestamp", end.getTime())
      .order("timestamp", { ascending: true });

    if (error) throw error;

    const { data: candles } = await supabase
      .from("candles")
      .select("*")
      .gte("time", start.getTime())
      .lte("time", end.getTime())
      .order("time", { ascending: true });

    const priceDataByTimeframe = groupBy(candles, "timeframe");
    set({ events: data, priceDataByTimeframe });
  },

  // Persist scrub position + speed so users can resume later
  persistReplaySession: async () => {
    const { currentTime, playbackSpeed } = get();
    await supabase
      .from("replay_sessions")
      .upsert({ current_time: currentTime, playback_speed: playbackSpeed })
      .match({ id: sessionId });
  },
}));
```

---

## Auth — Supabase Auth

```typescript
// lib/supaclient.ts
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

// Auth helpers
export const signIn = (email: string, password: string) =>
  supabase.auth.signInWithPassword({ email, password });

export const signOut = () => supabase.auth.signOut();

export const getSession = () => supabase.auth.getSession();
```

> Supabase Auth issues JWTs automatically. RLS policies consume `auth.uid()` server-side — no manual JWT forwarding required.

---

## Real-Time — Supabase Realtime

Supabase Realtime lets you subscribe to Postgres changes directly, eliminating a separate WebSocket server entirely.

```typescript
// Subscribe to new trade events for the current pair in real time
function useLiveTradeEvents(pair: string) {
  const { addEvent } = useReplayStore();

  useEffect(() => {
    const channel = supabase
      .channel("live-trade-events")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "trade_events",
          filter: `pair=eq.${pair}`,
        },
        (payload) => {
          addEvent(payload.new as TradeEvent);
        }
      )
      .subscribe();

    return () => supabase.removeChannel(channel);
  }, [pair]);
}
```

The Python backend writes events directly to Supabase (via `supabase-py`). The frontend subscription fires within ~50–100ms of the INSERT — no bespoke WebSocket infra needed.

```python
# Python backend — emit trade events
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def emit_trade_event(event: dict):
    supabase.table("trade_events").insert(event).execute()
```

---

## API Layer — Supabase as Backend

The `/api/replay/events` REST endpoint is replaced by direct Supabase queries. Edge Functions cover any logic that needs server-side computation.

### Historical Events (replaces `GET /api/replay/events`)

```typescript
// Direct Supabase query — no custom API route needed
async function fetchReplayData(pair: string, start: Date, end: Date) {
  const [{ data: events }, { data: candles }] = await Promise.all([
    supabase
      .from("trade_events")
      .select("*")
      .eq("pair", pair)
      .gte("timestamp", start.getTime())
      .lte("timestamp", end.getTime()),

    supabase
      .from("candles")
      .select("*")
      .eq("pair", pair)
      .gte("time", start.getTime())
      .lte("time", end.getTime()),
  ]);

  return {
    events,
    prices: groupBy(candles, "timeframe"),
  };
}
```

### Replay Session Save/Load

```typescript
// Save scrub position to Supabase
async function saveReplaySession(sessionId: string, partial: Partial<ReplaySession>) {
  await supabase
    .from("replay_sessions")
    .upsert({ id: sessionId, ...partial, updated_at: new Date().toISOString() });
}

// Restore on next visit
async function loadReplaySession(sessionId: string): Promise<ReplaySession | null> {
  const { data } = await supabase
    .from("replay_sessions")
    .select("*")
    .eq("id", sessionId)
    .single();
  return data;
}
```

### Supabase Edge Function — Stats Aggregation

For heavier aggregations (win rate, average R:R per pattern) use an Edge Function rather than pulling raw rows to the client:

```typescript
// supabase/functions/trade-stats/index.ts
import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js";

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  const { data } = await supabase
    .from("trade_events")
    .select("pattern, type, metadata")
    .eq("type", "exit");

  const stats = aggregateByPattern(data);
  return new Response(JSON.stringify(stats), {
    headers: { "Content-Type": "application/json" },
  });
});
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Framework | React 19 + TypeScript | Type safety, real-time updates |
| State | Zustand | Minimal boilerplate, fast |
| Charts | TradingView Lightweight Charts v5 | Lightweight, real-time candles, easy overlays |
| Styling | Tailwind CSS 3 | Fast iteration, dark mode out-of-box |
| Data Fetching | TanStack Query v5 + Supabase SDK | Caching, Supabase-aware re-fetching |
| Auth | **Supabase Auth** | Native JWT, RLS integration, no extra service |
| Database | **Supabase (Postgres)** | Events, candles, sessions — all in one place |
| Real-time | **Supabase Realtime** | Postgres CDC → frontend, replaces Socket.io |
| Routing | React Router v7 | Client-side SPA routing |
| Secrets | Azure Key Vault | No plaintext secrets in code |

---

## Storage & Caching

### Frontend

- Cache events by date range via React Query (`staleTime: 5 * 60 * 1000`)
- Restore replay session state from Supabase `replay_sessions` on load (replaces localStorage — survives device switches)
- Max 5MB in-memory (one week of 1m events per pair)

### Backend (Supabase Postgres)

- `trade_events` indexed on `(user_id, pair, timestamp)` — covers all primary query patterns
- `candles` indexed on `(pair, timeframe, time)` with a `UNIQUE` constraint to prevent duplicates on re-sync
- Retention policy: pg_cron job to hard-delete rows older than 6 months
- Write latency: Python backend inserts via `supabase-py` service role key — events land in DB within 50ms; Realtime fires to subscribed frontends within ~100ms

```sql
-- pg_cron retention job (register in Supabase Dashboard → Database → Cron Jobs)
select cron.schedule(
  'purge-old-events',
  '0 2 * * *',   -- 2am daily
  $$delete from trade_events where created_at < now() - interval '6 months'$$
);
```

---

## Security & Permissions

| Concern | Approach |
|---------|----------|
| Auth | Supabase Auth (JWT, email/password + OAuth) |
| Data isolation | RLS `auth.uid() = user_id` on every table |
| Service role | Python backend uses `SUPABASE_SERVICE_ROLE_KEY` (server-only, never sent to browser) |
| Anon key | Frontend uses `SUPABASE_ANON_KEY` — safe to expose; RLS enforces access |
| Secrets | All keys in env vars / Supabase Vault; never committed to source |

---

## Key UX Decisions

**Dark Theme (Default)** — traders monitor extended sessions; all colors designed for both modes.

**Information Density** — chart 70% of screen (desktop); controls below; event log in sidebar (desktop) / below chart (mobile). Tooltips for detail, no UI clutter.

**Real-time vs. Replay** — Supabase Realtime drives live mode; new events queue without interrupting an active scrub. Clear mode indicator in the header.

**Accessibility** — color + shape for patterns; high contrast on markers; keyboard shortcuts (Space = play/pause, ← → = scrub).

---

## Color Coding

| Element | Color | Meaning |
|---------|-------|---------|
| FVG | Amber | Fair value gap (imbalance) |
| OB | Blue | Order block (liquidity sweep zone) |
| MSS | Teal | Market structure shift (BoS) |
| Entry | Green | Long entry or bullish |
| Exit | Red | Short entry or bearish |
| Invalidated | Gray | Pattern broke before entry |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Chart render | < 16ms (60 FPS) |
| Scrubber drag | Smooth 60 FPS |
| Event log scroll | Virtualized (visible rows only) |
| Historical load | < 2s for one week of data |
| Live event latency | < 100ms (Supabase Realtime CDC) |

---

## Testing Strategy

- **Unit:** Pattern rendering logic, state transitions, Supabase query helpers
- **Integration:** Supabase insert → Realtime subscription fires → chart updates
- **E2E:** Full replay session (load → scrub → verify events match)
- **Performance:** 60 FPS scrubber drag with 1000+ events; Supabase query benchmarks on indexed columns

---

## Example: User Scrubs to Entry at 14:32 UTC

```
selectedTimeframe: "5m"
currentTime:       1620063120000  // 2024-05-04 14:32 UTC
```

**What renders:**

- Chart shows 5m candles from trade start up to 14:32 (fetched from `candles` table)
- FVG box drawn at 14:30 (high/low of candle 3 bars back, from `trade_events`)
- Green pin at 14:32 with label "LONG @ 1.0875"
- Event log:
  ```
  14:32 | ENTRY    | FVG + MSS @ 1.0875 | +52 pips
  14:31 | DETECTED | FVG (5m)
  14:30 | DETECTED | OB (1h confirmation)
  14:29 | DETECTED | MSS (15m)
  ```
- Context cascade: Dashed box overlaid showing "This 5m candle is inside THIS 1h candle [with OB zone]"
- User clicks "Why this entry?" → Tooltip: "5m FVG + MSS confluence, confirmed by 1h Order Block (ICT Scenario A)"

---

## What Is Built

The following features from the original design are now implemented:

- ✅ Live mode — Supabase Realtime streams trade events to the chart and event log in real time
- ✅ Replay mode — scrub any historical session candle-by-candle with a slider or keyboard shortcuts
- ✅ Pattern overlays — FVG boxes (amber), OB zones (blue), MSS lines (teal), BOS lines (purple) rendered on canvas
- ✅ Context Cascade — strip below the chart header showing the latest pattern on each parent timeframe (1m → 5m → 15m → 1h)
- ✅ Multi-page dashboard — Overview, Feed, Chart, Trades, Prop Firm, Settings
- ✅ Prop Firm Panel — daily drawdown tracker, consecutive-loss counter, profit-target progress, halt status
- ✅ Share audit link — immutable public snapshots via `/share/:uuid` served from `shared_sessions` table; no login required to view
- ✅ Onboarding wizard — step-by-step setup stored in `user_onboarding`, synced across devices
- ✅ Toast notification system
- ✅ Keyboard shortcuts (Space, ← →, Home/End, L, 1/5/F/H)
- ✅ Telegram notifications (signals, fills, rejections, drawdown halts, worker status)
- ✅ Multi-account orchestrator with automatic restarts
- ✅ Standalone backtest harness (`backend/backtest/ict_backtest.py`) with no Lumibot/MT5/Supabase deps

## Tasks Not Yet Accomplished

- 🔲 Billing / Stripe integration — `BillingTab` in `SettingsPage.tsx` is a stub; tier is toggled by a dev preview switch
- 🔲 Hide tier preview switcher from non-dev users (or gate on `NODE_ENV`)
- 🔲 Replace dead footer links (`Landing.tsx` About/Blog/Careers/Contact)
- 🔲 Change "30-day free trial" landing page copy to "Request Early Access" until billing ships
- 🔲 Replace placeholder social proof with real stats/testimonials before marketing outreach
- 🔲 Port `Term` glossary tooltips from landing page to dashboard (Live Feed, VerdictSidebar)
- 🔲 Wire "?" Documentation link in sidebar
- 🔲 Multi-pair comparison view
- 🔲 Paper trading / simulation mode
- 🔲 Mobile bottom-nav and responsive chart layout
- 🔲 Pattern strength heatmap (R:R histogram by pattern type)

---