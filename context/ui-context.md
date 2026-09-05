# Glass Box: UI Context

## Design direction

Dark-first precision fintech: **“terminal meets gallery.”** The interface is dense and data-literate but calm, deliberate, and legible. The dashboard must make an automated system feel inspectable, never mystical. Use borders rather than card shadows; use motion only to communicate a state/data change.

## Existing implementation constraints

- React + Vite + Tailwind CSS 3 is the active frontend stack.
- There is no installed shadcn/ui or Lucide dependency. Do not assume either exists; use existing components/native accessible controls unless a task explicitly authorizes adding a dependency.
- Extend the existing `tailwind.config.js` and `src/index.css`; do not create a second, conflicting design-token system.

## Tokens

| Category | Token | Value | Use |
| --- | --- | --- | --- |
| Canvas | `bg-base` | `#080C10` | Page background |
| Surface | `bg-surface` / `bg-elevated` / `bg-overlay` | `#0D1117` / `#161B22` / `#1C2128` | Panels, nested controls, modal/tooltip |
| Border | `border-subtle` / `border-muted` / `border-active` | `#21262D` / `#30363D` / `#388BFD` | Separation, emphasis, focus |
| Text | `text-primary` / `text-secondary` / `text-muted` | `#E6EDF3` / `#8B949E` / `#484F58` | Content hierarchy |
| Brand | `brand-blue` / `brand-dim` | `#388BFD` / `#1F6FEB` | Primary action, active selection |
| Trade | `bull` / `bull-dim` | `#3FB950` / `#1A4A22` | Buy/profit/success |
| Trade | `bear` / `bear-dim` | `#F85149` / `#4A1A1A` | Sell/loss/error |
| Caution | `amber` / `amber-dim` | `#D29922` / `#3D2E00` | Pending/warning |
| Critical | `halt` | `#FF6B6B` | Halted engine only |
| Special | `breakeven` | `#A8B1FF` | Breakeven events |

Use token classes such as `bg-bg-surface`, `text-text-secondary`, and `border-border-subtle`, not arbitrary colors. `brand-glow` is an accent/update halo, not a broad background gradient.

## Typography and layout

- Display/headline: Space Mono, `text-5xl` display or `text-3xl` page H1.
- UI/body: Geist, usually `text-sm`; captions use `text-xs text-text-secondary`.
- Prices, P&L, percentages, counts, and timestamps: JetBrains Mono / `font-mono`; use shared formatting helpers.
- 4px spacing scale. Standard panel padding `p-4`; prominent panels `p-6`; card grid gap `gap-4`; major section gap `gap-6`.
- Cards `rounded-lg`; buttons `rounded-md`; badges `rounded-full`; chart containers `rounded-xl`.
- Dashboard desktop layout reserves a 240px left sidebar. Keep important trade/risk information responsive and reachable on narrow screens.

## Component patterns

### Panels and data states

- Standard panel: `bg-bg-surface border border-border-subtle rounded-lg`.
- Nested/filter panel: `bg-bg-elevated`; modal/tooltip: `bg-bg-overlay`.
- Every async panel needs loading, empty, error, and populated states with a fixed/minimum height that avoids layout jumps.
- Show provenance where useful: live/replay, timestamp, account, and stale/reconnecting state.

### Buttons and controls

- Primary: solid `brand-blue`, clear action verb, visible focus state.
- Secondary: border/ghost treatment; destructive action uses an explicit confirmation and bear/halt semantic color.
- Icon-only button: accessible name (`aria-label`/tooltip), keyboard focus, and a non-color state cue.
- Keyboard shortcuts belong in a discoverable help surface and must not fire while typing in an input.

### Status and trading semantics

- Communicate status with color **and** text/icon/shape: e.g. `● LIVE`, `✓ Filled`, `! Halted`.
- Bull/bear colors represent direction/outcome only; amber means pending/caution; halt is reserved for a real execution stop.
- Never display estimated or stale information as real-time. Show “reconnecting”, “no data yet”, or the last-update timestamp.
- Verdict details show entry, SL, TP, scenario, condition evidence, and execution outcome together so the explanation is not fragmented.

### Chart and replay

- Chart is the evidence surface, not decorative analytics. Render candle/event overlays only from persisted data.
- Overlay vocabulary: FVG amber, OB blue, MSS teal/brand-blue, BOS purple where established, entry/exit pins with labels.
- Replay controls show selected time, speed, and boundary state; future candles/events stay hidden until the replay cursor reaches them.
- Avoid heavy animated re-rendering of chart data. Dispose subscriptions/chart resources on unmount.

## Motion and accessibility

- 150ms micro-interactions, 300ms panels, 500ms data reveal; `ease-out` entering and `ease-in` leaving.
- Use existing `data-flash`, `pulse-dot`, `blink`, and `slide-in` utilities only when they communicate a change.
- Honor the existing `prefers-reduced-motion` override; never animate layout shifts.
- Maintain contrast, semantic headings, visible focus, keyboard navigation, form labels/errors, and descriptive empty states. Plain-English tooltips should explain ICT terminology for newcomers.

## Marketing vs dashboard

Marketing pages may use more whitespace and explanatory copy, but must retain the same palette and make no unsupported performance claims. Dashboard pages prioritize scanability, dense factual data, and immediate visibility of errors/halt states.
