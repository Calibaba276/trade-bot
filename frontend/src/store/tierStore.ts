import { create } from "zustand";

export type Tier = "starter" | "pro";

const STORAGE_KEY = "glassbox.tier";

function loadTier(): Tier {
  if (typeof localStorage === "undefined") return "pro";
  return localStorage.getItem(STORAGE_KEY) === "starter" ? "starter" : "pro";
}

interface TierStore {
  tier: Tier;
  setTier: (tier: Tier) => void;
  toggleTier: () => void;
}

/**
 * Subscription tier (Starter vs Pro).
 *
 * Until billing is live this is a client-side preview switch so the dashboard
 * can be viewed as either plan. When billing ships, seed this from the user's
 * actual subscription instead of localStorage.
 */
export const useTierStore = create<TierStore>((set, get) => ({
  tier: loadTier(),
  setTier: (tier) => {
    localStorage.setItem(STORAGE_KEY, tier);
    set({ tier });
  },
  toggleTier: () => get().setTier(get().tier === "pro" ? "starter" : "pro"),
}));

/** Capabilities gated by tier. Single source of truth for feature checks. */
export const TIER_FEATURES = {
  starter: {
    label: "Starter",
    propFirmPanel: false,
    replayMode: false,
    maxAccounts: 1,
  },
  pro: {
    label: "Pro",
    propFirmPanel: true,
    replayMode: true,
    maxAccounts: 10,
  },
} as const;
