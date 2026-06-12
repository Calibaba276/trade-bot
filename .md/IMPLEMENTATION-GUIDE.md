# Glass Box Trading Engine — Step-by-Step Implementation Guide

## Project Overview

You and an agent will build a multi-timeframe trade replay system with deterministic pattern detection visualization. This guide breaks down the entire project into discrete, sequential phases with clear deliverables at each stage.

**Tech Stack:**
- Frontend: React 18 + TypeScript, Zustand, TradingView Lightweight Charts, Tailwind CSS
- Backend: Python (lumi_trade.py), Supabase (Postgres + Auth + Realtime + Edge Functions)
- Auth: Supabase Auth
- Real-time: Supabase Realtime
- Database: Supabase Postgres

---

## PHASE 0: Project Setup & Infrastructure (1–2 days)

### 0.1: Supabase Project Creation

**What to do:**
- Supabase has been setup - Login to my Supabase Project using the CLI
- Ensure to look at the available tables so as to work with what's available and only create another when it is not needed e.g. Don't make an accounts table if broker_accounts table already does the same work

**Deliverable:** Supabase project credentials document

### 0.2: Database Schema & RLS Setup

**What the agent will do:**
1. Ensure to look at the available tables so as to work with what's available and only create another when it is not needed e.g. Don't make an accounts table if broker_accounts table already does the same work
2. Run the SQL schema in Supabase Dashboard → SQL Editor:
   - Create `accounts`, `trade_events`, `candles`, `replay_sessions` tables
   - Create indexes on `(user_id, pair, timestamp)`, `(pair, timeframe, time)`, etc.
   - Create composite indexes for query performance
   - Only Create when one with the same use case does not exist already

3. Enable Row-Level Security (RLS) on all tables:
   - Create policies: `auth.uid() = user_id` for each table
   - Test that RLS blocks cross-user access

**You verify:** Log into Supabase Console, navigate to Database → Tables, confirm all tables exist with correct columns and indexes.

---

## PHASE 1: Frontend Scaffold & State Management

### 1.1: React + TypeScript Project Setup

**What the agent will do:**
```bash
npm create vite@latest glass-box -- --template react-ts
cd glass-box
npm i @supabase/supabase-js zustand @tanstack/react-query @tanstack/react-query-devtools lightweight-charts tailwindcss postcss autoprefixer

# Configure Tailwind
npx tailwindcss init -p
```

Create `.env.local`:
```
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
```

**Directory structure:**
```
src/
├── lib/
│   └── supabase.ts           # Supabase client init
├── hooks/
│   ├── useAuth.ts            # Auth context
│   └── useReplayStore.ts     # Zustand store
├── components/
│   ├── Auth/
│   │   ├── Login.tsx
│   │   └── SignUp.tsx
│   ├── Chart/
│   │   └── TradeReplayChart.tsx
│   ├── Controls/
│   │   ├── Scrubber.tsx
│   │   ├── PlaybackSpeed.tsx
│   │   └── TimeframeSelector.tsx
│   ├── EventLog/
│   │   └── EventLog.tsx
│   └── Layout.tsx
├── store/
│   └── replayStore.ts        # Zustand state
├── types/
│   └── index.ts              # TypeScript interfaces
├── pages/
│   ├── Login.tsx
│   ├── Replay.tsx
│   └── Home.tsx
└── App.tsx
```

**Deliverable:** Working Vite project with folder structure, Supabase client initialized, zero errors on `npm run dev`

### 1.2: Supabase Client & Auth Helpers

**What the agent will do:**

Create `src/lib/supaclient.ts`:
```typescript
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export const signIn = (email: string, password: string) =>
  supabase.auth.signInWithPassword({ email, password });

export const signUp = (email: string, password: string) =>
  supabase.auth.signUp({ email, password });

export const signOut = () => supabase.auth.signOut();

export const getSession = () => supabase.auth.getSession();

export const onAuthStateChange = (callback: (user: any) => void) =>
  supabase.auth.onAuthStateChange((_, session) => {
    callback(session?.user ?? null);
  });
```

Create `src/hooks/useAuth.ts`:
```typescript
import { useEffect, useState } from "react";
import { onAuthStateChange, getSession } from "../lib/supabase";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const unsubscribe = onAuthStateChange((user) => setUser(user));
    return unsubscribe;
  }, []);

  return { user, loading };
}
```

**Deliverable:** 
- `supabase.ts` and `useAuth.ts` files

### 1.3: Zustand State Management Store

**What the agent will do:**

