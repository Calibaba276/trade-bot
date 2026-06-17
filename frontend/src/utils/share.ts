// Shareable Audit Link — a public, read-only audit trail served from Supabase.
//
// The B2B2C acquisition motion (design review §New Concepts 1) requires that a
// signal provider can open a follower's Glass Box results without an account.
// The trust mechanism only holds if the recipient cannot fabricate or tamper
// with the data: the snapshot is written once by the authenticated owner into
// `shared_sessions` and served read-only by uuid. The link is `/share/:uuid`.
//
// Legacy links embedded the base64 payload in the URL directly; decodeShare()
// still resolves those so old links don't 404, but new links always go through
// the server (createShare → buildShareUrl).

import { supabase } from "../lib/supaclient";
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

// --- server-side shares -----------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Persist a snapshot to Supabase and return its uuid. Throws on failure. */
export async function createShare(trades: Trade[], title = "Shared Audit"): Promise<string> {
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) throw new Error("You must be signed in to create a share link.");

  const payload: SharePayload = {
    v: VERSION,
    createdAt: Date.now(),
    title,
    trades: trades.map(toShareTrade),
  };

  const { data, error } = await supabase
    .from("shared_sessions")
    .insert({ user_id: auth.user.id, title, payload })
    .select("id")
    .single();

  if (error || !data) throw error ?? new Error("Failed to create share link.");
  return data.id as string;
}

/** Fetch a server-stored share by uuid. Null on missing / malformed. */
export async function fetchShare(
  id: string,
): Promise<{ payload: SharePayload; trades: Trade[] } | null> {
  const { data, error } = await supabase
    .from("shared_sessions")
    .select("payload")
    .eq("id", id)
    .maybeSingle();

  if (error || !data) return null;
  const payload = data.payload as SharePayload;
  if (!payload || payload.v !== VERSION || !Array.isArray(payload.trades)) return null;
  return { payload, trades: payload.trades.map(fromShareTrade) };
}

/** Resolve a /share/:token route param — server uuid first, legacy payload otherwise. */
export function resolveShare(
  token: string,
): Promise<{ payload: SharePayload; trades: Trade[] } | null> {
  if (UUID_RE.test(token)) return fetchShare(token);
  return Promise.resolve(decodeShare(token));
}

/** Create a server-stored share and return its absolute public URL. */
export async function buildShareUrl(trades: Trade[], title?: string): Promise<string> {
  const id = await createShare(trades, title);
  return `${window.location.origin}/share/${id}`;
}
