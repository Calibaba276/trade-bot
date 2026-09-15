"""Explainable, fail-closed selectivity checks for EURUSD ICT setups.

The filter accepts only the immutable :class:`Setup` handoff. It does not read
raw candles, broker state, or external services. Session facts and previously
accepted/evaluated setup identities are supplied explicitly through
``FilterContext`` so evaluation stays deterministic and testable. Selectivity
state is strategy-scoped; account-specific execution limits remain worker
responsibilities.
"""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from math import isfinite
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.strategies.eurusd_model import Setup

FilterCheckName = Literal[
    "check_session_safety",
    "check_selectivity",
    "check_confluence",
    "check_bias_quality",
    "check_liquidity_target",
    "check_amd_timing",
]

ConfigurableCheckName = Literal[
    "check_selectivity",
    "check_confluence",
    "check_bias_quality",
    "check_liquidity_target",
    "check_amd_timing",
]


class SessionSafetyContext(BaseModel):
    """Externally resolved no-trade facts for the setup's session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_resolved: bool = False
    is_bank_holiday: bool | None = None
    is_nfp_release_day: bool | None = None
    is_fomc_decision_afternoon: bool | None = None
    has_draw_on_liquidity: bool | None = None
    is_adr_exhausted: bool | None = None
    has_clear_dxy_conflict: bool | None = None

    @model_validator(mode="after")
    def resolved_context_must_be_complete(self) -> SessionSafetyContext:
        safety_values = (
            self.is_bank_holiday,
            self.is_nfp_release_day,
            self.is_fomc_decision_afternoon,
            self.has_draw_on_liquidity,
            self.is_adr_exhausted,
            self.has_clear_dxy_conflict,
        )
        if self.is_resolved and any(value is None for value in safety_values):
            raise ValueError("resolved session safety context must be complete")

        return self


class FilterContext(BaseModel):
    """Strategy/session state needed by checks but absent from ``Setup``.

    Killzone quota entries represent accepted setups only. Rejected candidates
    must never be added to ``accepted_setup_killzones``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_state_is_resolved: bool = False
    accepted_setups_today: int | None = Field(default=None, ge=0)
    accepted_setup_killzones: tuple[str, ...] | None = None
    accepted_narrative_keys: frozenset[str] | None = None
    evaluated_setup_keys: frozenset[str] | None = None
    session_safety: SessionSafetyContext = Field(default_factory=SessionSafetyContext)

    @model_validator(mode="after")
    def resolved_strategy_state_must_be_complete(self) -> FilterContext:
        strategy_values = (
            self.accepted_setups_today,
            self.accepted_setup_killzones,
            self.accepted_narrative_keys,
            self.evaluated_setup_keys,
        )
        if self.strategy_state_is_resolved and any(
            value is None for value in strategy_values
        ):
            raise ValueError("resolved strategy filter context must be complete")

        return self


class FilterCheckResult(BaseModel):
    """One explainable setup-quality or session-safety decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_name: FilterCheckName
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    reason: str = Field(min_length=1)


class FilterResult(BaseModel):
    """Immutable outcome of one complete setup evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    setup: Setup
    passed: bool
    composite_score: float = Field(ge=0.0, le=1.0)
    checks: tuple[FilterCheckResult, ...]
    rejected_by: FilterCheckName | None = None

    @model_validator(mode="after")
    def outcome_must_match_rejection(self) -> FilterResult:
        if self.passed == (self.rejected_by is not None):
            raise ValueError("passed and rejected_by describe conflicting outcomes")

        return self