Create `src/store/replayStore.ts`:
```typescript
import { create } from "zustand";
import { supabase } from "../lib/supabase";

interface TradeEvent {
  id: string;
  user_id: string;
  timestamp: number;
  timeframe: "1m" | "5m" | "15m" | "1h";
  type: "pattern_detected" | "entry" | "exit" | "invalidated";
  pattern?: string;
  price: number;
  metadata?: Record<string, any>;
}

interface ReplayStore {
  // UI State
  selectedTimeframe: "1m" | "5m" | "15m" | "1h";
  currentTime: number;
  isPlaying: boolean;
  playbackSpeed: 1 | 2 | 4;

  // Data
  events: TradeEvent[];
  priceData: Record<string, any[]>;

  // Actions
  setSelectedTimeframe: (tf: "1m" | "5m" | "15m" | "1h") => void;
  setCurrentTime: (time: number) => void;
  togglePlayback: () => void;
  setPlaybackSpeed: (speed: 1 | 2 | 4) => void;
  loadEventsForDateRange: (start: Date, end: Date, pair: string) => Promise<void>;
  addEvent: (event: TradeEvent) => void;
}

export const useReplayStore = create<ReplayStore>((set, get) => ({
  selectedTimeframe: "5m",
  currentTime: 0,
  isPlaying: false,
  playbackSpeed: 1,
  events: [],
  priceData: {},

  setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),
  setCurrentTime: (time) => set({ currentTime: time }),
  togglePlayback: () => set((s) => ({ isPlaying: !s.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),

  loadEventsForDateRange: async (start, end, pair) => {
    const { data: events, error: eventsError } = await supabase
      .from("trade_events")
      .select("*")
      .eq("pair", pair)
      .gte("timestamp", start.getTime())
      .lte("timestamp", end.getTime())
      .order("timestamp", { ascending: true });

    if (eventsError) throw eventsError;

    const { data: candles } = await supabase
      .from("candles")
      .select("*")
      .eq("pair", pair)
      .gte("time", start.getTime())
      .lte("time", end.getTime())
      .order("time", { ascending: true });

    const priceDataByTf = {
      "1m": candles?.filter((c) => c.timeframe === "1m") ?? [],
      "5m": candles?.filter((c) => c.timeframe === "5m") ?? [],
      "15m": candles?.filter((c) => c.timeframe === "15m") ?? [],
      "1h": candles?.filter((c) => c.timeframe === "1h") ?? [],
    };

    set({ events, priceData: priceDataByTf });
  },

  addEvent: (event) =>
    set((s) => ({ events: [...s.events, event].sort((a, b) => a.timestamp - b.timestamp) })),
}));
```

Create `src/types/index.ts`:
```typescript
export interface TradeEvent {
  id: string;
  user_id: string;
  account_id: string;
  timestamp: number;
  timeframe: "1m" | "5m" | "15m" | "1h";
  type: "pattern_detected" | "entry" | "exit" | "invalidated";
  pattern?: "FVG" | "OB" | "MSS" | "BOS";
  price: number;
  high: number;
  low: number;
  volume: number;
  ohlcv: { o: number; h: number; l: number; c: number; v: number };
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface Candle {
  id?: number;
  pair: string;
  timeframe: "1m" | "5m" | "15m" | "1h";
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ReplaySession {
  id: string;
  user_id: string;
  pair: string;
  start_time: number;
  end_time: number;
  current_time: number;
  playback_speed: 1 | 2 | 4;
  created_at: string;
}
```

**Deliverable:** 
- `replayStore.ts` with all actions
- `types/index.ts` with interfaces
- Test: Log Zustand state to console, confirm state mutations work

### 1.4: Auth Pages (Login & Sign Up)

**What the agent will do:**

Create `src/components/Auth/Login.tsx`:
```typescript
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { signIn } from "../../lib/supabase";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await signIn(email, password);
    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    navigate("/replay");
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900">
      <form onSubmit={handleSubmit} className="w-full max-w-md bg-gray-800 p-8 rounded-lg">
        <h1 className="text-3xl font-bold text-white mb-6">Glass Box Replay</h1>
        {error && <p className="text-red-500 mb-4">{error}</p>}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full mb-4 px-4 py-2 bg-gray-700 text-white rounded"
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full mb-6 px-4 py-2 bg-gray-700 text-white rounded"
          required
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded"
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>

        <p className="text-gray-400 mt-4">
          No account?{" "}
          <Link to="/signup" className="text-blue-400 hover:underline">
            Sign up
          </Link>
        </p>
      </form>
    </div>
  );
}
```

Create `src/components/Auth/SignUp.tsx` (similar pattern).

**Deliverable:** 
- Login and SignUp pages
- Test: Create an account via UI, confirm user appears in Supabase Auth dashboard

---

## PHASE 2: Chart Integration & Live Event Streaming (3–4 days)

### 2.1: TradingView Lightweight Charts Integration

**What the agent will do:**

