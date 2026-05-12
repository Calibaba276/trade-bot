import json
from dataclasses import asdict
from typing import Optional

import redis

from backend.services.verdict import Verdict
from backend.config.secrets import get_azure_secret

from ..config.logger import setup_logger

logger = setup_logger(__name__)

_redis: Optional[redis.Redis] = None

def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        url = get_azure_secret("REDIS-URL")
        if not url:
            raise RuntimeError("Missing REDIS-URL secret in Azure Key Vault")
        if str(url).startswith(("http://", "https://")):
            raise RuntimeError(
                "REDIS-URL must be a Redis URI (redis:// or rediss://), not an HTTP URL"
            )
        _redis = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
    return _redis

def publish_verdict(verdict: Verdict):
    """Serialise the verdict to JSON and publish it to the Redis
    'signals' channel. Returns the number of workers that received
    the message (Redis Pub/Sub subscriber count)."""

    r = _get_redis()
    payload = json.dumps(asdict(verdict))

    try:
        subscriber_count = r.publish("signals", payload)

        logger.info(
            f"[SIGNAL PUBLISHED] signal_id={verdict.signal_id} "
            f"symbol={verdict.symbol} direction={verdict.direction} "
            f"scenario={verdict.scenario} "
            f"execute_at={verdict.execute_at} "
            f"workers_notified={subscriber_count}"
        )

        if subscriber_count == 0:
            logger.warning(
                f"[SIGNAL PUBLISHED — NO LISTENERS] signal_id={verdict.signal_id} "
                f"No workers subscribed. Signal saved to Supabase but not executed."
            )
        return subscriber_count
    except Exception as e:
        logger.error(f"[PUBLISH FAILED] signal_id={verdict.signal_id} error={e}")
        raise

def redis_healthy() -> None:
    """
    Ping Redis. Raises ConnectionError if unreachable.
    Call this once at bot startup so a Redis outage is caught
    immediately rather than silently at signal time.
    """
    try:
        _get_redis().ping()
        logger.info("Redis connection healthy.")
    except Exception as e:
        raise ConnectionError(f"[REDIS] Cannot connect: {e}")
