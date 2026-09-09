"""Persistence for setup-filter audit evaluations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

from backend.config.logger import setup_logger
from backend.strategies.setup_filter import FilterResult

logger = setup_logger(__name__)


def log_filter_result(
    result: FilterResult,
    account_id: str,
    supabase_client: Client,
) -> None:
    """Persist one pass/reject evaluation in the append-only audit log.

    The configured client is used by default. Tests may supply a compatible
    fake client without making network calls or loading credentials.
    """

    setup = result.setup
    risk_distance = abs(setup.entry_price - setup.stop_price)
    reward_distance = abs(setup.target_price - setup.entry_price)
    reward_risk_ratio = (
        reward_distance / risk_distance if risk_distance > 0 else None
    )

    row: dict[str, object] = {
        "account_id": account_id,
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
        supabase_client.table("audit_log").insert(row).execute()
    except Exception as exc:
        logger.error(
            "[AUDIT LOG FAILED] account_id=%s instrument=%s timestamp=%s error=%s",
            account_id,
            setup.instrument,
            setup.timestamp.isoformat(),
            exc,
        )
        raise
