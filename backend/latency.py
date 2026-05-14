#!/usr/bin/env python3
"""
Glass Box Trading Engine — Latency Validation Script
Tests Azure → Upstash Redis → Key Vault latency.
Run AFTER VM deployment to validate region selection.
"""

import os
import sys
import time
import statistics
from typing import List, Optional

from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret, VAULT_URL

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

def test_redis_latency(redis_url: str, num_pings: int = 20) -> Optional[dict]:
    """Test latency to Upstash Redis."""
    try:
        import redis
    except ImportError:
        print("❌ redis-py not installed. Run: pip install redis")
        logger.error("redis-py not installed")
        return None

    print("\n" + "=" * 70)
    print("🔍 TESTING UPSTASH REDIS LATENCY")
    print("=" * 70)

    try:
        r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        r.ping()
        print("✅ Connected to Upstash Redis successfully")
        logger.info("[REDIS] Connected successfully")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print("   Check REDIS_URL — verify the REDIS-URL secret in Key Vault")
        logger.error(f"[REDIS] Connection failed: {e}")
        return None

    latencies: List[float] = []

    print(f"\nPinging Redis {num_pings} times...\n")

    for i in range(num_pings):
        try:
            start = time.perf_counter()
            r.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            if (i + 1) % 5 == 0:
                print(f"  [{i+1:2d}/{num_pings}] {latency_ms:6.2f}ms", end="")
                if latency_ms < 15:
                    print(" ✅")
                elif latency_ms < 30:
                    print(" ⚠️  (acceptable)")
                else:
                    print(" ❌ (slow!)")

            time.sleep(0.1)
        except Exception as e:
            print(f"  [{i+1:2d}/{num_pings}] ERROR: {e}")
            logger.warning(f"[REDIS] Ping {i+1} failed: {e}")

    if not latencies:
        return None

    avg = statistics.mean(latencies)
    median = statistics.median(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0

    print("\n" + "-" * 70)
    print("📊 REDIS LATENCY STATISTICS")
    print("-" * 70)
    print(f"  Average:    {avg:7.2f}ms")
    print(f"  Median:     {median:7.2f}ms")
    print(f"  Min:        {min_lat:7.2f}ms")
    print(f"  Max:        {max_lat:7.2f}ms")
    print(f"  Std Dev:    {stdev:7.2f}ms")
    print(f"  Range:      {max_lat - min_lat:7.2f}ms")

    logger.info(
        f"[REDIS] avg={avg:.2f}ms median={median:.2f}ms "
        f"min={min_lat:.2f}ms max={max_lat:.2f}ms stdev={stdev:.2f}ms"
    )

    print("\n🎯 VERDICT:")
    if avg < 10:
        print("   ✅ EXCELLENT (< 10ms) — Perfect AWS/Azure region match")
    elif avg < 20:
        print("   ✅ GOOD (< 20ms) — Acceptable for trading")
    elif avg < 50:
        print("   ⚠️  ACCEPTABLE (< 50ms) — Trading is viable but not ideal")
    else:
        print("   ❌ POOR (> 50ms) — Check region match!")
        print(f"\n   DIAGNOSTIC:")
        print(f"   • Verify Upstash Redis region matches your Azure VM region")
        print(f"   • Is Azure VM in same region?")
        print(f"   • Check Upstash console for actual Redis region")

    return {
        "average": avg,
        "median": median,
        "min": min_lat,
        "max": max_lat,
        "stdev": stdev,
        "latencies": latencies,
    }


# ---------------------------------------------------------------------------
# Key Vault
# ---------------------------------------------------------------------------

def test_key_vault_latency(
    vault_url: str,
    test_secret: Optional[str] = None,
    num_fetches: int = 10,
) -> Optional[dict]:
    """Test latency to Azure Key Vault."""
    try:
        from azure.keyvault.secrets import SecretClient
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print(
            "\n❌ Azure SDK not installed. "
            "Run: pip install azure-keyvault-secrets azure-identity"
        )
        logger.error("Azure SDK not installed")
        return None

    print("\n" + "=" * 70)
    print("🔍 TESTING AZURE KEY VAULT LATENCY")
    print("=" * 70)

    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        print(f"✅ Connected to Key Vault: {vault_url}")
        logger.info("[VAULT] Connected to Key Vault")
    except Exception as e:
        print(f"❌ Failed to connect to Key Vault: {e}")
        print(f"   • Check AZURE_VAULT_URL: {vault_url}")
        print(f"   • Check Managed Identity is enabled on VM")
        print(f"   • Check VM has 'Key Vault Secrets User' role")
        logger.error(f"[VAULT] Connection failed: {e}")
        return None

    if not test_secret:
        try:
            secret_list = [s.name for s in client.list_properties_of_secrets()]
            if secret_list:
                test_secret = secret_list[0]
                print("\nUsing first available secret for timing")
            else:
                print("⚠️  No secrets in vault. Add a test secret to measure latency.")
                return None
        except Exception as e:
            print(f"⚠️  Could not list secrets: {e}")
            logger.warning(f"[VAULT] Could not list secrets: {e}")
            return None

    latencies: List[float] = []
    errors = 0

    print(f"\nFetching vault secret {num_fetches} times...\n")

    for i in range(num_fetches):
        try:
            start = time.perf_counter()
            client.get_secret(test_secret)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            if (i + 1) % 5 == 0:
                print(f"  [{i+1:2d}/{num_fetches}] {latency_ms:6.2f}ms", end="")
                if latency_ms < 15:
                    print(" ✅")
                elif latency_ms < 30:
                    print(" ⚠️  ")
                else:
                    print(" ❌")

            time.sleep(0.2)
        except Exception as e:
            print(f"  [{i+1:2d}/{num_fetches}] ERROR: {str(e)[:50]}")
            logger.warning(f"[VAULT] Fetch {i+1} failed: {e}")
            errors += 1

    if not latencies:
        print("❌ All Key Vault fetches failed")
        logger.error("[VAULT] All fetches failed")
        return None

    avg = statistics.mean(latencies)
    median = statistics.median(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0

    print("\n" + "-" * 70)
    print("📊 KEY VAULT LATENCY STATISTICS")
    print("-" * 70)
    print(f"  Average:    {avg:7.2f}ms")
    print(f"  Median:     {median:7.2f}ms")
    print(f"  Min:        {min_lat:7.2f}ms")
    print(f"  Max:        {max_lat:7.2f}ms")
    print(f"  Std Dev:    {stdev:7.2f}ms")
    print(f"  Errors:     {errors}/{num_fetches}")

    logger.info(
        f"[VAULT] avg={avg:.2f}ms median={median:.2f}ms "
        f"min={min_lat:.2f}ms max={max_lat:.2f}ms errors={errors}/{num_fetches}"
    )

    print("\n🎯 VERDICT:")
    if avg < 10:
        print("   ✅ EXCELLENT (< 10ms) — Key Vault in same region")
    elif avg < 20:
        print("   ✅ GOOD (< 20ms) — Acceptable")
    else:
        print(f"   ⚠️  SLOW ({avg:.0f}ms) — Verify Key Vault region matches VM region")

    return {
        "average": avg,
        "median": median,
        "min": min_lat,
        "max": max_lat,
        "stdev": stdev,
        "errors": errors,
        "latencies": latencies,
    }


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def test_supabase_latency(
    supabase_url: str,
    supabase_key: str,
    num_requests: int = 5,
) -> Optional[dict]:
    """Test latency to Supabase."""
    try:
        from supabase import create_client
    except ImportError:
        print("\n❌ Supabase client not installed. Run: pip install supabase")
        logger.error("supabase client not installed")
        return None

    print("\n" + "=" * 70)
    print("🔍 TESTING SUPABASE LATENCY")
    print("=" * 70)

    try:
        supabase = create_client(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
        logger.info("[SUPABASE] Connected successfully")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        logger.error(f"[SUPABASE] Connection failed: {e}")
        return None

    latencies: List[float] = []

    print(f"\nPinging Supabase {num_requests} times...\n")

    for i in range(num_requests):
        start = time.perf_counter()
        try:
            supabase.table("broker_accounts").select("id", count="exact").limit(1).execute()
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            print(f"  [{i+1:2d}/{num_requests}] {latency_ms:6.2f}ms", end="")
            if latency_ms < 30:
                print(" ✅")
            elif latency_ms < 100:
                print(" ⚠️  (acceptable for async)")
            else:
                print(" ⚠️  (slow)")

            time.sleep(0.2)
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            # Table may not exist in all environments — round-trip timing is still valid
            if "does not exist" in str(e).lower() or "42p01" in str(e).lower():
                latencies.append(latency_ms)
                print(f"  [{i+1:2d}/{num_requests}] {latency_ms:6.2f}ms ⚠️  (table missing — timing valid)")
            else:
                print(f"  [{i+1:2d}/{num_requests}] ERROR: {str(e)[:40]}")
                logger.warning(f"[SUPABASE] Request {i+1} failed: {e}")

    if not latencies:
        print("❌ All Supabase requests failed")
        logger.error("[SUPABASE] All requests failed")
        return None

    avg = statistics.mean(latencies)
    median = statistics.median(latencies)

    print("\n" + "-" * 70)
    print("📊 SUPABASE LATENCY STATISTICS")
    print("-" * 70)
    print(f"  Average:    {avg:7.2f}ms")
    print(f"  Median:     {median:7.2f}ms")
    print(f"  Min:        {min(latencies):7.2f}ms")
    print(f"  Max:        {max(latencies):7.2f}ms")

    logger.info(
        f"[SUPABASE] avg={avg:.2f}ms median={median:.2f}ms "
        f"min={min(latencies):.2f}ms max={max(latencies):.2f}ms"
    )

    print("\n🎯 VERDICT:")
    if avg < 50:
        print("   ✅ GOOD (< 50ms) — Acceptable (async write, not critical path)")
    elif avg < 100:
        print("   ⚠️  ACCEPTABLE (50–100ms) — Supabase may be remote region")
    else:
        print("   ⚠️  SLOW (> 100ms) — Consider migrating Supabase to same region")

    return {
        "average": avg,
        "median": median,
        "min": min(latencies),
        "max": max(latencies),
        "latencies": latencies,
    }


# ---------------------------------------------------------------------------
# End-to-end summary
# ---------------------------------------------------------------------------

def calculate_end_to_end(
    redis_stats: Optional[dict],
    vault_stats: Optional[dict],
    supabase_stats: Optional[dict] = None,
) -> None:
    """Calculate and display estimated end-to-end latency."""
    print("\n" + "=" * 70)
    print("📈 END-TO-END LATENCY ESTIMATE")
    print("=" * 70)

    if not redis_stats or not vault_stats:
        print("❌ Cannot calculate without Redis and Key Vault stats")
        return

    redis_avg = redis_stats["average"]
    vault_avg = vault_stats["average"]
    supabase_avg = supabase_stats["average"] if supabase_stats else 30  # estimate

    print("\nSignal Flow (Your Responsibility):")
    print(f"  1. Orchestrator → Redis publish:     3–5ms (local)")
    print(f"  2. Worker Redis subscribe latency:  {redis_avg:.1f}ms (measured)")
    print(f"  3. Worker → Key Vault fetch:        {vault_avg:.1f}ms (measured)")
    print(f"  4. Worker → MT5 order send:         2–3ms (local)")
    print(f"  ────────────────────────────────────────────")

    your_latency = 5 + redis_avg + vault_avg + 3
    print(f"  TOTAL YOUR LATENCY:                 {your_latency:.1f}ms")

    print("\n\nBroker Execution (Not Your Control):")
    print(f"  1. Broker receives order:           5–15ms")
    print(f"  2. Order matching engine:           5–15ms")
    print(f"  3. Confirmation back to MT5:        5–15ms")
    print(f"  ────────────────────────────────────────────")
    print(f"  TYPICAL BROKER LATENCY:             15–45ms")

    print("\n\n🎯 FINAL ESTIMATE:")
    total_latency = your_latency + 30  # average broker latency
    print(f"  Your latency:      {your_latency:.1f}ms")
    print(f"  Broker latency:    ~30ms (typical)")
    print(f"  ─────────────────────────────")
    print(f"  TOTAL EXECUTION:   {total_latency:.1f}ms")

    if total_latency < 50:
        print("\n   ✅ EXCELLENT — Top 5% of traders")
    elif total_latency < 100:
        print("\n   ✅ GOOD — Top 20% of traders")
    elif total_latency < 150:
        print("\n   ⚠️  ACCEPTABLE — Viable for FTMO")
    else:
        print("\n   ❌ SLOW — Check region configuration")

    logger.info(
        f"[E2E] your_latency={your_latency:.1f}ms total_estimate={total_latency:.1f}ms"
    )

    if supabase_stats:
        print(f"\n  Note: Supabase writes (~{supabase_stats['average']:.0f}ms) are async")
        print(f"        Not in critical execution path")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "Glass Box Trading Engine — Latency Validator" + " " * 14 + "║")
    print("╚" + "=" * 68 + "╝\n")

    logger.info("[LATENCY] Starting latency validation")

    # Primary source: Azure Key Vault.  Fall back to env vars so the script
    # can also be run locally before Key Vault access is configured.
    redis_url = get_azure_secret("REDIS-URL") or os.getenv("REDIS_URL")
    vault_url = VAULT_URL or os.getenv("AZURE_VAULT_URL")
    supabase_url = get_azure_secret("SUPABASE-URL") or os.getenv("SUPABASE_URL")
    supabase_key = get_azure_secret("SUPABASE-KEY") or os.getenv("SUPABASE_SERVICE_KEY")

    if not redis_url:
        print("❌ Redis URL not found. Set REDIS-URL in Key Vault or REDIS_URL env var.")
        logger.error("[LATENCY] REDIS_URL not configured")
        sys.exit(1)
    if not vault_url:
        print("❌ Vault URL not found. Set AZURE_VAULT_URL env var.")
        logger.error("[LATENCY] AZURE_VAULT_URL not configured")
        sys.exit(1)

    print("Configuration detected:")
    print(f"  Redis:     [REDIS-URL from Key Vault]")
    print(f"  Key Vault: {vault_url}")
    print(f"  Supabase:  {'[SUPABASE-URL from Key Vault]' if supabase_url else 'Not configured'}")

    redis_stats = test_redis_latency(redis_url, num_pings=20)
    vault_stats = test_key_vault_latency(vault_url, num_fetches=10)

    supabase_stats = None
    if supabase_url and supabase_key:
        supabase_stats = test_supabase_latency(supabase_url, supabase_key, num_requests=5)

    if redis_stats and vault_stats:
        calculate_end_to_end(redis_stats, vault_stats, supabase_stats)

    print("\n" + "=" * 70)
    print("✅ LATENCY TEST COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review end-to-end latency estimate above")
    print("  2. If > 100ms, check Redis/Vault region match")
    print("  3. If < 80ms, you're ready for live trading 🚀")

    logger.info("[LATENCY] Validation complete")


if __name__ == "__main__":
    main()
