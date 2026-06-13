export interface TradeEvent {
  id: string;
  user_id: string;
  account_id: string;
  signal_id?: string;
  pair: string;
  timestamp: number;                          // ms UTC
  timeframe: "1m" | "5m" | "15m" | "1h";
  type: "pattern_detected" | "entry" | "exit" | "invalidated";
  pattern?: "FVG" | "OB" | "MSS" | "BOS";
  price: number;
  high: number;
  low: number;
  volume: number;
  ohlcv?: { o: number; h: number; l: number; c: number; v: number };
  confidence?: number;
  metadata?: {
    parentTimeframeConfirm?: string;
    entryReason?: string;
    pnl?: number;
    [key: string]: unknown;
  };
  created_at?: string;
}

export interface Candle {
  id?: number;
  user_id?: string;
  pair: string;
  timeframe: "1m" | "5m" | "15m" | "1h";
  time: number;                               // ms UTC, candle open time
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ReplaySession {
  id: string;
  user_id: string;
  trade_id?: string;
  pair: string;
  start_time: number;
  end_time: number;
  current_time: number;
  playback_speed: 1 | 2 | 4;
  selected_timeframe: "1m" | "5m" | "15m" | "1h";
  created_at?: string;
  updated_at?: string;
}

export interface BrokerAccount {
  id: string;
  user_id?: string;
  label?: string;
  created_at?: string;
}
