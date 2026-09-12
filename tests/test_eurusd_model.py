from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

import pytest
from pydantic import ValidationError

from backend.strategies.eurusd_model import (
    BiasEvidence,
    ClosedCandle,
    EURUSDModel,
    EURUSDModelState,
    LiquidityTarget,
    RangeLevels,
    Setup,
    SetupState,
    build_ranges,
    confirm_mss,
    detect_sweep,
    determine_bias,
    extract_imbalances,
    ny_killzone_window_utc,
    ny_midnight_range_window_utc,
    select_liquidity_target,
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
    impulse = candles[-2].model_copy(update={"open": 1.101, "close": 1.106, "high": 1.1062, "low": 1.103})
    confirmation = candles[-1].model_copy(update={"open": 1.105, "close": 1.1055, "high": 1.106, "low": 1.104})
    result = extract_imbalances(candles[:-2] + [impulse, confirmation], mss_index=len(candles) - 2, direction="long")
    assert result.kind in {"fvg_only", "both"}


def test_bias_is_unknown_for_chop() -> None:
    assert determine_bias(_candles(7)).bias is None


def test_state_machine_emits_one_fvg_setup_and_ignores_duplicate_bar() -> None:
    model = EURUSDModel()
    ranges = RangeLevels(midnight_high=1.11, midnight_low=1.10, midnight_mid=1.105)
    target = LiquidityTarget(level=1.115, level_type="pdh", direction="long")
    candles = _candles(16)
    sweep = candles[-1].model_copy(
        update={"open": 1.1042, "high": 1.1046, "low": 1.1035, "close": 1.1045}
    )
    candles[-1] = sweep
    assert model.process_closed_candles(
        candles,
        bias_evidence=BiasEvidence(bias="bullish", swing_count=2),
        ranges=ranges,
        liquidity_target=target,
        sweep_level=1.104,
        sweep_level_type="asian_low",
        counter_trend_swing=1.105,
    ) is None
    assert model.state.state == SetupState.SWEPT_AWAITING_MSS

    impulse = sweep.model_copy(
        update={
            "timestamp": sweep.timestamp + timedelta(minutes=5),
            "open": 1.1049,
            "high": 1.1101,
            "low": 1.1048,
            "close": 1.1100,
        }
    )
    candles.append(impulse)
    assert model.process_closed_candles(candles, bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=1.105) is None
    assert model.state.state == SetupState.MSS_CONFIRMED_AWAITING_FVG

    fvg_extraction_bar = impulse.model_copy(
        update={"timestamp": impulse.timestamp + timedelta(minutes=5), "open": 1.105, "high": 1.1092, "low": 1.105, "close": 1.1085}
    )
    candles.append(fvg_extraction_bar)
    assert model.process_closed_candles([fvg_extraction_bar], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None
    assert model.state.state == SetupState.AWAITING_RETRACEMENT

    touch = fvg_extraction_bar.model_copy(
        update={"timestamp": fvg_extraction_bar.timestamp + timedelta(minutes=5), "open": 1.1048, "high": 1.1055, "low": 1.1047, "close": 1.1052}
    )
    candles.append(touch)
    setup = model.process_closed_candles(candles, bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None)
    assert setup is not None
    assert setup.extract_fvg_and_order_block in {"fvg_only", "both"}
    assert setup.stop_price == pytest.approx(model.state.displacement_swing_price - 0.0003)
    assert model.process_closed_candles(candles, bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None


def test_state_machine_resets_an_invalidated_sweep() -> None:
    model = EURUSDModel()
    model.state = EURUSDModelState(
        state=SetupState.SWEPT_AWAITING_MSS,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        sweep_extreme_price=1.10,
    )
    candle = ClosedCandle(
        timestamp=datetime(2026, 6, 1, 12, tzinfo=UTC),
        open=1.10,
        high=1.101,
        low=1.098,
        close=1.099,
    )
    assert model.process_closed_candles([candle], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None
    assert model.state.state == SetupState.AWAITING_BIAS


def test_sweep_invalidation_preserves_the_confirmed_daily_context() -> None:
    model = EURUSDModel()
    model.state = EURUSDModelState(
        state=SetupState.SWEPT_AWAITING_MSS,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        bias_swing_count=2,
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        sweep_extreme_price=1.10,
    )
    invalidation = ClosedCandle(
        timestamp=datetime(2026, 6, 1, 12, tzinfo=UTC),
        open=1.10,
        high=1.101,
        low=1.098,
        close=1.099,
    )
    model.process_closed_candles([invalidation], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None)
    assert model.state.state == SetupState.AWAITING_SWEEP
    assert model.state.range_mid == 1.105


def test_state_machine_ignores_stale_bars_without_rewinding() -> None:
    model = EURUSDModel()
    latest = datetime(2026, 6, 2, 12, tzinfo=UTC)
    model.state = EURUSDModelState(
        state=SetupState.AWAITING_SWEEP,
        trading_date_ny=date(2026, 6, 2),
        bias="bullish",
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        last_processed_candle_time=latest,
    )
    stale = ClosedCandle(timestamp=latest - timedelta(minutes=5), open=1.1, high=1.101, low=1.099, close=1.1)
    assert model.process_closed_candles([stale], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None
    assert model.state.trading_date_ny == date(2026, 6, 2)
    assert model.state.last_processed_candle_time == latest


def test_state_machine_uses_stable_indexes_with_a_rolling_window() -> None:
    model = EURUSDModel()
    ranges = RangeLevels(midnight_high=1.11, midnight_low=1.10, midnight_mid=1.105)
    target = LiquidityTarget(level=1.115, level_type="pdh", direction="long")
    candles = _candles(20)
    sweep = candles[-1].model_copy(
        update={"open": 1.1042, "high": 1.1046, "low": 1.1035, "close": 1.1045}
    )
    candles[-1] = sweep
    model.process_closed_candles(candles, bias_evidence=BiasEvidence(bias="bullish", swing_count=2), ranges=ranges, liquidity_target=target, sweep_level=1.104, sweep_level_type="asian_low", counter_trend_swing=1.105)
    impulse = sweep.model_copy(update={"timestamp": sweep.timestamp + timedelta(minutes=5), "open": 1.1049, "high": 1.1101, "low": 1.1048, "close": 1.1100})
    rolling_window = candles[-15:] + [impulse]
    assert model.process_closed_candles(rolling_window, bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=1.105) is None
    assert model.state.state == SetupState.MSS_CONFIRMED_AWAITING_FVG
    assert model.state.sweep_candle_index == 0
    assert model.state.mss_candle_index == 1


def test_state_machine_fails_closed_when_m5_bars_are_skipped() -> None:
    model = EURUSDModel()
    latest = datetime(2026, 6, 1, 12, tzinfo=UTC)
    model.state = EURUSDModelState(
        state=SetupState.AWAITING_SWEEP,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        last_processed_candle_time=latest,
    )
    after_gap = ClosedCandle(timestamp=latest + timedelta(minutes=10), open=1.1, high=1.101, low=1.099, close=1.1)
    assert model.process_closed_candles([after_gap], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None
    assert model.state.state == SetupState.AWAITING_BIAS


@pytest.mark.parametrize(("timeframe", "minutes"), [("M3", 3), ("M1", 1)])
def test_state_machine_accepts_refinement_timeframe_interval(
    timeframe: Literal["M3", "M1"], minutes: int
) -> None:
    model = EURUSDModel()
    latest = datetime(2026, 6, 1, 12, tzinfo=UTC)
    model.state = EURUSDModelState(
        state=SetupState.AWAITING_SWEEP,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        last_processed_candle_time=latest,
    )
    next_bar = ClosedCandle(
        timestamp=latest + timedelta(minutes=minutes),
        open=1.1,
        high=1.101,
        low=1.099,
        close=1.1,
    )
    model.process_closed_candles(
        [next_bar],
        bias_evidence=None,
        ranges=None,
        liquidity_target=None,
        sweep_level=None,
        sweep_level_type=None,
        counter_trend_swing=None,
        timeframe=timeframe,
    )
    assert model.state.state == SetupState.AWAITING_SWEEP
    assert model.state.last_processed_candle_time == next_bar.timestamp


def test_state_machine_rejects_target_on_the_wrong_side_of_entry() -> None:
    timestamp = datetime(2026, 6, 1, 12, tzinfo=UTC)
    model = EURUSDModel()
    model.state = EURUSDModelState(
        state=SetupState.AWAITING_RETRACEMENT,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        target_liquidity_level=1.103,
        target_liquidity_type="invalid_target",
        sweep_time=timestamp,
        sweep_extreme_price=1.1035,
        sweep_level_type="asian_low",
        sweep_candle_index=0,
        mss_time=timestamp,
        mss_candle_index=1,
        mss_displacement_atr_multiple=1.6,
        displacement_swing_price=1.1035,
        ob_high=1.104,
        ob_low=1.103,
        imbalance_kind="ob_only",
    )
    trigger = ClosedCandle(timestamp=timestamp + timedelta(minutes=5), open=1.1039, high=1.105, low=1.1038, close=1.1045)
    assert model.process_closed_candles([trigger], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None) is None
    assert model.state.state == SetupState.AWAITING_BIAS


def test_state_machine_uses_order_block_boundary_only_without_fvg() -> None:
    timestamp = datetime(2026, 6, 1, 12, tzinfo=UTC)
    model = EURUSDModel()
    model.state = EURUSDModelState(
        state=SetupState.AWAITING_RETRACEMENT,
        trading_date_ny=date(2026, 6, 1),
        bias="bullish",
        bias_swing_count=2,
        range_high=1.11,
        range_low=1.10,
        range_mid=1.105,
        target_liquidity_level=1.115,
        target_liquidity_type="pdh",
        sweep_time=timestamp,
        sweep_extreme_price=1.1035,
        sweep_level_type="asian_low",
        sweep_candle_index=1,
        mss_time=timestamp,
        mss_candle_index=2,
        mss_displacement_atr_multiple=1.6,
        displacement_swing_price=1.1035,
        ob_high=1.104,
        ob_low=1.103,
        imbalance_kind="ob_only",
    )
    touch = ClosedCandle(
        timestamp=timestamp + timedelta(minutes=5),
        open=1.1039,
        high=1.1052,
        low=1.1038,
        close=1.1045,
    )
    setup = model.process_closed_candles([touch], bias_evidence=None, ranges=None, liquidity_target=None, sweep_level=None, sweep_level_type=None, counter_trend_swing=None)
    assert setup is not None
    assert setup.entry_price == 1.104
    assert setup.extract_fvg_and_order_block == "ob_only"
