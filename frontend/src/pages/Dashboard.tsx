import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { useReplayStore } from "../store/replayStore";
import { useLiveTradeEvents } from "../hooks/useLiveTradeEvents";
import { useReplaySession } from "../hooks/useReplaySession";
import { Topbar } from "../components/Layout/Topbar";
import { MarketsPanel } from "../components/Layout/MarketsPanel";
import { ChartArea } from "../components/Chart/ChartArea";
import { PlaybackControls } from "../components/Controls/PlaybackControls";
import { RightPanel } from "../components/Layout/RightPanel";
import { TradesTable } from "../components/Layout/TradesTable";

export function Dashboard() {
  const { user } = useAuth();
  const { selectedPair, dateRange, loadEventsForDateRange, setCurrentTime } =
    useReplayStore();

  // Live mode: Realtime events stream in and currentTime tracks now.
  // Replay mode: scrubber controls currentTime over historical data.
  const [isLive, setIsLive] = useState(false);

  // Subscribe to live trade_events for the selected pair (only in live mode)
  useLiveTradeEvents(selectedPair, isLive);

  // Persist and restore scrub position across sessions
  useReplaySession();

  // In live mode, keep currentTime at now so new events are immediately visible
  useEffect(() => {
    if (!isLive) return;
    setCurrentTime(Date.now());
    const id = setInterval(() => setCurrentTime(Date.now()), 5000);
    return () => clearInterval(id);
  }, [isLive, setCurrentTime]);

  // Load historical events whenever pair or date range changes
  useEffect(() => {
    if (!user) return;
    loadEventsForDateRange(dateRange.start, dateRange.end, selectedPair).catch(
      (err) => console.error("[Dashboard] loadEvents:", err)
    );
  }, [user, selectedPair, dateRange, loadEventsForDateRange]);

  const userName = user?.email?.split("@")[0] ?? "Trader";

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{ height: "100vh", background: "#0f1419", color: "#e5e7eb" }}
    >
      {/* Top bar */}
      <Topbar userName={userName} isLive={isLive} onToggleLive={() => setIsLive((v) => !v)} />

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left — markets panel */}
        <MarketsPanel />

        {/* Centre — chart + playback + trades */}
        <div className="flex flex-col flex-1 min-w-0">
          <div className="flex flex-1 min-h-0">
            <div className="flex flex-col flex-1 min-w-0">
              <ChartArea />
              {/* Playback controls disabled in live mode */}
              {!isLive && <PlaybackControls />}
            </div>
          </div>
          <TradesTable />
        </div>

        {/* Right — event log + prop firm rules + performance */}
        <RightPanel />
      </div>
    </div>
  );
}
