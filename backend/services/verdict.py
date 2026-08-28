import uuid
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from backend.config.logger import setup_logger

logger = setup_logger(__name__)

def _admin_supabase():
    # Keep cloud integrations out of the module import path.  Verdict creation
    # is deterministic and must be unit-testable without Azure credentials.
    from supabase import create_client
    from backend.config.secrets import get_azure_secret
    from backend.config.supaclient import SUPABASE_URL

    key = get_azure_secret("SUPABASE-SERVICE-ROLE-KEY") or get_azure_secret("SUPABASE-KEY")
    return create_client(SUPABASE_URL, key)

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

    # ICT indicator state captured at signal generation time
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    swept_high: Optional[float] = None
    swept_low: Optional[float] = None
    mss_swing_high: Optional[float] = None
    mss_swing_low: Optional[float] = None
    fvg_top: Optional[float] = None
    fvg_bottom: Optional[float] = None
    fvg_confirmed: Optional[bool] = None
    sweep_point: Optional[float] = None
    daily_bias: Optional[str] = None
    london_high: Optional[float] = None
    london_low: Optional[float] = None

def build_verdict(
        symbol, direction, entry, sl, tp, risk, rr, scenario,
        pdh=None, pdl=None,
        swept_high=None, swept_low=None,
        mss_swing_high=None, mss_swing_low=None,
        fvg_top=None, fvg_bottom=None, fvg_confirmed=None,
        sweep_point=None,
        daily_bias=None,
        london_high=None, london_low=None,
) -> Verdict:
    """Returns a clean verdict object with ICT indicator state."""

    if entry is None or sl is None or tp is None:
        raise ValueError(
            f"Invalid verdict prices: entry={entry}, sl={sl}, tp={tp}"
        )

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
        created_at=now.isoformat(),
        pdh=pdh,
        pdl=pdl,
        swept_high=swept_high,
        swept_low=swept_low,
        mss_swing_high=mss_swing_high,
        mss_swing_low=mss_swing_low,
        fvg_top=fvg_top,
        fvg_bottom=fvg_bottom,
        fvg_confirmed=fvg_confirmed,
        sweep_point=sweep_point,
        daily_bias=daily_bias,
        london_high=london_high,
        london_low=london_low,
    )

def save_verdict(verdict: Verdict):
    """Saves the verdict to Supabase Signals table and returns the data for Redis broadcasting"""

    from backend.services.telegram_notifier import notify_signal

    payload = asdict(verdict)

    try:
        _admin_supabase().table("signals").insert(payload).execute()
        logger.info(
            f"[VERDICT SAVED] signal_id={verdict.signal_id} "
            f"symbol={verdict.symbol} direction={verdict.direction} "
            f"scenario={verdict.scenario} execute_at={verdict.execute_at}"
        )
        notify_signal(
            symbol=verdict.symbol,
            direction=verdict.direction,
            scenario=verdict.scenario,
            entry=verdict.entry_price,
            sl=verdict.stop_loss,
            tp=verdict.take_profit,
            signal_id=verdict.signal_id,
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
        import redis
        from backend.config.secrets import get_azure_secret

        # Pull your connection string straight from Azure Key Vault
        redis_url = get_azure_secret("REDIS-URL")
        if not redis_url:
            raise ValueError("REDIS-URL secret could not be retrieved from Key Vault.")
            
        # Connect with short execution timeouts to keep execution rapid
        r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        
        # Publish the data payload to your primary engine channel
        channel = "signals"
        serialized_data = json.dumps(payload)
        
        # publish() returns the number of subscribers that received the message.
        # Pub/sub has NO persistence — if this is 0, the signal was delivered to
        # nobody and is gone forever. Surfacing it here makes a deaf/absent worker
        # immediately visible instead of silently dropping trades.
        receivers = r.publish(channel, serialized_data)

        log = logger.warning if receivers == 0 else logger.info
        log(
            f"[REDIS PUBLISHED] channel={channel} receivers={receivers} "
            f"signal_id={payload.get('signal_id')} symbol={payload.get('symbol')}"
        )
        if receivers == 0:
            logger.warning(
                f"[REDIS NO SUBSCRIBERS] signal_id={payload.get('signal_id')} "
                f"was published but no worker was listening — the durability "
                f"backstop in the worker should recover it from the signals table."
            )
    except Exception as e:
        logger.error(f"[REDIS PUBLISH FAILED] error={e}")
        raise
