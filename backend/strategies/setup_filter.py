"""Validated contracts for the EURUSD setup selectivity boundary.

This module intentionally contains models only. Detection logic, filter checks,
configuration, and audit persistence will be added in later reviewed steps.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _require_utc_aware(value: datetime) -> datetime:
    """Reject timestamps that are naive or carry a non-UTC offset."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware UTC datetimes")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("timestamps must use UTC")
    return value


class Setup(BaseModel):
    """Immutable handoff from EURUSD pattern detection to setup filtering."""

    timestamp: datetime
    instrument: Literal["EURUSD"] = "EURUSD"
    direction: Literal["long", "short"]

    bias: Literal["bullish", "bearish"]
    bias_swing_count: int = Field(ge=0)

    range_high: float
    range_low: float
    range_mid: float
    entry_zone: Literal["premium", "discount"]

    target_liquidity_level: float
    target_liquidity_type: str

    sweep_time: datetime
    sweep_extreme_price: float
    sweep_level_type: str
    sweep_in_killzone: bool
    killzone_label: str | None = None

    mss_time: datetime
    mss_candle_index: int
    sweep_candle_index: int
    mss_displacement_atr_multiple: float = Field(ge=0)

    fvg_high: float | None = None
    fvg_low: float | None = None
    fvg_ce: float | None = None
    ob_high: float | None = None
    ob_low: float | None = None
    extract_fvg_and_order_block: Literal["fvg_only", "ob_only", "both"]

    entry_price: float
    stop_price: float
    target_price: float

    model_config = {"frozen": True}

    _timestamp_is_utc = field_validator("timestamp", "sweep_time", "mss_time")(
        _require_utc_aware
    )


class FilterCheckResult(BaseModel):
    """One named filter check and its explainable score."""

    check_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    reason: str


class FilterResult(BaseModel):
    """Complete filter outcome for one immutable setup."""

    setup: Setup
    passed: bool
    composite_score: float
    checks: list[FilterCheckResult]
    rejected_by: str | None = None


class FilterContext(BaseModel):
    """Session state required by checks but not part of the immutable setup."""

    trades_taken_today: int = 0
    last_setup_time: datetime | None = None
    last_setup_killzone: str | None = None
    setups_this_killzone: int = 0

    _last_setup_time_is_utc = field_validator("last_setup_time")(_require_utc_aware)
