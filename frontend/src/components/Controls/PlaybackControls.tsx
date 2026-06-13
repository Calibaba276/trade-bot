import { useEffect } from "react";
import { useReplayStore } from "../../store/replayStore";

export function PlaybackControls() {
  const {
    isPlaying,
    togglePlayback,
    currentTime,
    setCurrentTime,
    setIsPlaying,
    playbackSpeed,
    setPlaybackSpeed,
    dateRange,
  } = useReplayStore();

  const startMs = dateRange.start.getTime();
  const endMs = dateRange.end.getTime();

  // Play loop — advance currentTime at playbackSpeed × 60s steps per 100ms tick
  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      setCurrentTime(Math.min(currentTime + 60_000 * playbackSpeed, endMs));
      if (currentTime >= endMs) setIsPlaying(false);
    }, 100);
    return () => clearInterval(id);
  }, [isPlaying, currentTime, playbackSpeed, endMs, setCurrentTime, setIsPlaying]);

  const fmtTime = (ms: number) =>
    new Date(ms).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Africa/Lagos",
    });

  return (
    <div
      className="flex items-center gap-2 px-2.5 flex-shrink-0"
      style={{
        height: "36px",
        borderTop: "0.5px solid #1e2530",
        background: "#0f1419",
      }}
    >
      {/* Transport buttons */}
      <PbBtn onClick={() => { setCurrentTime(startMs); setIsPlaying(false); }} title="Go to start">⏮</PbBtn>
      <PbBtn onClick={togglePlayback} active={isPlaying} title={isPlaying ? "Pause" : "Play"}>⏯</PbBtn>
      <PbBtn onClick={() => { setCurrentTime(endMs); setIsPlaying(false); }} title="Go to end">⏭</PbBtn>

      {/* Scrubber */}
      <input
        type="range"
        min={startMs}
        max={endMs}
        value={Math.min(Math.max(currentTime, startMs), endMs)}
        onChange={(e) => {
          setCurrentTime(parseInt(e.target.value));
          setIsPlaying(false);
        }}
        className="flex-1 h-1 cursor-pointer accent-[#378add]"
        style={{ maxWidth: "200px" }}
      />

      {/* Current time */}
      <span className="font-mono text-[10px] text-[#6b7280]">{fmtTime(currentTime)}</span>

      {/* Speed selector */}
      <select
        value={playbackSpeed}
        onChange={(e) => setPlaybackSpeed(parseInt(e.target.value) as 1 | 2 | 4)}
        className="font-mono text-[10px] text-[#e5e7eb] cursor-pointer focus:outline-none"
        style={{
          width: "46px",
          background: "#1e2530",
          border: "0.5px solid #2a3040",
          borderRadius: "3px",
          padding: "2px 4px",
        }}
      >
        <option value={1}>1x</option>
        <option value={2}>2x</option>
        <option value={4}>4x</option>
      </select>

      {/* Mode badge */}
      <span
        className="font-mono uppercase text-[#6b7280]"
        style={{ fontSize: "10px" }}
      >
        Replay
      </span>

      {/* Range */}
      <span className="font-mono text-[#4b5563]" style={{ fontSize: "9px" }}>
        {fmtTime(startMs)} – {fmtTime(endMs)}
      </span>
    </div>
  );
}

function PbBtn({
  children,
  onClick,
  active,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="font-mono text-[10px] cursor-pointer transition-colors"
      style={{
        padding: "3px 7px",
        borderRadius: "3px",
        background: active ? "#162040" : "#1e2530",
        border: `0.5px solid ${active ? "#378add" : "#2a3040"}`,
        color: active ? "#85b7eb" : "#e5e7eb",
      }}
    >
      {children}
    </button>
  );
}