Create `src/components/Chart/TradeReplayChart.tsx`:
```typescript
import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi } from "lightweight-charts";
import { useReplayStore } from "../../store/replayStore";

interface Props {
  pair: string;
}

export function TradeReplayChart({ pair }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi | null>(null);

  const { selectedTimeframe, currentTime, priceData } = useReplayStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize chart
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { color: "#1f2937", type: ColorType.Solid } },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      timeScale: { timeVisible: true },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Update candles when currentTime or timeframe changes
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    const candles = priceData[selectedTimeframe] || [];
    const visibleCandles = candles.filter((c) => c.time <= currentTime);

    candleSeriesRef.current.setData(
      visibleCandles.map((c) => ({
        time: Math.floor(c.time / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    if (visibleCandles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [currentTime, selectedTimeframe, priceData]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full h-[500px] bg-gray-900 rounded-lg border border-gray-700"
    />
  );
}
```

**Deliverable:** 
- Chart renders candles from `priceData`
- Chart updates as `currentTime` advances
- Test: Load 5m candles, verify they appear, manually change `selectedTimeframe` and confirm chart updates

### 2.2: Playback Controls (Scrubber, Play/Pause, Speed)

**What the agent will do:**

Create `src/components/Controls/Scrubber.tsx`:
```typescript
import { useReplayStore } from "../../store/replayStore";

interface Props {
  startTime: number;
  endTime: number;
}

export function Scrubber({ startTime, endTime }: Props) {
  const { currentTime, setCurrentTime, setIsPlaying } = useReplayStore();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentTime(parseInt(e.target.value));
    setIsPlaying(false); // Pause on manual scrub
  };

  const formatTime = (ms: number) => {
    const date = new Date(ms);
    return date.toLocaleTimeString();
  };

  return (
    <div className="flex items-center gap-4">
      <input
        type="range"
        min={startTime}
        max={endTime}
        value={currentTime}
        onChange={handleChange}
        className="flex-1 h-2 bg-gray-700 rounded cursor-pointer"
      />
      <span className="text-sm text-gray-400">{formatTime(currentTime)}</span>
    </div>
  );
}
```

Create `src/components/Controls/PlaybackSpeed.tsx`:
```typescript
import { useReplayStore } from "../../store/replayStore";

export function PlaybackSpeed() {
  const { playbackSpeed, setPlaybackSpeed } = useReplayStore();

  return (
    <select
      value={playbackSpeed}
      onChange={(e) => setPlaybackSpeed(parseInt(e.target.value) as 1 | 2 | 4)}
      className="px-3 py-1 bg-gray-700 text-white rounded"
    >
      <option value={1}>1x</option>
      <option value={2}>2x</option>
      <option value={4}>4x</option>
    </select>
  );
}
```

Create `src/components/Controls/PlayButton.tsx`:
```typescript
import { useReplayStore } from "../../store/replayStore";
import { useEffect } from "react";

export function PlayButton() {
  const { isPlaying, togglePlayback, currentTime, setCurrentTime, playbackSpeed, endTime } =
    useReplayStore();

  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentTime((prev) => Math.min(prev + 100 * playbackSpeed, endTime));
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, endTime, setCurrentTime]);

  return (
    <button
      onClick={togglePlayback}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold"
    >
      {isPlaying ? "⏸ Pause" : "▶ Play"}
    </button>
  );
}
```

**Deliverable:** 
- Scrubber slider (manual position control)
- Play/Pause button with auto-increment at playback speed
- Speed selector (1x, 2x, 4x)
- Test: Press play, verify `currentTime` increments; change speed, verify increment rate changes; drag scrubber, verify pause + position update

### 2.3: Event Log Component

**What the agent will do:**

Create `src/components/EventLog/EventLog.tsx`:
```typescript
import { useMemo } from "react";
import { useReplayStore } from "../../store/replayStore";

export function EventLog() {
  const { events, currentTime, selectedTimeframe } = useReplayStore();

  const visibleEvents = useMemo(
    () =>
      events
        .filter((e) => e.timeframe === selectedTimeframe && e.timestamp <= currentTime)
        .sort((a, b) => b.timestamp - a.timestamp),
    [events, currentTime, selectedTimeframe]
  );

  const formatTime = (ms: number) => new Date(ms).toLocaleTimeString();

  const patternColor = (pattern?: string) => {
    switch (pattern) {
      case "FVG":
        return "bg-amber-600";
      case "OB":
        return "bg-blue-600";
      case "MSS":
        return "bg-teal-600";
      default:
        return "bg-gray-600";
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 max-h-96 overflow-y-auto">
      <div className="sticky top-0 bg-gray-900 px-4 py-2 border-b border-gray-700">
        <h3 className="font-semibold text-white">Trade Events</h3>
      </div>
      <div className="divide-y divide-gray-700">
        {visibleEvents.length === 0 ? (
          <p className="p-4 text-gray-400 text-sm">No events for current timeframe</p>
        ) : (
          visibleEvents.map((event) => (
            <div key={event.id} className="p-3 hover:bg-gray-700 transition">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">{formatTime(event.timestamp)}</span>
                <span className={`px-2 py-1 rounded text-xs font-semibold text-white ${patternColor(event.pattern)}`}>
                  {event.pattern || event.type}
                </span>
              </div>
              <p className="text-sm text-white">{event.metadata?.entryReason || event.type}</p>
              {event.price && <p className="text-xs text-gray-400">@ {event.price.toFixed(4)}</p>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

**Deliverable:** 
- Event log renders events filtered by `currentTime` and `selectedTimeframe`
- Color-coded by pattern type
- Newest events first
- Test: Scrub to different times, verify event log updates; change timeframe, verify filter applies

### 2.4: Timeframe Selector

**What the agent will do:**

Create `src/components/Controls/TimeframeSelector.tsx`:
```typescript
import { useReplayStore } from "../../store/replayStore";