class FilterConfig(BaseModel):
    """Validated selectivity settings; malformed values fail closed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hard_gate_checks: frozenset[ConfigurableCheckName] = frozenset(
        {
            "check_selectivity",
            "check_confluence",
            "check_liquidity_target",
        }
    )

    max_accepted_setups_per_day: int = Field(default=2, ge=1)
    max_accepted_setups_per_killzone: int = Field(default=1, ge=1)

    min_confluence_categories: int = Field(default=2, ge=1, le=3)
    min_displacement_atr: float = Field(default=1.5, gt=0)
    high_quality_liquidity_types: frozenset[str] = frozenset(
        {
            "pdh",
            "pdl",
            "asian_high",
            "asian_low",
            "previous_session",
            "prev_day_high",
            "prev_day_low",
            "prev_session_high",
            "prev_session_low",
        }
    )

    ideal_bias_swing_count: int = Field(default=3, ge=1)
    bias_quality_weight: float = Field(default=0.5, ge=0)
    min_bias_quality_score: float = Field(default=0.67, ge=0, le=1)

    min_reward_risk_ratio: float = Field(default=3.0, gt=0)
    target_reward_risk_ratio: float = Field(default=4.0, gt=0)
    liquidity_target_weight: float = Field(default=0.5, ge=0)

    max_candles_sweep_to_mss: int = Field(default=5, ge=1)
    amd_timing_weight: float = Field(default=0.5, ge=0)
    min_amd_timing_score: float = Field(default=0.3, ge=0, le=1)

    @model_validator(mode="after")
    def validate_filter_configuration(self) -> FilterConfig:
        required_hard_gates = {
            "check_selectivity",
            "check_confluence",
            "check_liquidity_target",
        }
        if not required_hard_gates.issubset(self.hard_gate_checks):
            raise ValueError(
                "selectivity, confluence, and liquidity target must remain hard gates"
            )

        if self.target_reward_risk_ratio < self.min_reward_risk_ratio:
            raise ValueError(
                "target_reward_risk_ratio must be at least min_reward_risk_ratio"
            )

        if not self.high_quality_liquidity_types:
            raise ValueError("high_quality_liquidity_types must not be empty")

        return self

    def is_hard_gate(self, check_name: FilterCheckName) -> bool:
        if check_name == "check_session_safety":
            return True

        return check_name in self.hard_gate_checks


def setup_narrative_key(setup: Setup) -> str:
    """Return a stable identity for one sweep-to-MSS market narrative."""

    evidence = "|".join(
        (
            setup.instrument,
            setup.direction,
            setup.sweep_time.isoformat(),
            setup.mss_time.isoformat(),
            setup.sweep_level_type,
            format(setup.sweep_extreme_price, ".10g"),
        )
    )
    return sha256(evidence.encode("utf-8")).hexdigest()


def setup_evaluation_key(setup: Setup) -> str:
    """Return a stable identity for one exact immutable setup candidate."""

    evidence = "|".join(
        (
            setup_narrative_key(setup),
            setup.timestamp.isoformat(),
            format(setup.entry_price, ".10g"),
            format(setup.stop_price, ".10g"),
            format(setup.target_price, ".10g"),
            setup.extract_fvg_and_order_block,
        )
    )
    return sha256(evidence.encode("utf-8")).hexdigest()


def check_session_safety(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Fail closed on session-wide no-trade conditions and invalid timing."""

    del config
    safety = context.session_safety
    if not safety.is_resolved:
        return FilterCheckResult(
            check_name="check_session_safety",
            passed=False,
            score=0.0,
            weight=1.0,
            reason="Session safety data is unresolved",
        )

    required_numeric_evidence = (
        setup.range_high,
        setup.range_low,
        setup.range_mid,
        setup.target_liquidity_level,
        setup.sweep_extreme_price,
        setup.mss_displacement_atr_multiple,
        setup.entry_price,
        setup.stop_price,
        setup.target_price,
    )
    has_invalid_numeric_evidence = not all(
        isfinite(value) for value in required_numeric_evidence
    )

    failure_reasons = (
        (safety.is_bank_holiday is True, "Bank-holiday session is disabled"),
        (safety.is_nfp_release_day is True, "NFP release day is disabled"),
        (
            safety.is_fomc_decision_afternoon is True,
            "FOMC decision afternoon is disabled",
        ),
        (
            safety.has_draw_on_liquidity is not True,
            "No valid draw on liquidity is available",
        ),
        (safety.is_adr_exhausted is True, "Average daily range is exhausted"),
        (safety.has_clear_dxy_conflict is True, "Clear DXY structural conflict"),
        (
            not setup.target_liquidity_type.strip()
            or not isfinite(setup.target_liquidity_level),
            "Setup has no valid draw on liquidity",
        ),
        (
            has_invalid_numeric_evidence,
            "Setup contains non-finite numeric evidence",
        ),
        (
            setup.mss_time < setup.sweep_time
            or setup.timestamp < setup.mss_time
            or setup.mss_candle_index <= setup.sweep_candle_index,
            "Setup timestamps are not chronologically valid",
        ),
    )

    for failed, reason in failure_reasons:
        if failed:
            return FilterCheckResult(
                check_name="check_session_safety",
                passed=False,
                score=0.0,
                weight=1.0,
                reason=reason,
            )

    return FilterCheckResult(
        check_name="check_session_safety",
        passed=True,
        score=1.0,
        weight=1.0,
        reason="Session safety gates clear",
    )


