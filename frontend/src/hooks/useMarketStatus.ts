import { useEffect, useState } from "react";
import { isMarketOpen } from "../utils/market";

/** Reactive forex market open/closed flag, re-checked once a minute. */
export function useMarketStatus(): boolean {
  const [open, setOpen] = useState(isMarketOpen);
  useEffect(() => {
    const id = setInterval(() => setOpen(isMarketOpen()), 60_000);
    return () => clearInterval(id);
  }, []);
  return open;
}
