from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.strategies.eurusd_model import Setup
from backend.strategies.setup_filter import (
    AuditClient,
    ConfigurableCheckName,
    FilterConfig,
    FilterContext,
    SessionSafetyContext,
    check_amd_timing,
    check_bias_quality,
    check_confluence,
    check_liquidity_target,
    evaluate,
    log_filter_result,
    setup_evaluation_key,
    setup_narrative_key,
)

UTC = timezone.utc
ACCOUNT_ID = "8c505d14-f0a1-4a96-9875-a46084d39191"
SECOND_ACCOUNT_ID = "97d73960-548a-4077-aa87-eb567654a30b"


def _setup(**updates: object) -> Setup:
    sweep_time = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "timestamp": sweep_time + timedelta(minutes=15),
        "direction": "long",
        "bias": "bullish",
        "bias_swing_count": 3,
        "range_high": 1.1100,
        "range_low": 1.1000,
        "range_mid": 1.1050,
        "entry_zone": "discount",
        "target_liquidity_level": 1.1120,
        "target_liquidity_type": "pdh",
        "sweep_time": sweep_time,
        "sweep_extreme_price": 1.1020,
        "sweep_level_type": "asian_low",
        "sweep_in_killzone": True,
        "killzone_label": "ny_am",
        "mss_time": sweep_time + timedelta(minutes=5),
        "mss_candle_index": 11,
        "sweep_candle_index": 10,
        "mss_displacement_atr_multiple": 1.8,
        "fvg_high": 1.1060,
        "fvg_low": 1.1040,
        "fvg_ce": 1.1050,
        "ob_high": 1.1045,
        "ob_low": 1.1035,
        "extract_fvg_and_order_block": "both",
        "entry_price": 1.1050,
        "stop_price": 1.1020,
        "target_price": 1.1140,
    }
    values.update(updates)
    return Setup.model_validate(values)


def _safe_session(**updates: object) -> SessionSafetyContext:
    values: dict[str, object] = {
        "is_resolved": True,
        "is_bank_holiday": False,
        "is_nfp_release_day": False,
        "is_fomc_decision_afternoon": False,
        "has_draw_on_liquidity": True,
        "is_adr_exhausted": False,
        "has_clear_dxy_conflict": False,
    }
    values.update(updates)
    return SessionSafetyContext.model_validate(values)


def _context(**updates: object) -> FilterContext:
    values: dict[str, object] = {
        "strategy_state_is_resolved": True,
        "accepted_setups_today": 0,
        "accepted_setup_killzones": (),
        "accepted_narrative_keys": frozenset(),
        "evaluated_setup_keys": frozenset(),
        "session_safety": _safe_session(),
    }
    values.update(updates)
    return FilterContext.model_validate(values)


def test_valid_setup_passes_all_hard_gates() -> None:
    result = evaluate(
        _setup(),
        _context(),
        FilterConfig(),
    )

    assert result.passed is True
    assert result.rejected_by is None
    assert [check.check_name for check in result.checks] == [
        "check_session_safety",
        "check_selectivity",
        "check_confluence",
        "check_bias_quality",
        "check_liquidity_target",
        "check_amd_timing",
    ]


def test_unresolved_session_safety_fails_closed() -> None:
    result = evaluate(
        _setup(),
        FilterContext(),
        FilterConfig(),
    )

    assert result.rejected_by == "check_session_safety"
    assert "unresolved" in result.checks[0].reason


def test_unresolved_strategy_state_fails_closed() -> None:
    result = evaluate(
        _setup(),
        FilterContext(session_safety=_safe_session()),
        FilterConfig(),
    )

    assert result.rejected_by == "check_selectivity"
    assert "Strategy" in result.checks[-1].reason
    assert "unresolved" in result.checks[-1].reason


def test_resolved_contexts_require_complete_source_data() -> None:
    with pytest.raises(ValidationError, match="session safety context"):
        SessionSafetyContext(is_resolved=True)

    with pytest.raises(ValidationError, match="strategy filter context"):
        FilterContext(
            strategy_state_is_resolved=True,
            session_safety=_safe_session(),
        )


@pytest.mark.parametrize(
    ("safety_update", "reason"),
    [
        ({"is_bank_holiday": True}, "Bank-holiday"),
        ({"is_nfp_release_day": True}, "NFP release day"),
        ({"is_fomc_decision_afternoon": True}, "FOMC"),
        ({"has_draw_on_liquidity": False}, "No valid draw"),
        ({"is_adr_exhausted": True}, "range is exhausted"),
        ({"has_clear_dxy_conflict": True}, "DXY"),
    ],
)
def test_session_safety_failures_stop_evaluation(
    safety_update: dict[str, bool],
    reason: str,
) -> None:
    safety = _safe_session(**safety_update)
    result = evaluate(
        _setup(),
        _context(session_safety=safety),
        FilterConfig(),
    )

    assert result.passed is False
    assert result.rejected_by == "check_session_safety"
    assert len(result.checks) == 1
    assert reason in result.checks[0].reason


