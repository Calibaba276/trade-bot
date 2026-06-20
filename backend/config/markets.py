"""
markets.py — single source of truth for plan → market access.

Signals are broadcast to EVERY worker over the same Redis channel. Each worker
decides whether it is allowed to act on a given signal. Market access is gated
here: a Starter account only executes Starter markets, a Pro account executes
the full Pro set. The per-account `enabled_markets` column lets a user opt out
of any market their plan permits — this module supplies the plan ceiling and the
default (all-permitted) list new accounts start with.

Only EURUSD and XAUUSD are live in the engine today. The index/crypto markets
are declared here so the plan ceiling and dashboard are correct ahead of those
runners shipping — an account can "enable" NAS100 now, it just won't receive a
signal until that strategy exists.
"""

from typing import Iterable, List

# Canonical (broker-agnostic) market base names. Broker symbols carry suffixes
# (EURUSDm, XAUUSD.raw, US30-ECN); matching is done by prefix in is_market_enabled
# so the canonical base is all we store.
STARTER_MARKETS: List[str] = ["EURUSD", "XAUUSD"]

# Pro = everything Starter gets, plus US indices and crypto.
# NAS100 / US30 / SPX500 / BTCUSD / ETHUSD are not yet wired to a runner.
PRO_ONLY_MARKETS: List[str] = ["NAS100", "US30", "SPX500", "BTCUSD", "ETHUSD"]
PRO_MARKETS: List[str] = STARTER_MARKETS + PRO_ONLY_MARKETS

PLAN_MARKETS = {
    "starter": STARTER_MARKETS,
    "pro": PRO_MARKETS,
}

DEFAULT_PLAN = "starter"


def markets_for_plan(plan: str) -> List[str]:
    """Return the full list of markets a plan permits (the access ceiling)."""
    return list(PLAN_MARKETS.get(str(plan or "").lower(), PLAN_MARKETS[DEFAULT_PLAN]))


# Broker suffixes that decorate the canonical ticker — the micro-lot "m", a
# liquidity/account tag after a separator (.raw, -ECN, _pro, #, !). These are
# stripped before matching so EURUSDm resolves to EURUSD. We deliberately do NOT
# strip arbitrary trailing letters: that's what told EURUSD apart from EURUSDT
# (Tether) and BTCUSD from BTCUSDT — a bare prefix match would conflate them.
_KNOWN_TRAILING_SUFFIXES = ("MICRO", "PRO", "ECN", "RAW", "M", "C", "Z")
_SEPARATORS = ".-_#!/ "


def normalize_symbol(symbol: str) -> str:
    """Uppercase and strip non-alphanumerics so EURUSDm, eurusd, EUR/USD all
    reduce to a comparable form (EURUSDM, EURUSD, EURUSD)."""
    return "".join(ch for ch in str(symbol or "").upper() if ch.isalnum())


def _strip_broker_suffix(symbol: str) -> str:
    """
    Reduce a broker symbol to its canonical ticker for exact matching.

    Drops anything after a separator (EURUSD.raw → EURUSD, US30-ECN → US30) then
    removes one trailing decoration tag (EURUSDm → EURUSD). Only the known tags
    in _KNOWN_TRAILING_SUFFIXES are removed, so EURUSDT / BTCUSDT keep their final
    letter and never collapse onto EURUSD / BTCUSD.
    """
    raw = str(symbol or "").upper()
    for sep in _SEPARATORS:
        if sep in raw:
            raw = raw.split(sep, 1)[0]
    norm = "".join(ch for ch in raw if ch.isalnum())
    for suffix in _KNOWN_TRAILING_SUFFIXES:
        if norm.endswith(suffix) and len(norm) > len(suffix):
            return norm[: -len(suffix)]
    return norm


def is_market_enabled(symbol: str, enabled_markets: Iterable[str]) -> bool:
    """
    True when a broker symbol belongs to one of the account's enabled markets.

    Matching is exact on the canonical ticker after broker suffixes are stripped,
    so EURUSDm → EURUSD matches enabled "EURUSD" but EURUSDT (Tether) does not.
    An empty/None enabled_markets means "nothing enabled" → False (fail closed).
    """
    if not enabled_markets:
        return False
    norm = normalize_symbol(symbol)
    canonical = _strip_broker_suffix(symbol)
    if not norm:
        return False
    for market in enabled_markets:
        base = normalize_symbol(market)
        # Match either the raw normalized symbol (broker uses the bare ticker)
        # or the suffix-stripped canonical form (broker adds a decoration tag).
        if base and (norm == base or canonical == base):
            return True
    return False
