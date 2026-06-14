import { useEffect, useState } from "react";

interface Props {
  onGoToReplay: () => void;
}

function getNextMarketOpen(): Date {
  // Forex opens Sunday 22:00 UTC (5 PM ET)
  const now = new Date();
  const day = now.getUTCDay(); // 0=Sun, 6=Sat
  const hour = now.getUTCHours();

  const next = new Date(now);
  next.setUTCMinutes(0, 0, 0);
  next.setUTCHours(22);

  if (day === 0 && hour < 22) {
    // Sunday before open — opens today at 22:00 UTC
    return next;
  }

  // Calculate days until next Sunday
  const daysUntilSunday = (7 - day) % 7 || 7;
  next.setUTCDate(now.getUTCDate() + daysUntilSunday);
  return next;
}

function formatCountdown(ms: number): string {
  if (ms <= 0) return "00:00:00";
  const totalSecs = Math.floor(ms / 1000);
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

export function MarketClosed({ onGoToReplay }: Props) {
  const [remaining, setRemaining] = useState(() => getNextMarketOpen().getTime() - Date.now());
  const [nextOpen] = useState(() => getNextMarketOpen());

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining(getNextMarketOpen().getTime() - Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const openLabel = nextOpen.toLocaleString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });

  return (
    <div
      className="flex flex-col items-center justify-center flex-1"
      style={{ background: "#0f1419", color: "#e5e7eb" }}
    >
      {/* Icon */}
      <div
        className="flex items-center justify-center rounded-full mb-6"
        style={{ width: 72, height: 72, background: "#1e2530" }}
      >
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="#374151" strokeWidth="1.5" />
          <path d="M12 6v6l4 2" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      {/* Heading */}
      <h2 className="font-mono text-[22px] font-semibold mb-1" style={{ color: "#f3f4f6" }}>
        Market is Closed
      </h2>
      <p className="font-mono text-[12px] mb-6" style={{ color: "#6b7280" }}>
        Forex markets are offline until
      </p>

      {/* Next open */}
      <div
        className="font-mono text-[13px] px-4 py-2 rounded mb-6"
        style={{ background: "#1e2530", color: "#9ca3af" }}
      >
        {openLabel}
      </div>

      {/* Countdown */}
      <div className="flex flex-col items-center mb-8">
        <span className="font-mono text-[11px] mb-2" style={{ color: "#4b5563" }}>
          OPENS IN
        </span>
        <span
          className="font-mono text-[40px] font-bold tracking-widest"
          style={{ color: "#34d399", letterSpacing: "0.12em" }}
        >
          {formatCountdown(remaining)}
        </span>
      </div>

      {/* CTA */}
      <button
        onClick={onGoToReplay}
        className="font-mono text-[13px] px-6 py-2.5 rounded transition-colors"
        style={{
          background: "#1e2530",
          color: "#38bdf8",
          border: "1px solid #253042",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "#253042")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "#1e2530")}
      >
        Review Previous Sessions →
      </button>
    </div>
  );
}