def test_invalid_setup_chronology_fails_session_safety() -> None:
    sweep_time = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    setup = _setup(mss_time=sweep_time - timedelta(minutes=5))

    result = evaluate(
        setup,
        _context(),
        FilterConfig(),
    )

    assert result.rejected_by == "check_session_safety"
    assert "chronologically valid" in result.checks[0].reason


def test_four_rejections_do_not_block_the_fifth_candidate_in_a_killzone() -> None:
    base = _setup()
    rejected_candidates: list[Setup] = []

    for offset in range(4):
        candidate = _setup(
            timestamp=base.timestamp + timedelta(minutes=offset * 2),
            sweep_time=base.sweep_time + timedelta(minutes=offset * 2),
            mss_time=base.mss_time + timedelta(minutes=offset * 2),
            sweep_extreme_price=1.1020 - offset * 0.0001,
            mss_displacement_atr_multiple=1.0,
            sweep_level_type="m15_equal_level",
        )
        context = _context(
            evaluated_setup_keys=frozenset(
                setup_evaluation_key(previous) for previous in rejected_candidates
            ),
        )
        result = evaluate(
            candidate,
            context,
            FilterConfig(),
        )

        assert result.rejected_by == "check_confluence"
        rejected_candidates.append(candidate)

    winning_candidate = _setup(
        timestamp=base.timestamp + timedelta(minutes=10),
        sweep_time=base.sweep_time + timedelta(minutes=10),
        mss_time=base.mss_time + timedelta(minutes=10),
        sweep_extreme_price=1.1015,
    )
    winning_result = evaluate(
        winning_candidate,
        _context(
            evaluated_setup_keys=frozenset(
                setup_evaluation_key(candidate) for candidate in rejected_candidates
            ),
        ),
        FilterConfig(),
    )

    assert winning_result.passed is True


def test_accepted_setup_consumes_only_its_killzone_quota() -> None:
    london_candidate = _setup(
        killzone_label="london",
        sweep_time=datetime(2026, 6, 1, 7, 0, tzinfo=UTC),
        mss_time=datetime(2026, 6, 1, 7, 5, tzinfo=UTC),
        timestamp=datetime(2026, 6, 1, 7, 10, tzinfo=UTC),
    )
    context = _context(accepted_setup_killzones=("london",))

    london_result = evaluate(
        london_candidate,
        context,
        FilterConfig(),
    )
    ny_result = evaluate(
        _setup(),
        context,
        FilterConfig(),
    )

    assert london_result.rejected_by == "check_selectivity"
    assert ny_result.passed is True


def test_daily_accepted_setup_cap_is_a_hard_gate() -> None:
    result = evaluate(
        _setup(),
        _context(accepted_setups_today=2),
        FilterConfig(),
    )

    assert result.rejected_by == "check_selectivity"
    assert "Daily accepted-setup cap" in result.checks[-1].reason


def test_exact_candidate_and_accepted_narrative_are_deduplicated() -> None:
    setup = _setup()
    exact_duplicate = evaluate(
        setup,
        _context(
            evaluated_setup_keys=frozenset({setup_evaluation_key(setup)}),
        ),
        FilterConfig(),
    )
    narrative_duplicate = evaluate(
        setup.model_copy(update={"timestamp": setup.timestamp + timedelta(minutes=5)}),
        _context(
            accepted_narrative_keys=frozenset({setup_narrative_key(setup)}),
        ),
        FilterConfig(),
    )

    assert exact_duplicate.rejected_by == "check_selectivity"
    assert "already evaluated" in exact_duplicate.checks[-1].reason
    assert narrative_duplicate.rejected_by == "check_selectivity"
    assert "already has an accepted setup" in narrative_duplicate.checks[-1].reason


def test_confluence_counts_only_three_independent_categories() -> None:
    result = check_confluence(
        _setup(
            mss_displacement_atr_multiple=1.0,
            sweep_level_type="m15_equal_level",
        ),
        _context(),
        FilterConfig(),
    )

    assert result.passed is False
    assert result.score == pytest.approx(1 / 3)
    assert "timing" in result.reason


def test_bias_quality_and_amd_timing_remain_soft_scores() -> None:
    setup = _setup(
        bias_swing_count=0,
        mss_candle_index=20,
        sweep_candle_index=10,
    )

    bias = check_bias_quality(
        setup,
        _context(),
        FilterConfig(),
    )
    amd = check_amd_timing(
        setup,
        _context(),
        FilterConfig(),
    )
    result = evaluate(
        setup,
        _context(),
        FilterConfig(),
    )

    assert bias.passed is False
    assert bias.score == 0.0
    assert amd.passed is True
    assert amd.score == 0.3
    assert result.passed is True


def test_bias_quality_can_be_promoted_to_a_hard_gate() -> None:
    hard_gates: frozenset[ConfigurableCheckName] = frozenset(
        {
            "check_selectivity",
            "check_confluence",
            "check_liquidity_target",
            "check_bias_quality",
        }
    )
    result = evaluate(
        _setup(bias_swing_count=0),
        _context(),
        FilterConfig(hard_gate_checks=hard_gates),
    )

    assert result.rejected_by == "check_bias_quality"


