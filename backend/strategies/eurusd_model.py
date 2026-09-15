"""Pure, timezone-safe domain foundation for the EURUSD ICT strategy.

This module intentionally contains no broker, database, messaging, or strategy
framework imports.  Detection rules and the state machine are added in later
implementation steps; the types here make their time and immutability contract
explicit first.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from itertools import pairwise
from math import isfinite
from typing import ClassVar, Literal
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
    processed_bar_count: int = 0
    target_liquidity_level: float | None = None
    target_liquidity_type: str | None = None
    sweep_time: datetime | None = None
    sweep_extreme_price: float | None = None
    sweep_level_type: str | None = None
    sweep_candle_index: int | None = None
    sweep_in_killzone: bool = False
    killzone_label: str | None = None
    mss_time: datetime | None = None
    mss_candle_index: int | None = None
    mss_displacement_atr_multiple: float | None = None
    pre_mss_candle: ClosedCandle | None = None
    mss_candle: ClosedCandle | None = None
    mss_order_block_candle: ClosedCandle | None = None
    displacement_swing_price: float | None = None
    fvg_high: float | None = None
    fvg_low: float | None = None
    fvg_ce: float | None = None
    ob_high: float | None = None
    ob_low: float | None = None
    imbalance_kind: Literal["fvg_only", "ob_only", "both"] | None = None

    @model_validator(mode="after")
    def validate_state(self) -> EURUSDModelState:
        if self.last_processed_candle_time is not None:
            _require_utc(
                self.last_processed_candle_time, field_name="last_processed_candle_time"
            )

        if self.bias_swing_count < 0:
            raise ValueError("bias_swing_count must not be negative")
        if self.processed_bar_count < 0:
            raise ValueError("processed_bar_count must not be negative")

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

    @field_validator(
        "range_high",
        "range_low",
        "range_mid",
        "target_liquidity_level",
        "sweep_extreme_price",
        "mss_displacement_atr_multiple",
        "fvg_high",
        "fvg_low",
        "fvg_ce",
        "ob_high",
        "ob_low",
        "entry_price",
        "stop_price",
        "target_price",
    )
    @classmethod
    def numeric_values_must_be_finite(cls, value: float | None) -> float | None:
        if value is None:
            return None

        return _require_finite(value, field_name="Setup numeric value")


class BiasEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    bias: Literal["bullish", "bearish"] | None
    swing_count: int = Field(ge=0)
    dxy_inverse_correlation: Literal["bullish", "bearish", "neutral"] | None = None
    gbpusd_smt: Literal["bullish", "bearish", "neutral"] | None = None
    dxy_conflict: bool = False


class RangeLevels(BaseModel):
    model_config = ConfigDict(frozen=True)

    midnight_high: float
    midnight_low: float
    midnight_mid: float
    asian_high: float | None = None
    asian_low: float | None = None
    asian_mid: float | None = None


class LiquidityTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: float
    level_type: str
    direction: Literal["long", "short"]


class Sweep(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    candle_index: int = Field(ge=0)
    level: float
    level_type: str
    direction: Literal["long", "short"]
    extreme_price: float

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, field_name="timestamp")


class MSSConfirmation(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    candle_index: int = Field(ge=0)
    direction: Literal["long", "short"]
    broken_swing: float
    atr: float = Field(gt=0)
    displacement_atr_multiple: float = Field(ge=1.5)
    body_to_wick_ratio: float = Field(ge=0.7, le=1.0)
    timeframe: Literal["M5", "M3", "M1"]

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, field_name="timestamp")


class ImbalanceSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    fvg_high: float | None = None
    fvg_low: float | None = None
    fvg_ce: float | None = None
    ob_high: float | None = None
    ob_low: float | None = None
    kind: Literal["fvg_only", "ob_only", "both"]


def _ordered(candles: Sequence[ClosedCandle]) -> list[ClosedCandle]:
    result = list(candles)

    if any(left.timestamp >= right.timestamp for left, right in pairwise(result)):
        raise ValueError("candles must be strictly chronological")

    return result


def _atr(candles: Sequence[ClosedCandle], period: int = 14) -> float:
    if len(candles) < period + 1:
        raise ValueError("not enough candles for ATR")

    true_ranges = []

    for previous, candle in zip(candles[-period - 1 : -1], candles[-period:]):
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - previous.close), abs(candle.low - previous.close)))

    value = sum(true_ranges) / period

    if value <= 0:
        raise ValueError("ATR must be positive")
    return value


def determine_bias(
    candles: Sequence[ClosedCandle], *, dxy_bias: Literal["bullish", "bearish"] | None = None,
    gbpusd_bias: Literal["bullish", "bearish"] | None = None,
) -> BiasEvidence:
    """Infer structure from confirmed three-candle swings; contextual symbols never lead."""
    ordered = _ordered(candles)

    if len(ordered) < 7:
        return BiasEvidence(bias=None, swing_count=0)

    highs = [ordered[i].high for i in range(1, len(ordered) - 1) if ordered[i].high > ordered[i - 1].high and ordered[i].high > ordered[i + 1].high]

    lows = [ordered[i].low for i in range(1, len(ordered) - 1) if ordered[i].low < ordered[i - 1].low and ordered[i].low < ordered[i + 1].low]

    bullish = len(highs) >= 2 and len(lows) >= 2 and highs[-1] > highs[-2] and lows[-1] > lows[-2]
    bearish = len(highs) >= 2 and len(lows) >= 2 and highs[-1] < highs[-2] and lows[-1] < lows[-2]

    bias = "bullish" if bullish and not bearish else "bearish" if bearish and not bullish else None
    dxy_conflict = bias is not None and dxy_bias == ("bullish" if bias == "bullish" else "bearish")

    return BiasEvidence(
        bias=bias,
        swing_count=min(len(highs), len(lows)),
        dxy_inverse_correlation=None if dxy_bias is None else ("bearish" if dxy_bias == "bullish" else "bullish"),
        gbpusd_smt=None if gbpusd_bias is None else ("bullish" if gbpusd_bias == bias else "bearish"),
        dxy_conflict=dxy_conflict,
    )


def build_ranges(candles: Sequence[ClosedCandle], reference_date_utc: datetime) -> RangeLevels:
    ordered = _ordered(candles)

    start, end = ny_midnight_range_window_utc(reference_date_utc)

    if reference_date_utc < end:
        raise ValueError("midnight range is not complete")

    midnight = [c for c in ordered if start <= c.timestamp < end]

    if len(midnight) < 2 or midnight[0].timestamp != start:
        raise ValueError("midnight range requires complete candle coverage")

    interval = midnight[1].timestamp - midnight[0].timestamp

    if interval <= timedelta(0) or any(
        right.timestamp - left.timestamp != interval
        for left, right in pairwise(midnight)
    ) or midnight[-1].timestamp + interval != end:
        raise ValueError("midnight range requires complete candle coverage")

    ny_date = reference_date_utc.astimezone(NY_TZ).date()
    asian_start = datetime.combine(ny_date - timedelta(days=1), time(19), tzinfo=NY_TZ).astimezone(UTC)
    asian_end = datetime.combine(ny_date, time.min, tzinfo=NY_TZ).astimezone(UTC)
    asian = [c for c in ordered if asian_start <= c.timestamp < asian_end]
    ah = max(c.high for c in asian) if asian else None
    al = min(c.low for c in asian) if asian else None
    mh, ml = max(c.high for c in midnight), min(c.low for c in midnight)

    return RangeLevels(
        midnight_high=mh,
        midnight_low=ml,
        midnight_mid=(mh + ml) / 2,
        asian_high=ah,
        asian_low=al,
        asian_mid=None if ah is None or al is None else (ah + al) / 2)


def select_liquidity_target(*, direction: Literal["long", "short"], previous_day_high: float | None = None, previous_day_low: float | None = None, asian_high: float | None = None, asian_low: float | None = None, previous_session_level: float | None = None, equal_high_low: float | None = None, opposite_range_side: float) -> LiquidityTarget:
    candidates = [(previous_day_high if direction == "long" else previous_day_low, "pdh" if direction == "long" else "pdl"), (asian_high if direction == "long" else asian_low, "asian_high" if direction == "long" else "asian_low"), (previous_session_level, "previous_session"), (equal_high_low, "m15_equal_level"), (opposite_range_side, "opposite_range_side")]

    level, label = next((item for item in candidates if item[0] is not None), (None, ""))

    if level is None:
        raise ValueError("a liquidity target is required")

    return LiquidityTarget(
        level=level,
        level_type=label,
        direction=direction)


def detect_sweep(candles: Sequence[ClosedCandle], *, level: float, level_type: str, direction: Literal["long", "short"]) -> Sweep | None:
    for index, candle in enumerate(_ordered(candles)):
        swept = candle.low < level and candle.close > level if direction == "long" else candle.high > level and candle.close < level

        if swept:
            return Sweep(
                timestamp=candle.timestamp,
                candle_index=index,
                level=level,
                level_type=level_type,
                direction=direction,
                extreme_price=candle.low if direction == "long" else candle.high)
    return None


def confirm_mss(candles: Sequence[ClosedCandle], *, counter_trend_swing: float, direction: Literal["long", "short"], timeframe: Literal["M5", "M3", "M1"] = "M5", m5_confirmed: bool = False) -> MSSConfirmation | None:
    ordered = _ordered(candles)

    if timeframe != "M5" and not m5_confirmed:
        return None

    if len(ordered) < 16:
        raise ValueError("not enough candles for MSS confirmation")

    candle = ordered[-1]
    atr = _atr(ordered[:-1])
    body = abs(candle.close - candle.open)
    wick = (candle.high - candle.low) - body
    ratio = body / (body + wick) if body + wick else 0
    crossed = candle.close > counter_trend_swing if direction == "long" else candle.close < counter_trend_swing
    aligned = candle.close > candle.open if direction == "long" else candle.close < candle.open
    multiple = body / atr

    if not (crossed and aligned and multiple >= 1.5 and ratio >= 0.7):
        return None

    return MSSConfirmation(
        timestamp=candle.timestamp,
        candle_index=len(ordered) - 1,
        direction=direction,
        broken_swing=counter_trend_swing,
        atr=atr,
        displacement_atr_multiple=multiple,
        body_to_wick_ratio=ratio,
        timeframe=timeframe,
    )


def extract_imbalances(candles: Sequence[ClosedCandle], *, mss_index: int, direction: Literal["long", "short"]) -> ImbalanceSet:
    ordered = _ordered(candles)

    if mss_index < 1 or mss_index + 1 >= len(ordered):
        raise ValueError("invalid MSS index")

    first, current = ordered[mss_index - 1], ordered[mss_index + 1]
    opposing = next((c for c in reversed(ordered[:mss_index]) if (c.close < c.open if direction == "long" else c.close > c.open)), None)
    return _extract_imbalance_values(
        first=first,
        third=current,
        opposing=opposing,
        direction=direction,
    )


def _extract_imbalance_values(
    *,
    first: ClosedCandle,
    third: ClosedCandle,
    opposing: ClosedCandle | None,
    direction: Literal["long", "short"],
) -> ImbalanceSet:
    fvg_low, fvg_high = (
        (first.high, third.low)
        if direction == "long" and third.low > first.high
        else (third.high, first.low)
        if direction == "short" and third.high < first.low
        else (None, None)
    )
    ob_high, ob_low = (opposing.high, opposing.low) if opposing else (None, None)

    kind = "both" if fvg_low is not None and opposing else "fvg_only" if fvg_low is not None else "ob_only" if opposing else None

    if kind is None:
        raise ValueError("MSS impulse contains no FVG or opposing order block")

    return ImbalanceSet(
        fvg_high=fvg_high,
        fvg_low=fvg_low,
        fvg_ce=None if fvg_low is None else (fvg_low + fvg_high) / 2, #type:ignore
        ob_high=ob_high,
        ob_low=ob_low,
        kind=kind)


class EURUSDModel:
    """Closed-candle state machine for one EURUSD ICT setup at a time."""

    _STOP_OFFSET = 0.0003
    _MAX_STOP_DISTANCE = 0.0020
    _BAR_INTERVALS: ClassVar[dict[Literal["M5", "M3", "M1"], timedelta]] = {
        "M5": timedelta(minutes=5),
        "M3": timedelta(minutes=3),
        "M1": timedelta(minutes=1),
    }
    _LONDON_KILLZONE = (time(2), time(5))
    _NY_AM_KILLZONE = (time(7), time(10))

    def __init__(self) -> None:
        self.state = EURUSDModelState()

    def reset(self, trading_date_ny: date | None = None) -> None:
        """Discard an incomplete setup without retaining trade-affecting context."""
        self.state = EURUSDModelState(trading_date_ny=trading_date_ny)

    def process_closed_candles(
        self,
        candles: Sequence[ClosedCandle],
        *,
        bias_evidence: BiasEvidence | None,
        ranges: RangeLevels | None,
        liquidity_target: LiquidityTarget | None,
        sweep_level: float | None,
        sweep_level_type: str | None,
        counter_trend_swing: float | None,
        timeframe: Literal["M5", "M3", "M1"] = "M5",
        m5_confirmed: bool = False,
    ) -> Setup | None:
        """Advance using only a chronological sequence ending in one closed candle."""
        ordered = _ordered(candles)
        if not ordered:
            return None
        candle = ordered[-1]
        last_processed = self.state.last_processed_candle_time
        if last_processed is not None and candle.timestamp <= last_processed:
            return None
        ny_date = candle.timestamp.astimezone(NY_TZ).date()
        if (
            last_processed is not None
            and self.state.trading_date_ny == ny_date
            and candle.timestamp - last_processed != self._BAR_INTERVALS[timeframe]
        ):
            self.reset(ny_date)
            self.state.last_processed_candle_time = candle.timestamp
            return None
        if self.state.trading_date_ny != ny_date:
            self.reset(ny_date)
        self.state.last_processed_candle_time = candle.timestamp
        bar_index = self.state.processed_bar_count
        self.state.processed_bar_count += 1

        if bias_evidence is not None and bias_evidence.dxy_conflict:
            self.reset(ny_date)
            self.state.last_processed_candle_time = candle.timestamp
            return None

        if self.state.state == SetupState.AWAITING_BIAS:
            if bias_evidence is None or bias_evidence.bias is None:
                return None
            self.state.bias = bias_evidence.bias
            self.state.bias_swing_count = bias_evidence.swing_count
            self.state.state = SetupState.AWAITING_RANGE

        if self.state.state == SetupState.AWAITING_RANGE:
            if ranges is None:
                return None
            self.state.range_high = ranges.midnight_high
            self.state.range_low = ranges.midnight_low
            self.state.range_mid = ranges.midnight_mid
            self.state.state = SetupState.AWAITING_SWEEP

        direction: Literal["long", "short"] = (
            "long" if self.state.bias == "bullish" else "short"
        )
        if self.state.state == SetupState.AWAITING_SWEEP:
            if (
                liquidity_target is None
                or liquidity_target.direction != direction
                or sweep_level is None
                or sweep_level_type is None
            ):
                return None
            sweep = detect_sweep(
                [candle],
                level=sweep_level,
                level_type=sweep_level_type,
                direction=direction,
            )
            if sweep is None or not self._is_entry_zone(sweep.extreme_price, direction):
                return None

            self.state.target_liquidity_level = liquidity_target.level
            self.state.target_liquidity_type = liquidity_target.level_type
            self.state.sweep_time = sweep.timestamp
            self.state.sweep_extreme_price = sweep.extreme_price
            self.state.sweep_level_type = sweep.level_type
            self.state.sweep_candle_index = bar_index
            self.state.displacement_swing_price = sweep.extreme_price
            self.state.killzone_label = self._killzone_label(candle.timestamp)
            self.state.sweep_in_killzone = self.state.killzone_label is not None
            self.state.state = SetupState.SWEPT_AWAITING_MSS
            return None

        if self.state.state == SetupState.SWEPT_AWAITING_MSS:
            if self._sweep_invalidated(candle, direction):
                self._reset_to_awaiting_sweep(candle.timestamp)
                return None

            self._extend_displacement_swing(candle, direction)

            if counter_trend_swing is None or len(ordered) < 16:
                return None

            mss = confirm_mss(
                ordered,
                counter_trend_swing=counter_trend_swing,
                direction=direction,
                timeframe=timeframe,
                m5_confirmed=m5_confirmed,
            )

            if mss is None:
                return None

            self.state.mss_time = mss.timestamp
            self.state.mss_candle_index = bar_index
            self.state.mss_displacement_atr_multiple = mss.displacement_atr_multiple
            self.state.pre_mss_candle = ordered[-2]
            self.state.mss_candle = ordered[-1]
            self.state.mss_order_block_candle = next(
                (
                    item
                    for item in reversed(ordered[:-1])
                    if (item.close < item.open if direction == "long" else item.close > item.open)
                ),
                None,
            )
            self.state.state = SetupState.MSS_CONFIRMED_AWAITING_FVG
            return None

        if self.state.state == SetupState.MSS_CONFIRMED_AWAITING_FVG:
            if self.state.mss_time is None:
                self.reset(ny_date)
                self.state.last_processed_candle_time = candle.timestamp
                return None
            if self.state.pre_mss_candle is None or self.state.mss_candle is None:
                return None
            try:
                imbalance = _extract_imbalance_values(
                    first=self.state.pre_mss_candle,
                    third=candle,
                    opposing=self.state.mss_order_block_candle,
                    direction=direction,
                )
            except ValueError:
                return None

            self.state.fvg_high = imbalance.fvg_high
            self.state.fvg_low = imbalance.fvg_low
            self.state.fvg_ce = imbalance.fvg_ce
            self.state.ob_high = imbalance.ob_high
            self.state.ob_low = imbalance.ob_low
            self.state.imbalance_kind = imbalance.kind
            self.state.state = SetupState.AWAITING_RETRACEMENT
            return None

        if self.state.state == SetupState.AWAITING_RETRACEMENT:
            boundary = self.state.fvg_ce
            if boundary is None:
                boundary = self.state.ob_high if direction == "long" else self.state.ob_low

            if boundary is None:
                self.reset(ny_date)
                self.state.last_processed_candle_time = candle.timestamp
                return None

            if not (
                candle.low <= boundary <= candle.high
                and self._closes_with_bias(candle, direction)
            ):
                return None

            setup = self._build_setup(candle, direction, boundary)

            if setup is None:
                self.reset(ny_date)
                self.state.last_processed_candle_time = candle.timestamp
                return None

            self.state.state = SetupState.SETUP_READY
            return setup
        return None

    def _is_entry_zone(self, price: float, direction: Literal["long", "short"]) -> bool:
        if self.state.range_mid is None:
            return False
        return price <= self.state.range_mid if direction == "long" else price >= self.state.range_mid

    def _sweep_invalidated(
        self, candle: ClosedCandle, direction: Literal["long", "short"]
    ) -> bool:
        extreme = self.state.sweep_extreme_price
        if extreme is None:
            return True
        return candle.close < extreme if direction == "long" else candle.close > extreme

    def _extend_displacement_swing(
        self, candle: ClosedCandle, direction: Literal["long", "short"]
    ) -> None:
        anchor = self.state.displacement_swing_price
        if anchor is None:
            return
        self.state.displacement_swing_price = (
            min(anchor, candle.low) if direction == "long" else max(anchor, candle.high)
        )

    def _reset_to_awaiting_sweep(self, timestamp: datetime) -> None:
        if (
            self.state.trading_date_ny is None
            or self.state.bias is None
            or self.state.range_high is None
            or self.state.range_low is None
            or self.state.range_mid is None
        ):
            self.reset(timestamp.astimezone(NY_TZ).date())
            self.state.last_processed_candle_time = timestamp
            return
        self.state = EURUSDModelState(
            state=SetupState.AWAITING_SWEEP,
            trading_date_ny=self.state.trading_date_ny,
            bias=self.state.bias,
            bias_swing_count=self.state.bias_swing_count,
            range_high=self.state.range_high,
            range_low=self.state.range_low,
            range_mid=self.state.range_mid,
            last_processed_candle_time=timestamp,
            processed_bar_count=self.state.processed_bar_count,
        )

    @staticmethod
    def _closes_with_bias(candle: ClosedCandle, direction: Literal["long", "short"]) -> bool:
        return candle.close > candle.open if direction == "long" else candle.close < candle.open

    @classmethod
    def _killzone_label(cls, timestamp: datetime) -> str | None:
        london_start, london_end = ny_killzone_window_utc(timestamp, *cls._LONDON_KILLZONE)
        if london_start <= timestamp < london_end:
            return "london"
        ny_am_start, ny_am_end = ny_killzone_window_utc(timestamp, *cls._NY_AM_KILLZONE)
        if ny_am_start <= timestamp < ny_am_end:
            return "ny_am"
        return None

    def _build_setup(
        self,
        candle: ClosedCandle,
        direction: Literal["long", "short"],
        entry_price: float,
    ) -> Setup | None:
        if (
            self.state.range_high is None
            or self.state.range_low is None
            or self.state.range_mid is None
            or self.state.target_liquidity_level is None
            or self.state.target_liquidity_type is None
            or self.state.sweep_time is None
            or self.state.sweep_extreme_price is None
            or self.state.sweep_level_type is None
            or self.state.sweep_candle_index is None
            or self.state.mss_time is None
            or self.state.mss_candle_index is None
            or self.state.mss_displacement_atr_multiple is None
            or self.state.displacement_swing_price is None
            or self.state.imbalance_kind is None
            or self.state.bias is None
        ):
            return None

        stop = (
            self.state.displacement_swing_price - self._STOP_OFFSET
            if direction == "long"
            else self.state.displacement_swing_price + self._STOP_OFFSET
        )
        if abs(entry_price - stop) > self._MAX_STOP_DISTANCE:
            return None
        prices_are_ordered = (
            stop < entry_price < self.state.target_liquidity_level
            if direction == "long"
            else self.state.target_liquidity_level < entry_price < stop
        )
        if not prices_are_ordered:
            return None
        return Setup(
            timestamp=candle.timestamp,
            direction=direction,
            bias=self.state.bias,
            bias_swing_count=self.state.bias_swing_count,
            range_high=self.state.range_high,
            range_low=self.state.range_low,
            range_mid=self.state.range_mid,
            entry_zone="discount" if direction == "long" else "premium",
            target_liquidity_level=self.state.target_liquidity_level,
            target_liquidity_type=self.state.target_liquidity_type,
            sweep_time=self.state.sweep_time,
            sweep_extreme_price=self.state.sweep_extreme_price,
            sweep_level_type=self.state.sweep_level_type,
            sweep_in_killzone=self.state.sweep_in_killzone,
            killzone_label=self.state.killzone_label,
            mss_time=self.state.mss_time,
            mss_candle_index=self.state.mss_candle_index,
            sweep_candle_index=self.state.sweep_candle_index,
            mss_displacement_atr_multiple=self.state.mss_displacement_atr_multiple,
            fvg_high=self.state.fvg_high,
            fvg_low=self.state.fvg_low,
            fvg_ce=self.state.fvg_ce,
            ob_high=self.state.ob_high,
            ob_low=self.state.ob_low,
            extract_fvg_and_order_block=self.state.imbalance_kind,
            entry_price=entry_price,
            stop_price=stop,
            target_price=self.state.target_liquidity_level,
        )


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
