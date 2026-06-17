/** Glossary tooltip — keyboard + hover accessible, dotted underline on the term.
 *  Ported from Landing.tsx so dashboard components can gloss ICT jargon. */
export function Term({ children, def }: { children: React.ReactNode; def: string }) {
  return (
    <span className="relative group inline-block">
      <button
        type="button"
        className="border-b border-dotted border-text-secondary text-inherit cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded-sm"
        aria-label={typeof children === "string" ? children : undefined}
      >
        {children}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 z-50 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity duration-150 bg-bg-overlay border border-border-muted rounded-lg p-3 text-xs font-sans font-normal text-text-secondary leading-relaxed shadow-lg"
      >
        {def}
      </span>
    </span>
  );
}

export const ICT_DEFS = {
  FVG: "Fair Value Gap: a price gap where the market moved so fast that buyers and sellers never fully traded at those levels. Smart money tends to return to fill these gaps.",
  MSS: "Market Structure Shift: the moment the market definitively changes direction — detected when price breaks a specific previous swing point.",
  BOS: "Break of Structure: price breaks a significant swing point, confirming that the trend is shifting direction.",
  OB:  "Order Block: a specific candle or cluster representing institutional buy/sell orders. Price often returns to these levels to fill remaining orders.",
  ICT: "Inner Circle Trader — a framework for reading how institutional banks and funds move prices, and trading alongside them.",
  PDH: "Previous Day High / Low — the highest and lowest prices from the prior trading session. Key reference levels for the engine's bias.",
  swept_high:    "The swing high that was swept (a false breakout above) to grab liquidity before price reversed lower.",
  swept_low:     "The swing low that was swept (a false breakout below) to grab liquidity before price reversed higher.",
  mss_confirmed: "Market Structure Shift confirmed — price broke the swing that signals a directional change.",
  fvg_confirmed: "Fair Value Gap confirmed — an imbalance zone identified as a valid entry area.",
  fvg_top:       "Top boundary of the Fair Value Gap. Price tends to revisit and react off this level.",
  fvg_bottom:    "Bottom boundary of the Fair Value Gap.",
  mss_level:     "The exact price where the Market Structure Shift was confirmed.",
  sweep_point:   "The price level where liquidity was swept before the reversal entry.",
  pdh:           "Previous Day High — the high of the prior session. A key reference for daily bias.",
  pdl:           "Previous Day Low — the low of the prior session. A key reference for daily bias.",
} as const;