def test_amd_timing_can_be_promoted_to_a_hard_gate() -> None:
    hard_gates: frozenset[ConfigurableCheckName] = frozenset(
        {
            "check_selectivity",
            "check_confluence",
            "check_liquidity_target",
            "check_amd_timing",
        }
    )
    result = evaluate(
        _setup(
            sweep_in_killzone=False,
            killzone_label=None,
        ),
        _context(),
        FilterConfig(hard_gate_checks=hard_gates),
    )

    assert result.rejected_by == "check_amd_timing"


def test_reward_to_risk_is_a_directional_hard_gate() -> None:
    low_reward = check_liquidity_target(
        _setup(target_price=1.1100),
        _context(),
        FilterConfig(),
    )
    invalid_order = check_liquidity_target(
        _setup(stop_price=1.1060),
        _context(),
        FilterConfig(),
    )

    assert low_reward.passed is False
    assert "R:R = 1.67" in low_reward.reason
    assert invalid_order.passed is False
    assert invalid_order.score == 0.0


def test_invalid_filter_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must remain hard gates"):
        FilterConfig(hard_gate_checks=frozenset({"check_confluence"}))

    with pytest.raises(ValidationError, match="at least min_reward_risk_ratio"):
        FilterConfig(
            min_reward_risk_ratio=4.0,
            target_reward_risk_ratio=3.0,
        )


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_setup_evidence_is_rejected_at_the_boundary(
    invalid_value: float,
) -> None:
    with pytest.raises(ValidationError, match="must be finite"):
        _setup(sweep_extreme_price=invalid_value)


class _FakeAuditQuery:
    def __init__(self, client: _FakeAuditClient) -> None:
        self.client = client

    def execute(self) -> object:
        if self.client.should_fail:
            raise OSError("database unavailable")

        self.client.was_executed = True
        return object()


class _FakeAuditTable:
    def __init__(self, client: _FakeAuditClient) -> None:
        self.client = client

    def insert(self, payload: dict[str, object]) -> _FakeAuditQuery:
        self.client.payload = payload
        return _FakeAuditQuery(self.client)


class _FakeAuditClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.table_name: str | None = None
        self.payload: dict[str, object] | None = None
        self.was_executed = False

    def table(self, table_name: str) -> _FakeAuditTable:
        self.table_name = table_name
        return _FakeAuditTable(self)


def test_log_filter_result_serializes_the_existing_audit_contract() -> None:
    setup = _setup()
    result = evaluate(
        setup,
        _context(),
        FilterConfig(),
    )
    client = _FakeAuditClient()

    log_filter_result(
        result,
        account_id=ACCOUNT_ID,
        supabase_client=cast(AuditClient, client),
    )

    assert client.table_name == "audit_log"
    assert client.was_executed is True
    assert client.payload is not None
    assert client.payload["account_id"] == str(UUID(ACCOUNT_ID))
    assert client.payload["timestamp"] == setup.timestamp.isoformat()
    assert client.payload["reward_risk_ratio"] == pytest.approx(3.0)
    assert client.payload["checks_detail"] == [
        check.model_dump(mode="json") for check in result.checks
    ]
    assert client.payload["raw_setup"] == setup.model_dump(mode="json")


def test_account_id_changes_only_the_audit_projection() -> None:
    result = evaluate(
        _setup(),
        _context(),
        FilterConfig(),
    )
    first_client = _FakeAuditClient()
    second_client = _FakeAuditClient()

    log_filter_result(
        result,
        account_id=ACCOUNT_ID,
        supabase_client=cast(AuditClient, first_client),
    )
    log_filter_result(
        result,
        account_id=SECOND_ACCOUNT_ID,
        supabase_client=cast(AuditClient, second_client),
    )

    assert first_client.payload is not None
    assert second_client.payload is not None
    first_payload = dict(first_client.payload)
    second_payload = dict(second_client.payload)
    first_payload.pop("account_id")
    second_payload.pop("account_id")

    assert first_payload == second_payload


def test_audit_failure_raises_and_must_block_execution() -> None:
    result = evaluate(
        _setup(),
        _context(),
        FilterConfig(),
    )
    client = _FakeAuditClient(should_fail=True)

    with pytest.raises(RuntimeError, match="must not proceed to execution"):
        log_filter_result(
            result,
            account_id=ACCOUNT_ID,
            supabase_client=cast(AuditClient, client),
        )


def test_audit_rejects_invalid_account_id_before_insert() -> None:
    result = evaluate(
        _setup(),
        _context(),
        FilterConfig(),
    )
    client = _FakeAuditClient()

    with pytest.raises(ValueError, match="valid UUID"):
        log_filter_result(
            result,
            account_id="not-a-uuid",
            supabase_client=cast(AuditClient, client),
        )

    assert client.table_name is None