export function TimeframeSelector() {
  const { selectedTimeframe, setSelectedTimeframe } = useReplayStore();

  return (
    <select
      value={selectedTimeframe}
      onChange={(e) => setSelectedTimeframe(e.target.value as any)}
      className="px-3 py-2 bg-gray-700 text-white rounded font-semibold"
    >
      <option value="1m">1m</option>
      <option value="5m">5m</option>
      <option value="15m">15m</option>
      <option value="1h">1h</option>
    </select>
  );
}
```

**Deliverable:** 
- Dropdown selector for 1m, 5m, 15m, 1h
- Triggers `setSelectedTimeframe`, which updates chart and event log

### 2.5: Supabase Realtime for Live Event Streaming

**What the agent will do:**

Create a hook `src/hooks/useLiveTradeEvents.ts`:
```typescript
import { useEffect } from "react";
import { supabase } from "../lib/supabase";
import { useReplayStore } from "../store/replayStore";
import type { TradeEvent } from "../types";

export function useLiveTradeEvents(pair: string, isEnabled: boolean = true) {
  const { addEvent } = useReplayStore();

  useEffect(() => {
    if (!isEnabled) return;

    const channel = supabase
      .channel(`live-events-${pair}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "trade_events",
          filter: `pair=eq.${pair}`,
        },
        (payload) => {
          const event = payload.new as TradeEvent;
          addEvent(event);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [pair, isEnabled, addEvent]);
}
```

Integrate into replay page:
```typescript
import { useLiveTradeEvents } from "../hooks/useLiveTradeEvents";

export function ReplayPage() {
  // ... component logic
  useLiveTradeEvents(pair, isLiveMode);
  // ...
}
```

**Deliverable:** 
- Live event subscription works
- Test: Insert a row into `trade_events` table directly in Supabase Console, verify it appears in UI instantly

### 2.6: Layout & Main Replay Page

**What the agent will do:**

Create `src/pages/Replay.tsx`:
```typescript
import { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { useReplayStore } from "../store/replayStore";
import { TradeReplayChart } from "../components/Chart/TradeReplayChart";
import { Scrubber } from "../components/Controls/Scrubber";
import { PlayButton } from "../components/Controls/PlayButton";
import { PlaybackSpeed } from "../components/Controls/PlaybackSpeed";
import { TimeframeSelector } from "../components/Controls/TimeframeSelector";
import { EventLog } from "../components/EventLog/EventLog";
import { useLiveTradeEvents } from "../hooks/useLiveTradeEvents";

export function Replay() {
  const { user, loading: authLoading } = useAuth();
  const { loadEventsForDateRange } = useReplayStore();
  const [pair] = useState("EURUSD");
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    end: new Date(),
  });

  useLiveTradeEvents(pair);

  useEffect(() => {
    if (!user) return;
    loadEventsForDateRange(dateRange.start, dateRange.end, pair);
  }, [user, dateRange, pair, loadEventsForDateRange]);

  if (authLoading) return <div>Loading...</div>;
  if (!user) return <div>Not authenticated</div>;

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-6">Glass Box — Trade Replay</h1>

        {/* Chart */}
        <div className="mb-6">
          <TradeReplayChart pair={pair} />
        </div>

        {/* Controls */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
          <div className="flex gap-4 items-center mb-4">
            <PlayButton />
            <PlaybackSpeed />
            <TimeframeSelector />
          </div>
          <Scrubber startTime={dateRange.start.getTime()} endTime={dateRange.end.getTime()} />
        </div>

        {/* Event Log */}
        <EventLog />
      </div>
    </div>
  );
}
```

**Deliverable:** 
- Full replay interface with chart, controls, and event log
- All components wired together
- Test: Load a historical date range, navigate with scrubber, verify all pieces sync

---

## PHASE 3: Pattern Overlay Rendering (3–4 days)

### 3.1: Pattern Detection Overlay Logic

**What the agent will do:**

Create `src/utils/patternRenderer.ts`:
```typescript
import { ISeriesApi } from "lightweight-charts";
import type { TradeEvent } from "../types";

export interface PatternOverlay {
  id: string;
  type: "fvg" | "ob" | "mss" | "entry" | "exit";
  priceHigh: number;
  priceLow: number;
  timestamp: number;
  color: string;
}

export function getPatternOverlays(events: TradeEvent[]): PatternOverlay[] {
  return events.map((event) => ({
    id: event.id,
    type: event.pattern?.toLowerCase() || event.type,
    priceHigh: event.high,
    priceLow: event.low,
    timestamp: event.timestamp,
    color: getPatternColor(event.pattern),
  }));
}

function getPatternColor(pattern?: string): string {
  switch (pattern) {
    case "FVG":
      return "rgba(217, 119, 6, 0.2)"; // Amber
    case "OB":
      return "rgba(37, 99, 235, 0.2)"; // Blue
    case "MSS":
      return "rgba(20, 184, 166, 0.2)"; // Teal
    default:
      return "rgba(107, 114, 128, 0.2)"; // Gray
  }
}

export function renderPatternBox(
  chart: any,
  overlay: PatternOverlay
) {
  // Draw a rectangle/box on the chart between priceLow and priceHigh
  // This is a simplified version; full implementation depends on TradingView API
  console.log(`Rendering ${overlay.type} overlay from ${overlay.priceLow} to ${overlay.priceHigh}`);
}
```

### 3.2: Integrate Pattern Overlays into Chart

**What the agent will do:**

Update `src/components/Chart/TradeReplayChart.tsx`:
```typescript
import { getPatternOverlays } from "../../utils/patternRenderer";

export function TradeReplayChart({ pair }: Props) {
  // ... existing code ...

  useEffect(() => {
    if (!candleSeriesRef.current) return;

    const candles = priceData[selectedTimeframe] || [];
    const visibleCandles = candles.filter((c) => c.time <= currentTime);
    const visiblePatterns = getPatternOverlays(
      events.filter((e) => e.timeframe === selectedTimeframe && e.timestamp <= currentTime)
    );

    candleSeriesRef.current.setData(
      visibleCandles.map((c) => ({
        time: Math.floor(c.time / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Draw pattern overlays
    visiblePatterns.forEach((pattern) => {
      // TradingView Lightweight Charts uses `addCustomSeries` or shape rendering
      // For now, log patterns; full shape drawing requires canvas manipulation
      console.log("Pattern:", pattern);
    });

    if (visibleCandles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [currentTime, selectedTimeframe, priceData, events]);

  return <div ref={chartContainerRef} className="w-full h-[500px] ..." />;
}
```

**Note:** TradingView Lightweight Charts doesn't natively support arbitrary shape drawing. For production, you can:
- Use `addLineSeries()` for MSS lines
- Layer Canvas on top of chart for custom rectangles (FVG/OB boxes)
- Or switch to a more flexible charting library (Plotly, Chart.js)

**Deliverable:** 
- Pattern overlay function renders FVG, OB, MSS, Entry, Exit
- Test: Manually insert a FVG event into database, verify it renders as an overlay on chart

### 3.3: Color-Coded Markers for Entry/Exit

**What the agent will do:**

Create entry/exit markers (simplified approach using HTML labels on top of chart):
```typescript
export function EntryExitMarkers() {
  const { events, currentTime, selectedTimeframe } = useReplayStore();

  const visibleEntryExit = events.filter(
    (e) =>
      (e.type === "entry" || e.type === "exit") &&
      e.timeframe === selectedTimeframe &&
      e.timestamp <= currentTime
  );

  return (
    <div className="absolute inset-0 pointer-events-none">
      {visibleEntryExit.map((event) => (
        <div
          key={event.id}
          className={`absolute w-2 h-8 ${event.type === "entry" ? "bg-green-500" : "bg-red-500"} rounded-full`}
          style={{
            left: `${(event.timestamp / currentTime) * 100}%`,
            top: `${(event.price / 2) * 100}%`, // Simplified positioning
          }}
          title={`${event.type} @ ${event.price}`}
        />
      ))}
    </div>
  );
}
```

**Deliverable:** 
- Entry/exit markers render on chart
- Color-coded: green for entry, red for exit
- Tooltips on hover show price and reason

---

## PHASE 4: Advanced Features (2–3 days)

### 4.1: Context Cascade (Multi-Timeframe Confirmation)

**What the agent will do:**

Create `src/components/ContextCascade/ContextCascade.tsx`:
```typescript
import { useReplayStore } from "../../store/replayStore";

interface Props {
  eventId: string;
}

export function ContextCascade({ eventId }: Props) {
  const { events } = useReplayStore();
  const event = events.find((e) => e.id === eventId);

  if (!event || event.type !== "entry") return null;

  const parentPattern = event.metadata?.parentTimeframeConfirm;
  if (!parentPattern) return null;

  const parentEvent = events.find(
    (e) =>
      e.timestamp <= event.timestamp &&
      e.pattern === parentPattern &&
      timeframeValue(e.timeframe) > timeframeValue(event.timeframe)
  );

  if (!parentEvent) return null;

  return (
    <div className="bg-blue-900 border border-blue-700 rounded p-3 mt-2">
      <p className="text-sm text-white">
        Entry triggered on <strong>{event.timeframe}</strong>
      </p>
      <p className="text-sm text-blue-300 mt-1">
        ✓ Confirmed by <strong>{parentEvent.pattern}</strong> on{" "}
        <strong>{parentEvent.timeframe}</strong>
      </p>
    </div>
  );
}

function timeframeValue(tf: string): number {
  const values: Record<string, number> = { "1m": 1, "5m": 5, "15m": 15, "1h": 60 };
  return values[tf] || 0;
}
```

**Deliverable:** 
- Context cascade shows parent timeframe confirmation
- Test: Create entry event with `parentTimeframeConfirm` metadata, verify cascade displays

### 4.2: Replay Session Persistence

**What the agent will do:**

Create a hook `src/hooks/useReplaySessionPersistence.ts`:
```typescript
import { useEffect } from "react";
import { useReplayStore } from "../store/replayStore";
import { supabase } from "../lib/supabase";

export function useReplaySessionPersistence(sessionId: string) {
  const { currentTime, playbackSpeed, selectedTimeframe } = useReplayStore();

  useEffect(() => {
    const saveSession = async () => {
      await supabase
        .from("replay_sessions")
        .upsert(
          {
            id: sessionId,
            current_time: currentTime,
            playback_speed: playbackSpeed,
            updated_at: new Date().toISOString(),
          },
          { onConflict: "id" }
        )
        .select();
    };

    const timer = setTimeout(saveSession, 1000); // Debounce saves
    return () => clearTimeout(timer);
  }, [currentTime, playbackSpeed, sessionId]);
}
```

**Deliverable:** 
- Replay session state (scrub position, speed) persisted to Supabase
- Test: Start a replay, move scrubber, refresh page, verify position restores

### 4.3: Statistics & Win Rate (Edge Function)

**What the agent will do:**

Create Supabase Edge Function `supabase/functions/trade-stats/index.ts`:
```typescript
import { serve } from "https://deno.land/std/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js";

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  const { pair } = await req.json();

  const { data: events } = await supabase
    .from("trade_events")
    .select("pattern, type, metadata")
    .eq("pair", pair);

  const stats = {
    totalTrades: events?.filter((e) => e.type === "entry").length || 0,
    wins: events?.filter((e) => e.type === "exit" && e.metadata?.pnl > 0).length || 0,
    losses: events?.filter((e) => e.type === "exit" && e.metadata?.pnl < 0).length || 0,
  };

  stats.winRate = stats.totalTrades > 0 ? (stats.wins / stats.totalTrades) * 100 : 0;

  return new Response(JSON.stringify(stats), {
    headers: { "Content-Type": "application/json" },
  });
});
```

**Deliverable:** 
- Edge Function computes win rate, total trades, wins/losses
- Frontend calls function and displays stats

---

## PHASE 5: Python Backend Integration (2–3 days)

### 5.1: Update Python Backend (lumi_trade.py)

**What you need to do:**

1. Install Supabase Python SDK:
   ```bash
   pip install supabase python-dotenv
   ```

2. Update your `lumi_trade.py` to emit trade events to Supabase:
   ```python
   from supabase import create_client
   import os
   from dotenv import load_dotenv

   load_dotenv()

   SUPABASE_URL = os.getenv("SUPABASE_URL")
   SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

   supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

   def emit_trade_event(event_data: dict):
       """Emit a trade event to Supabase"""
       try:
           response = supabase.table("trade_events").insert(event_data).execute()
           print(f"Event inserted: {response.data}")
       except Exception as e:
           print(f"Error inserting event: {e}")

   # Example usage in your trading logic:
   # event = {
   #     "user_id": "uuid",
   #     "account_id": "uuid",
   #     "pair": "EURUSD",
   #     "timestamp": int(time.time() * 1000),
   #     "timeframe": "5m",
   #     "type": "pattern_detected",
   #     "pattern": "FVG",
   #     "price": 1.0875,
   #     "high": 1.0880,
   #     "low": 1.0870,
   #     "volume": 100,
   #     "ohlcv": {...},
   #     "confidence": 0.85,
   #     "metadata": {"entryReason": "..."}
   # }
   # emit_trade_event(event)
   ```

3. Also insert candles:
   ```python
   def insert_candle(pair: str, timeframe: str, candle_data: dict):
       """Insert a candle into Supabase"""
       event = {
           "pair": pair,
           "timeframe": timeframe,
           "time": candle_data["time"],
           "open": candle_data["open"],
           "high": candle_data["high"],
           "low": candle_data["low"],
           "close": candle_data["close"],
           "volume": candle_data["volume"],
       }
       supabase.table("candles").upsert(event).execute()
   ```

**Deliverable:** 
- Python backend writes events/candles to Supabase
- Test: Run your bot on a paper account, verify events appear in Supabase Console → `trade_events` table in real-time

### 5.2: Test Data Population

**What you or the agent will do:**

Load historical trade data into Supabase for testing:
```bash
# Option A: CSV import via Supabase Dashboard
# Go to Tables → trade_events → Import data, upload CSV

# Option B: Python script to backfill
python scripts/backfill_trades.py \
  --pair EURUSD \
  --start-date 2024-05-01 \
  --end-date 2024-05-13 \
  --supabase-url $SUPABASE_URL \
  --api-key $SUPABASE_SERVICE_ROLE_KEY
```

**Deliverable:** 
- Historical data (1 week of events) in `trade_events` and `candles` tables
- Verify in Supabase Console that data is present and has proper timestamps

---

## PHASE 6: Testing & Deployment (2–3 days)

### 6.1: Unit & Integration Tests

**What the agent will do:**

Create test file `src/tests/replayStore.test.ts`:
```typescript
import { useReplayStore } from "../store/replayStore";
import { renderHook, act } from "@testing-library/react";

describe("useReplayStore", () => {
  it("should set current time", () => {
    const { result } = renderHook(() => useReplayStore());
    act(() => {
      result.current.setCurrentTime(1000);
    });
    expect(result.current.currentTime).toBe(1000);
  });

  it("should toggle playback", () => {
    const { result } = renderHook(() => useReplayStore());
    expect(result.current.isPlaying).toBe(false);
    act(() => {
      result.current.togglePlayback();
    });
    expect(result.current.isPlaying).toBe(true);
  });

  it("should add events in order", () => {
    const { result } = renderHook(() => useReplayStore());
    act(() => {
      result.current.addEvent({
        id: "1",
        timestamp: 1000,
        // ... rest of event
      });
      result.current.addEvent({
        id: "2",
        timestamp: 500,
        // ... rest of event
      });
    });
    expect(result.current.events[0].timestamp).toBe(500);
  });
});
```

Install testing dependencies:
```bash
npm i -D vitest @testing-library/react @testing-library/user-event jsdom
```

**Deliverable:** 
- Unit tests for Zustand store
- Run tests: `npm run test`

### 6.2: E2E Tests (Cypress or Playwright)

**What the agent will do:**

Create E2E test `e2e/replay.spec.ts`:
```typescript
import { test, expect } from "@playwright/test";

test("full replay workflow", async ({ page }) => {
  // Navigate to app
  await page.goto("http://localhost:5173");

  // Login
  await page.fill('input[type="email"]', "test@example.com");
  await page.fill('input[type="password"]', "password");
  await page.click("button:has-text('Sign In')");

  // Wait for chart to load
  await page.waitForSelector(".lightweight-charts-container");

  // Verify scrubber exists
  const scrubber = page.locator('input[type="range"]');
  expect(await scrubber.count()).toBeGreaterThan(0);

  // Click play
  await page.click("button:has-text('Play')");

  // Wait a second for currentTime to increment
  await page.waitForTimeout(1000);

  // Verify play button changed to pause
  expect(await page.locator("button:has-text('Pause')").count()).toBeGreaterThan(0);

  // Click timeframe selector
  await page.selectOption("select", "1h");

  // Verify event log updated
  const eventLog = page.locator(".event-log");
  expect(await eventLog.isVisible()).toBeTruthy();
});
```

**Deliverable:** 
- E2E test covers: login → load data → play → scrub → change timeframe
- Run tests: `npm run test:e2e`

### 6.3: Performance Optimization

**What the agent will do:**

1. **Memoize components:**
   ```typescript
   export const EventLog = React.memo(function EventLog() {
     // ... component
   });
   ```

2. **Virtualize event log:**
   ```typescript
   import { FixedSizeList } from "react-window";

   export function EventLogVirtualized() {
     return (
       <FixedSizeList
         height={400}
         itemCount={events.length}
         itemSize={60}
         width="100%"
       >
         {EventLogRow}
       </FixedSizeList>
     );
   }
   ```

3. **Lazy load chart:**
   ```typescript
   const TradeReplayChart = React.lazy(() =>
     import("../components/Chart/TradeReplayChart")
   );
   ```

**Deliverable:** 
- Performance metrics: chart render < 16ms, scrubber drag 60 FPS
- Test with React DevTools Profiler

### 6.4: Build & Deploy

**What the agent will do:**

```bash
# Build for production
npm run build

# Preview production build locally
npm run preview

```

Set environment variables on hosting platform:
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=...
```

**Deliverable:** 
- Deployed app accessible at public URL
- Test full workflow on deployed version

---

## PHASE 7: Polish & Documentation (1–2 days)

### 7.1: UI/UX Polish

**What the agent will do:**

1. Dark mode refinement (all colors validated in dark theme)
2. Responsive layout for mobile (test on phone/tablet)
3. Keyboard shortcuts:
   - `Space`: Play/Pause
   - `←` / `→`: Scrub backward/forward
   - `+` / `-`: Increase/decrease speed
4. Tooltips on all controls
5. Loading states and error handling

**Deliverable:** 
- Responsive design on mobile, tablet, desktop
- Keyboard shortcuts functional
- Graceful error messages

### 7.2: Documentation

**What the agent will do:**

Create `README.md`:
- Project overview
- Setup instructions
- Architecture diagram
- Environment variables
- Running locally
- Deployment guide
- Troubleshooting

Create `CONTRIBUTING.md`:
- Code style guide
- Testing requirements
- PR checklist

**Deliverable:** 
- Comprehensive README
- Developer guide

### 7.3: Final Testing & QA

**What you will do:**

1. Test full workflow on staging
2. Verify all data flows correctly
3. Test with real trade data from your bot
4. Performance testing on low-bandwidth connection
5. Cross-browser testing (Chrome, Firefox, Safari, Edge)

**Deliverable:** 
- QA checklist completed
- No critical bugs

---

## Summary: Checkpoint Checklist

Print this out and check off as you go:

### Phase 0: Setup
- [] Login to Supabase using the cli
- [ ] Database schema deployed
- [ ] RLS policies enabled

### Phase 1: Frontend
- [ ] React project initialized
- [ ] Zustand store working
- [ ] Auth pages (Login/SignUp) functional
- [ ] Supabase client integrated

### Phase 2: Chart & Controls
- [ ] Chart renders candles
- [ ] Scrubber works (drag + hover)
- [ ] Play/Pause button works
- [ ] Speed selector functional
- [ ] Timeframe selector updates chart
- [ ] Event log displays and filters correctly
- [ ] Realtime event subscription works

### Phase 3: Pattern Overlays
- [ ] Pattern color coding applied
- [ ] FVG/OB/MSS/Entry/Exit overlays render
- [ ] Pattern tooltips display

### Phase 4: Advanced
- [ ] Context cascade shows parent TF confirmation
- [ ] Replay session persists across refresh
- [ ] Statistics Edge Function computes win rate

### Phase 5: Backend
- [ ] Python backend emits events to Supabase
- [ ] Candles inserted correctly
- [ ] Historical data backfilled

### Phase 6: Testing
- [ ] Unit tests pass
- [ ] E2E tests pass
- [ ] Performance targets met (< 16ms chart, 60 FPS scrubber)
- [ ] Built & deployed successfully

### Phase 7: Polish
- [ ] Mobile responsive
- [ ] Keyboard shortcuts work
- [ ] Dark mode validated
- [ ] Documentation complete
- [ ] QA passed

---

## Communication Protocol with Agent

### For Each Phase:

**You say:**
> Agent, let's start Phase 2.1: TradingView Chart Integration.
> Here's what we need to build...
> When you're done, show me the code and let's test it together.

**Agent responds:**
> I've created the TradeReplayChart component. Here's the code...
> To test: Run `npm run dev` and navigate to the replay page.
> You should see a chart with candlesticks.

**You test & verify:**
> ✅ Chart loads and shows candles.
> Next, let's add the scrubber control.

### For Debugging:

**You say:**
> The chart isn't updating when I change the timeframe.
> Here's what I see:
> - Timeframe selector changes the state
> - But chart shows old candles

**Agent responds:**
> I see the issue. The `useEffect` isn't re-running when `selectedTimeframe` changes.
> Here's the fix: [code diff showing old vs new]
> Test this and let me know if it works.

---

## Final Notes

- **Start small**: Don't skip Phase 0. Supabase setup is the foundation.
- **Test as you go**: Don't wait until the end to test. Each phase should be working.
- **Keep it iterative**: If something isn't working, pause and debug together rather than pushing forward.
- **Document as you build**: Add comments and docstrings so you both understand the code later.

**Good luck!** 🚀
