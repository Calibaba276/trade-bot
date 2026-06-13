import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { TradeEvent } from "../types";

function tfToMs(tf: string): number {
  const map: Record<string, number> = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
  };
  return map[tf] ?? 300_000;
}

export function renderPatterns(
  canvas: HTMLCanvasElement,
  chart: IChartApi,
  series: ISeriesApi<"Candlestick">,
  events: TradeEvent[],
  currentTime: number,
  selectedTimeframe: string,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const visible = events.filter(
    (e) => e.timeframe === selectedTimeframe && e.timestamp <= currentTime,
  );
  if (!visible.length) return;

  ctx.save();
  ctx.scale(dpr, dpr);

  const timeScale = chart.timeScale();
  const tfMs = tfToMs(selectedTimeframe);

  for (const event of visible) {
    const x1 = timeScale.timeToCoordinate(Math.floor(event.timestamp / 1000) as Time);
    if (x1 === null) continue;

    // ── FVG / OB zone rectangles ────────────────────────────────────────────
    if (event.pattern === "FVG" || event.pattern === "OB") {
      const endMs = Math.min(event.timestamp + tfMs * 20, currentTime);
      const x2 =
        timeScale.timeToCoordinate(Math.floor(endMs / 1000) as Time) ?? x1 + 60;
      const yHigh = series.priceToCoordinate(event.high);
      const yLow = series.priceToCoordinate(event.low);
      if (yHigh === null || yLow === null) continue;

      const isFVG = event.pattern === "FVG";
      ctx.fillStyle = isFVG ? "rgba(251,191,36,0.12)" : "rgba(56,189,248,0.10)";
      ctx.strokeStyle = isFVG ? "rgba(251,191,36,0.5)" : "rgba(56,189,248,0.5)";
      ctx.lineWidth = 0.5;

      const rx = Math.min(x1, x2);
      const ry = Math.min(yHigh, yLow);
      const rw = Math.abs(x2 - x1);
      const rh = Math.abs(yLow - yHigh);

      ctx.beginPath();
      ctx.rect(rx, ry, rw, rh);
      ctx.fill();
      ctx.stroke();

      // Label (top-left of box)
      ctx.fillStyle = isFVG ? "rgba(251,191,36,0.85)" : "rgba(56,189,248,0.85)";
      ctx.font = "8px monospace";
      ctx.fillText(event.pattern, rx + 3, ry + 9);
    }

    // ── MSS / BOS dashed horizontal lines ───────────────────────────────────
    if (event.pattern === "MSS" || event.pattern === "BOS") {
      const y = series.priceToCoordinate(event.price);
      if (y === null) continue;

      const extendMs = Math.min(event.timestamp + tfMs * 30, currentTime);
      const x2 =
        timeScale.timeToCoordinate(Math.floor(extendMs / 1000) as Time) ?? x1 + 120;

      const isMSS = event.pattern === "MSS";
      ctx.strokeStyle = isMSS ? "rgba(20,184,166,0.85)" : "rgba(139,92,246,0.85)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = isMSS ? "rgba(20,184,166,0.9)" : "rgba(139,92,246,0.9)";
      ctx.font = "8px monospace";
      ctx.fillText(event.pattern, x1 + 4, y - 3);
    }

    // ── Entry / Exit triangle pins ───────────────────────────────────────────
    if (event.type === "entry" || event.type === "exit") {
      const y = series.priceToCoordinate(event.price);
      if (y === null) continue;

      const isEntry = event.type === "entry";
      ctx.fillStyle = isEntry ? "#34d399" : "#f87171";

      const sz = 6;
      ctx.beginPath();
      if (isEntry) {
        // downward triangle
        ctx.moveTo(x1, y + sz);
        ctx.lineTo(x1 - sz * 0.6, y);
        ctx.lineTo(x1 + sz * 0.6, y);
      } else {
        // upward triangle
        ctx.moveTo(x1, y - sz);
        ctx.lineTo(x1 - sz * 0.6, y);
        ctx.lineTo(x1 + sz * 0.6, y);
      }
      ctx.closePath();
      ctx.fill();
    }
  }

  ctx.restore();
}
