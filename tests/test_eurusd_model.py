from datetime import datetime, timedelta, time, timezone

import pytest
from pydantic import ValidationError

from backend.strategies.eurusd_model import (
    ClosedCandle,
    Setup,
    ny_killzone_window_utc,
    ny_midnight_range_window_utc,
    to_wat_for_display,
    build_ranges,
    confirm_mss,
    detect_sweep,
    determine_bias,
    extract_imbalances,
    select_liquidity_target,
)

UTC = timezone.utc


def _setup() -> Setup:
    timestamp = datetime(2026, 6, 1, 12, tzinfo=UTC)
    return Setup(
        timestamp=timestamp,
        direction="long",
        bias="bullish",
        bias_swing_count=2,
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        entry_zone="discount",
        target_liquidity_level=1.12,
        target_liquidity_type="prev_day_high",
        sweep_time=timestamp,
        sweep_extreme_price=1.099,
        sweep_level_type="range_low",
        sweep_in_killzone=True,
        mss_time=timestamp,
        mss_candle_index=3,
        sweep_candle_index=1,
        mss_displacement_atr_multiple=1.5,
        extract_fvg_and_order_block="both",
        entry_price=1.101,
        stop_price=1.099,
        target_price=1.107,
    )


def test_setup_rejects_naive_timestamp() -> None:
    values = _setup().model_dump()
    values["timestamp"] = datetime.fromisoformat("2026-06-01T12:00:00")
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        Setup.model_validate(values)


def test_closed_candle_rejects_non_utc_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        ClosedCandle(
            timestamp=datetime.fromisoformat("2026-06-01T12:00:00"),
            open=1.0,
            high=1.1,
            low=0.9,
            close=1.0,
        )


def test_setup_is_immutable() -> None:
    setup = _setup()
    with pytest.raises(ValidationError):
        setup.entry_price = 1.102  # type: ignore[misc]


@pytest.mark.parametrize(
    ("reference", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 6, 1, 12, tzinfo=UTC),
            "2026-06-01T12:00:00+00:00",
            "2026-06-01T15:00:00+00:00",
        ),
        (
            datetime(2026, 1, 15, 13, tzinfo=UTC),
            "2026-01-15T13:00:00+00:00",
            "2026-01-15T16:00:00+00:00",
        ),
    ],
)
def test_ny_killzone_converts_dst(
    reference: datetime, expected_start: str, expected_end: str
) -> None:
    start, end = ny_killzone_window_utc(reference, time(8), time(11))
    assert start.isoformat() == expected_start
    assert end.isoformat() == expected_end


@pytest.mark.parametrize(
    ("reference", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 6, 1, 12, tzinfo=UTC),
            "2026-06-01T04:00:00+00:00",
            "2026-06-01T07:00:00+00:00",
        ),
        (
            datetime(2026, 1, 15, 13, tzinfo=UTC),
            "2026-01-15T05:00:00+00:00",
            "2026-01-15T08:00:00+00:00",
        ),
    ],
)
def test_ny_midnight_range_is_dst_aware(
    reference: datetime, expected_start: str, expected_end: str
) -> None:
    start, end = ny_midnight_range_window_utc(reference)
    assert start.isoformat() == expected_start
    assert end.isoformat() == expected_end


def test_wat_display_conversion() -> None:
    assert to_wat_for_display(datetime(2026, 6, 1, 4, tzinfo=UTC)).isoformat() == (
        "2026-06-01T05:00:00+01:00"
    )


def _candles(count: int = 20) -> list[ClosedCandle]:
    start = datetime(2026, 6, 1, tzinfo=UTC)
    return [ClosedCandle(timestamp=start + timedelta(minutes=5 * i), open=1.1000 + i * 0.0001, high=1.1010 + i * 0.0001, low=1.0990 + i * 0.0001, close=1.1005 + i * 0.0001) for i in range(count)]


def test_sweep_requires_close_back_inside_level() -> None:
    candles = _candles(1)
    candle = candles[0].model_copy(update={"low": 1.098, "close": 1.100})
    assert detect_sweep([candle], level=1.099, level_type="range_low", direction="long") is not None
    breakout = candle.model_copy(update={"close": 1.0985})
    assert detect_sweep([breakout], level=1.099, level_type="range_low", direction="long") is None


def test_mss_requires_primary_m5_and_displacement() -> None:
    candles = _candles()
    impulse = candles[-1].model_copy(update={"open": 1.101, "close": 1.106, "high": 1.1062, "low": 1.1009})
    assert confirm_mss(candles[:-1] + [impulse], counter_trend_swing=1.102, direction="long") is not None
    assert confirm_mss(candles[:-1] + [impulse], counter_trend_swing=1.102, direction="long", timeframe="M1", m5_confirmed=False) is None
    assert confirm_mss(candles[:-1] + [impulse], counter_trend_swing=1.102, direction="long", timeframe="M1") is None
    assert confirm_mss(candles[:-1] + [impulse], counter_trend_swing=1.102, direction="long", timeframe="M1", m5_confirmed=True) is not None


def test_mss_evaluates_only_the_latest_closed_candle() -> None:
    candles = _candles()
    earlier_impulse = candles[-2].model_copy(
        update={"open": 1.101, "close": 1.106, "high": 1.1062, "low": 1.1009}
    )
    latest_non_confirmation = candles[-1].model_copy(
        update={"open": 1.101, "close": 1.1012, "high": 1.1014, "low": 1.1008}
    )
    assert (
        confirm_mss(
            candles[:-2] + [earlier_impulse, latest_non_confirmation],
            counter_trend_swing=1.102,
            direction="long",
        )
        is None
    )


def test_liquidity_priority_and_range_split() -> None:
    target = select_liquidity_target(direction="long", previous_day_high=1.12, asian_high=1.115, opposite_range_side=1.11)
    assert target.level_type == "pdh"
    midnight_candles = [
        candle.model_copy(update={"timestamp": candle.timestamp + timedelta(hours=4)})
        for candle in _candles(36)
    ]
    ranges = build_ranges(midnight_candles, datetime(2026, 6, 1, 12, tzinfo=UTC))
    assert ranges.midnight_high >= ranges.midnight_low


def test_range_rejects_incomplete_midnight_data() -> None:
    partial = [
        candle.model_copy(update={"timestamp": candle.timestamp + timedelta(hours=4)})
        for candle in _candles(20)
    ]
    with pytest.raises(ValueError, match="complete candle coverage"):
        build_ranges(partial, datetime(2026, 6, 1, 12, tzinfo=UTC))


def test_imbalance_extracts_fvg_and_order_block_without_future_candles() -> None:
    candles = _candles()
    impulse = candles[-1].model_copy(update={"open": 1.101, "close": 1.106, "high": 1.1062, "low": 1.103})
    result = extract_imbalances(candles[:-1] + [impulse], mss_index=len(candles) - 1, direction="long")
    assert result.kind in {"fvg_only", "both"}


def test_bias_is_unknown_for_chop() -> None:
    assert determine_bias(_candles(7)).bias is None
