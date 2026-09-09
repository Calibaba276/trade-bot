from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.strategies.setup_filter import (
    FilterCheckResult,
    FilterContext,
    FilterResult,
    Setup,
)


def make_setup(**overrides: object) -> Setup:
    values: dict[str, object] = {
        "timestamp": datetime(2026, 1, 5, 12, tzinfo=timezone.utc),
        "direction": "long",
        "bias": "bullish",
        "bias_swing_count": 2,
        "range_high": 1.1,
        "range_low": 1.09,
        "range_mid": 1.095,
        "entry_zone": "discount",
        "target_liquidity_level": 1.11,
        "target_liquidity_type": "prev_day_high",
        "sweep_time": datetime(2026, 1, 5, 10, tzinfo=timezone.utc),
        "sweep_extreme_price": 1.088,
        "sweep_level_type": "prev_day_low",
        "sweep_in_killzone": True,
        "killzone_label": "london",
        "mss_time": datetime(2026, 1, 5, 10, 15, tzinfo=timezone.utc),
        "mss_candle_index": 15,
        "sweep_candle_index": 10,
        "mss_displacement_atr_multiple": 1.8,
        "fvg_high": 1.096,
        "fvg_low": 1.095,
        "fvg_ce": 1.0955,
        "ob_high": 1.094,
        "ob_low": 1.093,
        "extract_fvg_and_order_block": "both",
        "entry_price": 1.0955,
        "stop_price": 1.092,
        "target_price": 1.11,
    }
    values.update(overrides)
    return Setup.model_validate(values)


def test_setup_is_immutable_and_serializable() -> None:
    setup = make_setup()

    with pytest.raises(ValidationError):
        setup.entry_price = 1.096  # type: ignore[misc]

    assert setup.model_dump()["instrument"] == "EURUSD"


@pytest.mark.parametrize(
    "field",
    ["timestamp", "sweep_time", "mss_time"],
)
def test_setup_rejects_non_utc_timestamp(field: str) -> None:
    with pytest.raises(ValidationError):
        make_setup(**{field: datetime(2026, 1, 5, 12)})


def test_filter_result_validates_nested_contracts() -> None:
    setup = make_setup()
    check = FilterCheckResult(
        check_name="check_confluence",
        passed=True,
        score=1.0,
        weight=1.0,
        reason="2/3 independent categories met",
    )
    result = FilterResult(
        setup=setup,
        passed=True,
        composite_score=1.0,
        checks=[check],
    )

    assert result.setup is setup
    assert result.checks[0].check_name == "check_confluence"


def test_filter_context_rejects_naive_last_setup_time() -> None:
    with pytest.raises(ValidationError):
        FilterContext(last_setup_time=datetime(2026, 1, 5, 12))
