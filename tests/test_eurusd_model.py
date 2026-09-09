from datetime import datetime, time, timezone

import pytest
from pydantic import ValidationError

from backend.strategies.eurusd_model import (
    ClosedCandle,
    Setup,
    ny_killzone_window_utc,
    ny_midnight_range_window_utc,
    to_wat_for_display,
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