def check_selectivity(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Limit accepted setups without consuming quota for rejected candidates."""

    if not context.strategy_state_is_resolved:
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason="Strategy selectivity state is unresolved",
        )

    accepted_setups_today = context.accepted_setups_today
    accepted_setup_killzones = context.accepted_setup_killzones
    accepted_narrative_keys = context.accepted_narrative_keys
    evaluated_setup_keys = context.evaluated_setup_keys
    if (
        accepted_setups_today is None
        or accepted_setup_killzones is None
        or accepted_narrative_keys is None
        or evaluated_setup_keys is None
    ):
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason="Strategy selectivity state is incomplete",
        )

    evaluation_key = setup_evaluation_key(setup)
    if evaluation_key in evaluated_setup_keys:
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason="Exact setup candidate was already evaluated",
        )

    narrative_key = setup_narrative_key(setup)
    if narrative_key in accepted_narrative_keys:
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason="Sweep/MSS narrative already has an accepted setup",
        )

    if accepted_setups_today >= config.max_accepted_setups_per_day:
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason=(
                "Daily accepted-setup cap reached "
                f"({config.max_accepted_setups_per_day})"
            ),
        )

    killzone_label = setup.killzone_label
    accepted_in_killzone = accepted_setup_killzones.count(killzone_label)
    if (
        killzone_label is not None
        and accepted_in_killzone >= config.max_accepted_setups_per_killzone
    ):
        return FilterCheckResult(
            check_name="check_selectivity",
            passed=False,
            score=0.0,
            weight=1.0,
            reason=f"Accepted setup cap reached for {killzone_label}",
        )

    return FilterCheckResult(
        check_name="check_selectivity",
        passed=True,
        score=1.0,
        weight=1.0,
        reason="Selectivity gates clear",
    )


def check_confluence(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Count independent structure, liquidity, and timing categories."""

    del context
    categories: list[str] = []

    if setup.mss_displacement_atr_multiple >= config.min_displacement_atr:
        categories.append("structure")

    if setup.sweep_level_type in config.high_quality_liquidity_types:
        categories.append("liquidity")

    if setup.sweep_in_killzone:
        categories.append("timing")

    categories_met = len(categories)
    passed = categories_met >= config.min_confluence_categories
    category_summary = ", ".join(categories) if categories else "none"

    return FilterCheckResult(
        check_name="check_confluence",
        passed=passed,
        score=categories_met / 3.0,
        weight=1.0,
        reason=(f"{categories_met}/3 independent categories met: {category_summary}"),
    )


def check_bias_quality(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Score confirmed bias structure without rejecting the setup."""

    del context
    score = min(
        setup.bias_swing_count / config.ideal_bias_swing_count,
        1.0,
    )
    passed = score >= config.min_bias_quality_score

    return FilterCheckResult(
        check_name="check_bias_quality",
        passed=passed,
        score=score,
        weight=config.bias_quality_weight,
        reason=(
            f"Bias swing count: {setup.bias_swing_count} "
            f"(ideal: {config.ideal_bias_swing_count})"
        ),
    )


def _reward_risk_ratio(setup: Setup) -> float | None:
    prices = (
        setup.entry_price,
        setup.stop_price,
        setup.target_price,
    )
    if not all(isfinite(price) for price in prices):
        return None

    if setup.direction == "long":
        has_valid_order = setup.stop_price < setup.entry_price < setup.target_price
    else:
        has_valid_order = setup.target_price < setup.entry_price < setup.stop_price

    if not has_valid_order:
        return None

    risk_distance = abs(setup.entry_price - setup.stop_price)
    if risk_distance <= 0:
        return None

    reward_distance = abs(setup.target_price - setup.entry_price)
    return reward_distance / risk_distance


def check_liquidity_target(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Hard-gate directional price ordering and minimum reward-to-risk."""

    del context
    reward_risk_ratio = _reward_risk_ratio(setup)
    if reward_risk_ratio is None:
        return FilterCheckResult(
            check_name="check_liquidity_target",
            passed=False,
            score=0.0,
            weight=config.liquidity_target_weight,
            reason="Entry, stop, and target prices are not directionally valid",
        )

    passed = reward_risk_ratio >= config.min_reward_risk_ratio
    score = min(
        reward_risk_ratio / config.target_reward_risk_ratio,
        1.0,
    )

    return FilterCheckResult(
        check_name="check_liquidity_target",
        passed=passed,
        score=score,
        weight=config.liquidity_target_weight,
        reason=(
            f"R:R = {reward_risk_ratio:.2f} "
            f"(minimum: {config.min_reward_risk_ratio:.2f})"
        ),
    )


def check_amd_timing(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterCheckResult:
    """Score manipulation-to-displacement timing without rejecting."""

    del context
    if not setup.sweep_in_killzone:
        score = 0.0
        return FilterCheckResult(
            check_name="check_amd_timing",
            passed=score >= config.min_amd_timing_score,
            score=score,
            weight=config.amd_timing_weight,
            reason="Sweep occurred outside a configured killzone",
        )

    candles_to_mss = setup.mss_candle_index - setup.sweep_candle_index
    is_clean_timing = 0 < candles_to_mss <= config.max_candles_sweep_to_mss
    score = 1.0 if is_clean_timing else 0.3

    return FilterCheckResult(
        check_name="check_amd_timing",
        passed=score >= config.min_amd_timing_score,
        score=score,
        weight=config.amd_timing_weight,
        reason=(
            f"Sweep-to-MSS: {candles_to_mss} candles "
            f"(preferred: 1-{config.max_candles_sweep_to_mss})"
        ),
    )


FilterCheck = Callable[
    [Setup, FilterContext, FilterConfig],
    FilterCheckResult,
]

FILTER_CHAIN: tuple[FilterCheck, ...] = (
    check_session_safety,
    check_selectivity,
    check_confluence,
    check_bias_quality,
    check_liquidity_target,
    check_amd_timing,
)


def evaluate(
    setup: Setup,
    context: FilterContext,
    config: FilterConfig,
) -> FilterResult:
    """Evaluate one candidate, stopping at the first failed hard gate."""

    results: list[FilterCheckResult] = []
    rejected_by: FilterCheckName | None = None

    for check in FILTER_CHAIN:
        result = check(
            setup,
            context,
            config,
        )
        results.append(result)

        if not result.passed and config.is_hard_gate(result.check_name):
            rejected_by = result.check_name
            break

    total_weight = sum(result.weight for result in results)
    weighted_score = sum(result.score * result.weight for result in results)
    composite_score = weighted_score / total_weight if total_weight > 0 else 0.0

    return FilterResult(
        setup=setup,
        passed=rejected_by is None,
        composite_score=composite_score,
        checks=tuple(results),
        rejected_by=rejected_by,
    )


class _AuditInsertQuery(Protocol):
    def execute(self) -> object: ...


class _AuditTable(Protocol):
    def insert(self, payload: dict[str, object]) -> _AuditInsertQuery: ...


class AuditClient(Protocol):
    def table(self, table_name: str) -> _AuditTable: ...


def log_filter_result(
    result: FilterResult,
    *,
    account_id: str,
    supabase_client: AuditClient,
) -> None:
    """Append one account-owned projection of a strategy filter outcome.

    ``account_id`` scopes audit visibility only. It must never alter the
    strategy-level result. A market runner that serves multiple eligible
    accounts writes the same result for each account before publishing it.
    Any insert failure raises so execution remains fail closed.
    """

    try:
        normalized_account_id = str(UUID(account_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("account_id must be a valid UUID") from exc

    setup = result.setup
    reward_risk_ratio = _reward_risk_ratio(setup)
    payload: dict[str, object] = {
        "account_id": normalized_account_id,
        "instrument": setup.instrument,
        "direction": setup.direction,
        "timestamp": setup.timestamp.isoformat(),
        "sweep_timestamp": setup.sweep_time.isoformat(),
        "mss_timestamp": setup.mss_time.isoformat(),
        "killzone_label": setup.killzone_label,
        "passed": result.passed,
        "rejected_by": result.rejected_by,
        "composite_score": result.composite_score,
        "checks_detail": [check.model_dump(mode="json") for check in result.checks],
        "bias": setup.bias,
        "bias_swing_count": setup.bias_swing_count,
        "entry_zone": setup.entry_zone,
        "target_liquidity_type": setup.target_liquidity_type,
        "sweep_level_type": setup.sweep_level_type,
        "extract_fvg_and_order_block": setup.extract_fvg_and_order_block,
        "entry_price": setup.entry_price,
        "stop_price": setup.stop_price,
        "target_price": setup.target_price,
        "reward_risk_ratio": reward_risk_ratio,
        "raw_setup": setup.model_dump(mode="json"),
    }

    try:
        (supabase_client.table("audit_log").insert(payload).execute())
    except Exception as exc:
        raise RuntimeError(
            "audit_log insert failed; setup must not proceed to execution"
        ) from exc
