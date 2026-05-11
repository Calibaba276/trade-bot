import uuid
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Literal

from backend.config import logger
from backend.config.supaclient import supabase

Scenario = Literal[
    "london_bearish",
    "london_bullish",
    "ny_continuation_bearish",
    "ny_continuation_bullish",
    "ny_range_bearish",
    "ny_range_bullish",
]

@dataclass
class Verdict:
    signal_id: str = str(uuid.uuid4())
    symbol: str
    direction: Literal["buy", "sell"]
    entry_price: float
    stop_loss: float
    take_profit: float
    risk: float
    reward_risk_ratio: float
    
    created_at: str
    execute_at: str
    scenario: Scenario

def build_verdict(
        symbol, direction, entry, sl, tp, risk, rr, scenario
) -> Verdict:
    """ Returns a clean verdict object"""

    nigeria_tz = timezone(timedelta(hours=1))
    now = datetime.now(nigeria_tz)

    execute_time = (now + timedelta(seconds=1)).isoformat()

    return Verdict(
        signal_id=str(uuid.uuid4()),
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        risk=risk,
        reward_risk_ratio=rr,
        execute_at=execute_time,
        scenario=scenario,
        created_at=now.isoformat()
    )

def save_verdict(verdict: Verdict):
    """Saves the verdict to Supabase Signals table and returns the data for Redis broadcasting"""

    payload = asdict(verdict)

    try:
        result = supabase.table("signals").insert(payload).execute()
        logger.info(
            f"[VERDICT SAVED] signal_id={verdict.signal_id} "
            f"symbol={verdict.symbol} direction={verdict.direction} "
            f"scenario={verdict.scenario} execute_at={verdict.execute_at}"
        )
        return result
    except Exception as e:
        logger.error(f"[VERDICT SAVE FAILED] signal_id={verdict.signal_id} error={e}")
        raise