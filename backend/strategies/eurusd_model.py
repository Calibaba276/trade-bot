"""Pure, timezone-safe domain foundation for the EURUSD ICT strategy.

This module intentionally contains no broker, database, messaging, or strategy
framework imports.  Detection rules and the state machine are added in later
implementation steps; the types here make their time and immutability contract
explicit first.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum
from math import isfinite
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UTC = timezone.utc
NY_TZ = ZoneInfo("America/New_York")
WAT_TZ = ZoneInfo("Africa/Lagos")


class SetupState(str, Enum):
    """Ordered stages of one EURUSD ICT setup."""

    AWAITING_BIAS = "awaiting_bias"
    AWAITING_RANGE = "awaiting_range"
    AWAITING_SWEEP = "awaiting_sweep"
    SWEPT_AWAITING_MSS = "swept_awaiting_mss"
    MSS_CONFIRMED_AWAITING_FVG = "mss_confirmed_awaiting_fvg"
    AWAITING_RETRACEMENT = "awaiting_retracement"
    SETUP_READY = "setup_ready"


def _require_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value


def _require_finite(value: float, *, field_name: str) -> float:
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


class ClosedCandle(BaseModel):
    """A fully closed OHLC candle supplied to future pure detection rules."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, field_name="timestamp")

    @model_validator(mode="after")
    def validate_ohlcv(self) -> ClosedCandle:
        for field_name in ("open", "high", "low", "close", "volume"):
            _require_finite(getattr(self, field_name), field_name=field_name)
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within the candle high/low")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within the candle high/low")
        if self.volume < 0:
            raise ValueError("volume must not be negative")
        return self


class EURUSDModelState(BaseModel):
    """Mutable in-memory state; never an execution or persistence contract."""

    state: SetupState = SetupState.AWAITING_BIAS
    trading_date_ny: date | None = None
    bias: Literal["bullish", "bearish"] | None = None
    bias_swing_count: int = 0
    range_high: float | None = None
    range_low: float | None = None
    range_mid: float | None = None
    last_processed_candle_time: datetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> EURUSDModelState:
        if self.last_processed_candle_time is not None:
            _require_utc(
                self.last_processed_candle_time, field_name="last_processed_candle_time"
            )
        if self.bias_swing_count < 0:
            raise ValueError("bias_swing_count must not be negative")
        return self


class Setup(BaseModel):
    """Immutable handoff from detection to the later selectivity layer."""

    model_config = ConfigDict(frozen=True)

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

    @field_validator("timestamp", "sweep_time", "mss_time")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, field_name="Setup timestamp")


def ny_killzone_window_utc(
    reference_date_utc: datetime, ny_start: time, ny_end: time
) -> tuple[datetime, datetime]:
    """Return a same-day NY-local killzone as UTC-aware boundaries."""
    _require_utc(reference_date_utc, field_name="reference_date_utc")
    if ny_end <= ny_start:
        raise ValueError("killzone end must be after its start")
    ny_date = reference_date_utc.astimezone(NY_TZ).date()
    start_ny = datetime.combine(ny_date, ny_start, tzinfo=NY_TZ)
    end_ny = datetime.combine(ny_date, ny_end, tzinfo=NY_TZ)
    return start_ny.astimezone(UTC), end_ny.astimezone(UTC)


def ny_midnight_range_window_utc(
    reference_date_utc: datetime,
) -> tuple[datetime, datetime]:
    """Return NY midnight through 03:00 local for the relevant NY trading day."""
    _require_utc(reference_date_utc, field_name="reference_date_utc")
    ny_date = reference_date_utc.astimezone(NY_TZ).date()
    start_ny = datetime.combine(ny_date, time.min, tzinfo=NY_TZ)
    end_ny = datetime.combine(ny_date, time(3), tzinfo=NY_TZ)
    return start_ny.astimezone(UTC), end_ny.astimezone(UTC)


def to_wat_for_display(dt_utc: datetime) -> datetime:
    """Convert UTC to WAT for display only; never use this in strategy logic."""
    _require_utc(dt_utc, field_name="dt_utc")
    return dt_utc.astimezone(WAT_TZ)
