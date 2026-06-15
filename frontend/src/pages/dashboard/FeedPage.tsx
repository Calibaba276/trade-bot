import { LiveLogicFeed } from "../../components/dashboard/LiveLogicFeed";

export function FeedPage() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <p className="text-sm text-text-secondary mb-4 max-w-2xl">
        The bot's internal thought process, streamed in real time. Every scan, detection, verdict,
        and execution is logged here — exactly when it happens.
      </p>
      <LiveLogicFeed heightClass="h-[calc(100vh-260px)]" showMarketTabs />
    </div>
  );
}
