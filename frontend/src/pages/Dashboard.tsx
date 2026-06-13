import { useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { useReplayStore } from "../store/replayStore";
import { Topbar } from "../components/Layout/Topbar";
import { MarketsPanel } from "../components/Layout/MarketsPanel";
import { ChartArea } from "../components/Chart/ChartArea";
import { PlaybackControls } from "../components/Controls/PlaybackControls";
import { RightPanel } from "../components/Layout/RightPanel";
import { TradesTable } from "../components/Layout/TradesTable";

export function Dashboard() {
  const { user } = useAuth();
  const { selectedPair, dateRange, loadEventsForDateRange } = useReplayStore();

  // Load events whenever pair or date range changes
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
      <Topbar userName={userName} />

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left — markets panel */}
        <MarketsPanel />

        {/* Centre — chart + playback + trades */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Chart section */}
          <div className="flex flex-1 min-h-0">
            <div className="flex flex-col flex-1 min-w-0">
              <ChartArea />
              <PlaybackControls />
            </div>
          </div>

          {/* Trades table */}
          <TradesTable />
        </div>

        {/* Right — event log + prop firm rules + performance */}
        <RightPanel />
      </div>
    </div>
  );
}
