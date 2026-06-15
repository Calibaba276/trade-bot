# ICT Model — standalone backtest

`ict_backtest.py` is a dependency-light, faithful re-implementation of the
decision logic in `backend/strategies/ict_model.py`. It drives the exact same
session/sweep/MSS/FVG/OTE branching over 1-minute bars, emits the same signals,
then resolves each one against future price action.

It deliberately does **not** import lumibot / supabase / MetaTrader5 — none of
those run in a Linux/CI sandbox (the `MetaTrader5` package is Windows-only and
requires a running terminal), so this harness reproduces the strategy's behaviour
without them.

## Data

Oanda EUR/USD 1-minute bars from the public
[`FutureSharks/financial-data`](https://github.com/FutureSharks/financial-data)
dataset (coverage ~2005–2020). The raw timestamps are UTC; the live strategy runs
in `Africa/Lagos` (UTC+1, no DST), so bars are shifted +1h to reproduce the
06:00 / 09:00 / 13:30 / 16:00 session windows.

The CSVs are not committed (large). Fetch them into `_fxdata/EUR_USD/<year>/`:

```bash
git clone --no-checkout --depth 1 --filter=blob:none \
  https://github.com/FutureSharks/financial-data.git /tmp/fxdata
cd /tmp/fxdata
git sparse-checkout init --cone
git sparse-checkout set pyfinancialdata/data/currencies/oanda/EUR_USD
git checkout
mkdir -p <repo>/_fxdata/EUR_USD
cp -r pyfinancialdata/data/currencies/oanda/EUR_USD/{2018,2019,2020} <repo>/_fxdata/EUR_USD/
```

## Run

```bash
pip install pandas numpy
python -m backend.backtest.ict_backtest
```

## Modelling assumptions

| Item            | Choice |
|-----------------|--------|
| `last_price`    | close of the current 1-minute bar |
| historical data | last N completed bars up to & incl. current |
| entry           | **limit** at the strategy's entry price; filled only if price touches it before the signal day ends (else discarded) |
| outcome         | from the fill bar, first of SL/TP touched intrabar wins; a bar straddling both counts as a **loss** (conservative); unresolved within 3 days = `open` |
| target          | **opposing liquidity pool** (PDL/PDH for London, pre-NY low/high for NY continuation, NY range low/high for range), enforced to be at least 3R away — else the trade is skipped (canonical ICT min 1:3 to liquidity) |
| risk            | $500/trade; reward = $500 × (actual RR to liquidity, ≥3) on a win |
| costs           | zero in the headline; a spread-sensitivity table is printed separately |

Runs both `EUR_USD` and `GBP_USD` for 2018–2020. Stage GBP data the same way as
EUR (sparse-checkout `.../oanda/GBP_USD`).
