import uuid
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Literal

from backend.config.logger import setup_logger
from backend.config.supaclient import supabase
from backend.config.secrets import get_azure_secret

logger = setup_logger(__name__)

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
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))

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
        supabase.table("signals").insert(payload).execute()
        logger.info(
            f"[VERDICT SAVED] signal_id={verdict.signal_id} "
            f"symbol={verdict.symbol} direction={verdict.direction} "
            f"scenario={verdict.scenario} execute_at={verdict.execute_at}"
        )
        return payload
    except Exception as e:
        logger.error(f"[VERDICT SAVE FAILED] signal_id={verdict.signal_id} error={e}")
        raise

def publish_verdict(payload: dict):
    """
    Publishes the saved verdict payload directly to Upstash Redis.
    Accepts the dictionary returned by save_verdict.
    """
    try:
        # Pull your connection string straight from Azure Key Vault
        redis_url = get_azure_secret("REDIS-URL")
        if not redis_url:
            raise ValueError("REDIS-URL secret could not be retrieved from Key Vault.")
            
        # Connect with short execution timeouts to keep execution rapid
        r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        
        # Publish the data payload to your primary engine channel
        channel = "signals"
        serialized_data = json.dumps(payload)
        
        r.publish(channel, serialized_data)
        
        logger.info(
            f"[REDIS PUBLISHED] channel={channel} "
            f"signal_id={payload.get('signal_id')} symbol={payload.get('symbol')}"
        )
    except Exception as e:
        logger.error(f"[REDIS PUBLISH FAILED] error={e}")
        raise
