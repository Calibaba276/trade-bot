from datetime import datetime
from pathlib import Path
import sys

from lumibot.backtesting import PolygonDataBacktesting
from lumibot.traders import Trader

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from backend.brokers.mt5_broker import MetaTrader5
from backend.config.logger import setup_logger
from backend.config.secrets import get_azure_secret
from backend.config.supaclient import supabase
from backend.strategies.eurusd_model import EURUSDModel

logger = setup_logger(__name__)


def _get_account_strategy_config(account_login: str, server: str) -> dict:
    """
    Resolve per-account strategy risk config from broker_accounts.
    Falls back to defaults when no row is found.
    """
    defaults = {
        "rr_ratio": 3.0,
        "max_daily_drawdown_pct": 0.02,
        "breakeven_buffer_ticks": 10,
    }

    try:
        row = (
            supabase.table("broker_accounts")
            .select("*")
            .eq("account_number", str(account_login))
            .eq("server", server)
            .limit(1)
            .execute()
        )
        if getattr(row, "data", None):
            data = row.data[0]
            drawdown_value = data.get("max_daily_drawdown_pct")
            if drawdown_value is None:
                drawdown_value = data.get("max_daily_drawdown")
            if drawdown_value is None:
                drawdown_value = defaults["max_daily_drawdown_pct"]

            return {
                "rr_ratio": float(data.get("rr_ratio", defaults["rr_ratio"]) or defaults["rr_ratio"]),
                "max_daily_drawdown_pct": float(drawdown_value or defaults["max_daily_drawdown_pct"]),
                "breakeven_buffer_ticks": int(
                    data.get("breakeven_buffer_ticks", defaults["breakeven_buffer_ticks"])
                    or defaults["breakeven_buffer_ticks"]
                ),
                # Frontend emitter needs these to satisfy RLS on trade_events / candles
                "account_id": str(data["id"]) if data.get("id") else None,
                "user_id": str(data["user_id"]) if data.get("user_id") else None,
            }
    except Exception as exc:
        logger.warning(f"Could not read strategy config for account={account_login} on server={server}: {exc}")

    logger.warning(
        f"No broker_accounts config found for account={account_login} on server={server}; using defaults"
    )
    return defaults


def run():
    is_backtesting = get_azure_secret("ISBACKTESTING")
    backtesting_start = get_azure_secret("BACKTESTING-START")
    backtesting_end = get_azure_secret("BACKTESTING-END")

    polygon_api_key = get_azure_secret("POLYGON-API-KEY")

    account = get_azure_secret("ACCOUNT")
    password = get_azure_secret("PASSWORD")
    server = get_azure_secret("SERVER")

    if str(is_backtesting).lower() == "true":
        start_date = datetime.strptime(backtesting_start, "%Y-%m-%d")
        end_date = datetime.strptime(backtesting_end, "%Y-%m-%d")

        EURUSDModel.backtest(
            PolygonDataBacktesting,
            start_date,
            end_date,
            parameters={
                "symbol": "C:EURUSD",
                "risk_amount": 500,
                "rr_ratio": 3.0,
                "max_daily_drawdown_pct": 0.02,
                "breakeven_buffer_ticks": 10,
                "stop_buffer_pips": 2,
            },
            polygon_api_key=polygon_api_key,
            quiet_logs=False,
        )
    else:
        strategy_cfg = _get_account_strategy_config(str(account), server)

        broker = MetaTrader5(
            {
                "login": int(account),
                "password": password,
                "server": server,
                "timezone": "Africa/Lagos",
                "path": "C:\\Program Files\\ICT\\terminal64.exe",
            }
        )

        strategy = EURUSDModel(
            broker=broker,
            parameters={
                "symbol": "EURUSDm",
                "risk_amount": 500,
                "rr_ratio": strategy_cfg["rr_ratio"],
                "max_daily_drawdown_pct": strategy_cfg["max_daily_drawdown_pct"],
                "breakeven_buffer_ticks": strategy_cfg["breakeven_buffer_ticks"],
                "stop_buffer_pips": 2,
                # Frontend emitter identifiers (None in backtest / when account has no user yet)
                "user_id": strategy_cfg.get("user_id"),
                "account_id": strategy_cfg.get("account_id"),
            },
        )

        trader = Trader()
        trader.add_strategy(strategy)
        trader.run_all()


if __name__ == "__main__":
    run()

