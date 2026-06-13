import { useEffect } from "react";
import { useReplayStore } from "../store/replayStore";

const TF_MS: Record<string, number> = {
  "1m": 60_000,
  "5m": 300_000,
  "15m": 900_000,
  "1h": 3_600_000,
};

interface Options {
  isLive: boolean;
  onToggleLive: () => void;
}

/**
 * Global keyboard shortcuts for the dashboard.
 *
 * Space          — Play / Pause (replay mode only)
 * ← / →          — Step back / forward one candle
 * Home           — Jump to start of date range
 * End            — Jump to end of date range
 * L              — Toggle Live / Replay mode
 * 1 / 5 / F / H  — Switch to 1m / 5m / 15m / 1h timeframe
 *
 * All shortcuts are suppressed when focus is inside a text input.
 */
export function useKeyboardShortcuts({ isLive, onToggleLive }: Options) {
  const {
    togglePlayback,
    setCurrentTime,
    setSelectedTimeframe,
    currentTime,
    dateRange,
    selectedTimeframe,
  } = useReplayStore();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

      const step = TF_MS[selectedTimeframe] ?? 60_000;
      const startMs = dateRange.start.getTime();
      const endMs = dateRange.end.getTime();

      switch (e.key) {
        case " ":
          e.preventDefault();
          if (!isLive) togglePlayback();
          break;

        case "ArrowLeft":
          e.preventDefault();
          if (!isLive) setCurrentTime(Math.max(currentTime - step, startMs));
          break;

        case "ArrowRight":
          e.preventDefault();
          if (!isLive) setCurrentTime(Math.min(currentTime + step, endMs));
          break;

        case "Home":
          e.preventDefault();
          if (!isLive) { setCurrentTime(startMs); }
          break;

        case "End":
          e.preventDefault();
          if (!isLive) { setCurrentTime(endMs); }
          break;

        case "l":
        case "L":
          onToggleLive();
          break;

        case "1":
          setSelectedTimeframe("1m");
          break;
        case "5":
          setSelectedTimeframe("5m");
          break;
        case "f":
        case "F":
          setSelectedTimeframe("15m");
          break;
        case "h":
        case "H":
          if (!isLive) setSelectedTimeframe("1h");
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    isLive,
    onToggleLive,
    togglePlayback,
    setCurrentTime,
    setSelectedTimeframe,
    currentTime,
    dateRange,
    selectedTimeframe,
  ]);
}
