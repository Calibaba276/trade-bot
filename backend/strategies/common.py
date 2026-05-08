import math


def calculate_quantity(self, asset, stop_loss=None):
    """Quantity Calculator for Stocks and Forex."""
    price = self.get_last_price(asset)

    if price is None or price == 0:
        self.log_message(f"Warning: Price for {asset.symbol} is 0 or None. Cannot calculate $25 trade.")
        return 0

    if stop_loss is not None:
        sl_distance = abs(price - stop_loss)
        if sl_distance == 0:
            return 0

        raw_quantity = self.risk_amount / sl_distance

        if asset.asset_type == "forex":
            step = 0.01
            quantity = raw_quantity / 100000
            final_qty = round(math.floor(quantity / step) * step, 2)
        else:
            quantity = raw_quantity
            final_qty = math.floor(quantity)
    else:
        final_qty = self.risk_amount / price

    if final_qty <= 0:
        self.log_message(f"Quantity too small for {asset.symbol} with $25 Limit.")
        return 0

    return final_qty


def _is_daily_drawdown_halted(strategy, current_date):
    """Use broker drawdown guard when available, otherwise apply strategy-local fallback."""
    broker_drawdown_guard = getattr(strategy.broker, "is_daily_drawdown_halted", None)
    if callable(broker_drawdown_guard):
        return broker_drawdown_guard(strategy, current_date)

    if strategy.last_trade_date != current_date:
        strategy.last_trade_date = current_date
        strategy.daily_equity_start = strategy.get_portfolio_value()
        return False

    if strategy.daily_equity_start is None:
        strategy.daily_equity_start = strategy.get_portfolio_value()
        return False

    current_equity = strategy.get_portfolio_value()
    max_loss = strategy.daily_equity_start * strategy.max_daily_drawdown_pct
    return current_equity <= (strategy.daily_equity_start - max_loss)


def _manage_risk_controls(strategy, current_date, current_time):
    """Apply broker-specific breakeven logic when available and enforce daily drawdown cap."""
    broker_breakeven_manager = getattr(strategy.broker, "manage_breakeven_and_drawdown", None)
    if callable(broker_breakeven_manager):
        broker_breakeven_manager(strategy)

    if _is_daily_drawdown_halted(strategy, current_date):
        if current_time.minute == 0:
            strategy.log_message("[DRAWDOWN] Daily drawdown cap reached. Trading halted.")
        return True
    return False

