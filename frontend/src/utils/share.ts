// Shareable Audit Link — encodes a trade snapshot into a public, read-only URL.
//
// The B2B2C acquisition motion (design review §New Concepts 1) requires that a
// signal provider can open a follower's Glass Box results without an account.
// Until billing + signed share rows exist server-side, we encode the snapshot
// directly into the URL: purely client-side, no auth, no RLS. The /share route
// decodes it and renders a read-only audit view.

import type { Trade } from "../hooks/useTrades";
import type { TradeEvent } from "../types";

const VERSION = 1;

/** Compact, serializable form of a Trade (drops chart/candle data we don't render). */
interface ShareTrade {
  id: string;
  signalId?: string;
  time: number;
  pair: string;
  direction: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp: number;
  lots: number;
  rr: number;
  pnl: number | null;
  status: "OPEN" | "WIN" | "LOSS";
  setup: string;
  meta: Record<string, unknown>;
}

export interface SharePayload {
  v: number;
  createdAt: number;
  title: string;
  trades: ShareTrade[];
}

// --- base64url helpers (unicode-safe) ---------------------------------------

function b64urlEncode(s: string): string {
  return btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function b64urlDecode(s: string): string {
  const padded = s.replace(/-/g, "+").replace(/_/g, "/");
  return decodeURIComponent(escape(atob(padded)));
}

// --- (de)serialization ------------------------------------------------------

function toShareTrade(t: Trade): ShareTrade {
  return {
    id: t.id,
    signalId: t.signalId,
    time: t.time,
    pair: t.pair,
    direction: t.direction,
    entry: t.entry,
    sl: t.sl,
    tp: t.tp,
    lots: t.lots,
    rr: t.rr,
    pnl: t.pnl,
    status: t.status,
    setup: t.setup,
    meta: t.entryEvent?.metadata ?? {},
  };
}

/** Rebuild a Trade with the minimal entryEvent the table + VerdictSidebar read. */
function fromShareTrade(s: ShareTrade): Trade {
  const entryEvent = {
    id: s.id,
    user_id: "",
    account_id: "",
    signal_id: s.signalId,
    pair: s.pair,
    timestamp: s.time,
    timeframe: "5m",
    type: "entry",
    price: s.entry,
    high: s.entry,
    low: s.entry,
    volume: 0,
    metadata: s.meta,
  } as TradeEvent;

  return {
    id: s.id,
    signalId: s.signalId,
    time: s.time,
    pair: s.pair,
    direction: s.direction,
    entry: s.entry,
    sl: s.sl,
    tp: s.tp,
    lots: s.lots,
    rr: s.rr,
    pnl: s.pnl,
    status: s.status,
    setup: s.setup,
    entryEvent,
  };
}

/** Encode a list of trades into a URL-safe payload string. */
export function encodeShare(trades: Trade[], title = "Shared Audit"): string {
  const payload: SharePayload = {
    v: VERSION,
    createdAt: Date.now(),
    title,
    trades: trades.map(toShareTrade),
  };
  return b64urlEncode(JSON.stringify(payload));
}

/** Decode a payload string back into a payload + reconstructed trades. Null on failure. */
export function decodeShare(encoded: string): { payload: SharePayload; trades: Trade[] } | null {
  try {
    const payload = JSON.parse(b64urlDecode(encoded)) as SharePayload;
    if (!payload || payload.v !== VERSION || !Array.isArray(payload.trades)) return null;
    return { payload, trades: payload.trades.map(fromShareTrade) };
  } catch {
    return null;
  }
}

/** Build the absolute public share URL for the given trades. */
export function buildShareUrl(trades: Trade[], title?: string): string {
  return `${window.location.origin}/share/${encodeShare(trades, title)}`;
}
