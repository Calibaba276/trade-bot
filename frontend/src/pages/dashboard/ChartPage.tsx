import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";
import { useReplaySession } from "../../hooks/useReplaySession";
import { MarketsPanel } from "../../components/Layout/MarketsPanel";
import { ChartArea } from "../../components/Chart/ChartArea";
import { PlaybackControls } from "../../components/Controls/PlaybackControls";
import { RightPanel } from "../../components/Layout/RightPanel";
import { TradesTable } from "../../components/Layout/TradesTable";

/**
 * Visual Debugger / Trade Replay (design guide §6.5).
 * Reuses the existing chart + replay engine; data is loaded by DashboardLayout.
 */
export function ChartPage() {
  useReplaySession();
  useKeyboardShortcuts({ isLive: false, onToggleLive: () => {} });

  return (
    <div className="h-full flex min-h-0">
      <MarketsPanel />
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex flex-1 min-h-0">
          <div className="flex flex-col flex-1 min-w-0">
            <ChartArea />
            <PlaybackControls />
          </div>
        </div>
        <TradesTable />
      </div>
      <RightPanel />
    </div>
  );
}
