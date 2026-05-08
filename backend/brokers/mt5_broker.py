import MetaTrader5 as mt5
import pandas as pd
from lumibot.brokers import Broker
from lumibot.entities import Asset, Position, Order

from datetime import datetime
from decimal import Decimal
import pytz
import zlib
import logging

from backend.config.logger import setup_logger

logger = setup_logger(__name__)

def generate_magic_number(strategy_name):
    return zlib.adler32(strategy_name.encode()) & 0xFFFFFFFF

class MetaTrader5(Broker):

    def __init__(self, config):
        super().__init__(name="MT5", data_source=self)
        self.SOURCE = "PANDAS"
        self.config = config
        self.timezone = self.config.get("timezone", "Africa/Lagos")
        self._initialize_mt5()

    def _initialize_mt5(self):

        path = self.config.get("path")
        
        if not mt5.initialize(path=path):
            raise RuntimeError(f"MT5 Initialize Failed: {mt5.last_error()}")

        authorized = mt5.login(
        login=self.config.get('login'),
        password=self.config.get('password'),
        server=self.config.get('server')
        )

        if not authorized:
            error = mt5.last_error()
            mt5.shutdown() # Close connection if login fails
            raise RuntimeError(f"MT5 Login failed for account {self.config['login']}: {error}")
        
        logger.info(f"Successfully logged into {self.config['server']} as {self.config['login']}")
    
    def manage_breakeven_and_drawdown(self, strategy):
        """
        Iterate over all open positions and move the stop loss to breakeven
        once the position has reached rr_ratio times the initial risk.

        Breakeven level includes a small commission buffer:
          - long  -> entry_price * 1.0005
          - short -> entry_price * 0.9995
        """
        open_positions = strategy.get_positions()
        if not open_positions:
            return

        if not hasattr(strategy, "entry_prices") or strategy.entry_prices is None:
            strategy.entry_prices = {}

        for position in open_positions:
            symbol = position.symbol
            current_price = strategy.get_last_price(symbol)
            if current_price is None:
                continue

            # Seed entry price from the fill price when not yet recorded
            if symbol not in strategy.entry_prices:
                strategy.entry_prices[symbol] = position.avg_fill_price

            entry_price = strategy.entry_prices[symbol]

            if position.side == "long":
                pnl = current_price - entry_price
                max_risk = abs(entry_price - position.stop_price) if position.stop_price else 0
                if max_risk > 0 and pnl >= (max_risk * strategy.rr_ratio):
                    breakeven_sl = entry_price * 1.0005
                    self.update_stop_loss(strategy, position, breakeven_sl)
                    strategy.log_message(
                        f"[BREAKEVEN] LONG {symbol}: Moved SL to breakeven {breakeven_sl:.5f}"
                    )

            elif position.side == "short":
                pnl = entry_price - current_price
                max_risk = abs(position.stop_price - entry_price) if position.stop_price else 0
                if max_risk > 0 and pnl >= (max_risk * strategy.rr_ratio):
                    breakeven_sl = entry_price * 0.9995
                    self.update_stop_loss(strategy, position, breakeven_sl)
                    strategy.log_message(
                        f"[BREAKEVEN] SHORT {symbol}: Moved SL to breakeven {breakeven_sl:.5f}"
                    )

    def update_stop_loss(self, strategy, position, new_stop_price):
        """Cancel the existing stop order for position and place a new one at new_stop_price."""
        symbol = position.symbol
        side = "sell" if position.side == "long" else "buy"
        try:
            for order in strategy.get_orders():
                if order.asset.symbol == symbol and order.status == "open":
                    if order.order_type == "stop" or (
                        hasattr(order, "stop_price") and order.stop_price is not None
                    ):
                        strategy.cancel_order(order)

            stop_order = strategy.create_order(
                symbol,
                position.quantity,
                side,
                order_type="stop",
                stop_price=new_stop_price,
            )
            strategy.submit_order(stop_order)
        except Exception as e:
            strategy.log_message(f"[ERROR] Failed to update SL for {symbol}: {e}")

    def is_daily_drawdown_halted(self, strategy, current_date):
        """
        Return True when the portfolio has lost more than max_daily_drawdown_pct
        of its value since the start of current_date, halting further trading for that day.
        """
        if strategy.last_trade_date != current_date:
            strategy.last_trade_date = current_date
            strategy.daily_equity_start = strategy.get_portfolio_value()
            return False

        if strategy.daily_equity_start is None:
            strategy.daily_equity_start = strategy.get_portfolio_value()
            return False

        current_equity = strategy.get_portfolio_value()
        max_loss = strategy.daily_equity_start * strategy.max_daily_drawdown_pct

        if current_equity <= (strategy.daily_equity_start - max_loss):
            return True

        return False

    def _get_balances_at_broker(self, *args, **kwargs):
        """
        This is the internal source for self.get_cash() 
        and self.get_portfolio_value()
        """
        account = mt5.account_info()
        if account is None:
            return 0.0, 0.0, 0.0
        
        cash = account.balance
        portfolio_value = account.equity
        position_value = portfolio_value - cash

        return cash, position_value, portfolio_value
    
    def _pull_positions(self, strategy=None, *args, **kwargs):
        """
        This is the source for self.get_positions() 
        and self.get_position(asset)
        """

        mt5_positions = mt5.positions_get()
        lumibot_positions = []

        if mt5_positions:
            for pos in mt5_positions:

                type = self.get_asset_type(pos.symbol)

                asset = Asset(symbol=pos.symbol, asset_type=type)

                lumibot_positions.append(Position(
                    strategy,
                    asset=asset,
                    quantity=pos.volume
                ))

                logger.info(f"TRACKED POSITION: {pos.symbol} | Quantity: {pos.volume} | Entry: {pos.price_open}")
        return lumibot_positions

    def get_last_price(self, asset, *args, **kwargs):
        """Fetches the last price from MT5."""
        symbol = self._symbol(asset)

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            logger.error(f"Could not get last price for {symbol}. Symbol might be wrong in MT5.")
            return None
        
        return tick.last if tick.last != 0 else (tick.bid + tick.ask) / 2
    
    def get_historical_prices(self, asset, length, timestep, *args, **kwargs):
        """Required for technical indicators and strategy logic"""

        tf_map = {"minute": mt5.TIMEFRAME_M1, "hour": mt5.TIMEFRAME_H1, "day": mt5.TIMEFRAME_D1}
        timeframe = tf_map.get(timestep)
        if timeframe is None:
            raise ValueError(f"Unsupported timestep: {timestep}. Use one of: {', '.join(tf_map.keys())}")

        symbol = self._symbol(asset)

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, length)

        if rates is None:
            raise RuntimeError(f"No rates returned for {symbol} ({timestep}). MT5 error: {mt5.last_error()}")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(self.timezone)
        df.set_index('time', inplace=True)
        return df

    def _normalize_volume(self, symbol, volume):
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0.0

        min_volume = float(getattr(info, "volume_min", 0.01) or 0.01)
        max_volume = float(getattr(info, "volume_max", 100.0) or 100.0)
        step = float(getattr(info, "volume_step", 0.01) or 0.01)
        if step <= 0:
            return 0.0

        if volume < min_volume:
            return 0.0

        capped = min(volume, max_volume)
        steps = int((capped - min_volume) / step)
        normalized = min_volume + (steps * step)
        precision = max(0, -Decimal(str(step)).as_tuple().exponent)
        return round(normalized, precision)

    def _is_exposure_reducing_order(self, symbol, side):
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return False

        has_same_side = False
        has_opposite_side = False
        requested_side = str(side).lower()

        for pos in positions:
            position_side = "buy" if int(pos.type) == mt5.POSITION_TYPE_BUY else "sell"
            if position_side == requested_side:
                has_same_side = True
            else:
                has_opposite_side = True

        return has_opposite_side and not has_same_side

    def _cap_volume_to_margin(self, symbol, side, requested_volume, reference_price):
        normalized_volume = self._normalize_volume(symbol, float(requested_volume))
        if normalized_volume <= 0:
            return 0.0

        account = mt5.account_info()
        if account is None:
            return normalized_volume

        free_margin = float(getattr(account, "margin_free", 0.0) or 0.0)
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL

        required_margin = mt5.order_calc_margin(order_type, symbol, normalized_volume, float(reference_price))
        if required_margin is None:
            return normalized_volume

        required_margin = float(required_margin)
        if required_margin <= free_margin:
            return normalized_volume

        if required_margin <= 0:
            return normalized_volume

        scaled_volume = normalized_volume * (free_margin / required_margin)
        return self._normalize_volume(symbol, scaled_volume)
    
    def _submit_order(self, order: Order):
        """Sends orders to MT5 and updates order status"""

        symbol = self._symbol(order.asset)

        order_class = str(getattr(order, "order_class", "")).lower()
        sl = getattr(order, "stop_loss_price", None)
        tp = getattr(order, "take_profit_price", None)

        # Strategies pass SL/TP as secondary_stop_price / secondary_limit_price.
        # Always prefer those over the legacy stop_price / limit_price attributes
        # so the values are populated for every order class.
        if sl is None:
            sl = getattr(order, "secondary_stop_price", None) or getattr(order, "stop_price", None)
        if tp is None:
            # For bracket orders limit_price is the take-profit level, not an entry
            # price, so use it as a fallback when secondary_limit_price is absent.
            tp = getattr(order, "secondary_limit_price", None) or (
                getattr(order, "limit_price", None) if order_class == "bracket" else None
            )

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            logger.error(f"ERROR: Could not get tick for {symbol}. Order aborted, but bot is still running.")
            order.status = "error"
            return order

        market_price = tick.ask if order.side == "buy" else tick.bid

        # Bracket orders must always be sent as immediate market deals with
        # attached SL/TP. If order_kind were left as "limit" (which Lumibot
        # sets whenever limit_price is present), the broker would try to place
        # a pending limit entry using the TP price as the entry level, which
        # is invalid and causes MT5 error 10013 (INVALID REQUEST).
        if order_class == "bracket":
            order_kind = "market"
        else:
            order_kind = str(getattr(order, "order_type", getattr(order, "type", "market"))).lower()

        # Lumibot may provide order.strategy as either the strategy object or its name string.
        if isinstance(order.strategy, str):
            strategy_name = order.strategy
        elif order.strategy is not None and hasattr(order.strategy, "name"):
            strategy_name = order.strategy.name
        else:
            strategy_name = "Unknown"
        magic_number = generate_magic_number(strategy_name)

        if order_kind == "limit":
            limit_price = float(getattr(order, "limit_price", 0.0) or 0.0)
            if limit_price <= 0:
                logger.error(f"MT5 ERROR: Missing valid limit_price for {symbol} limit order.")
                order.status = "error"
                return order

            requested_volume = self._normalize_volume(symbol, float(order.quantity))
            if requested_volume <= 0:
                logger.error(f"MT5 ERROR: Invalid lot size for {symbol}: {order.quantity}")
                order.status = "error"
                return order

            if self._is_exposure_reducing_order(symbol, order.side):
                volume = requested_volume
            else:
                volume = self._cap_volume_to_margin(symbol, order.side, requested_volume, limit_price)
            if volume <= 0:
                logger.error(f"MT5 ERROR: Not enough free margin for minimum lot on {symbol}.")
                order.status = "error"
                return order

            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "order_type": mt5.ORDER_TYPE_BUY_LIMIT if order.side == "buy" else mt5.ORDER_TYPE_SELL_LIMIT,
                "price": limit_price,
                "sl": float(sl) if sl else 0.0,
                "tp": float(tp) if tp else 0.0,
                "magic": magic_number,
                "comment": "Lumibot MT5 Limit Entry",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        else:
            requested_volume = self._normalize_volume(symbol, float(order.quantity))
            if requested_volume <= 0:
                logger.error(f"MT5 ERROR: Invalid lot size for {symbol}: {order.quantity}")
                order.status = "error"
                return order

            if self._is_exposure_reducing_order(symbol, order.side):
                volume = requested_volume
            else:
                volume = self._cap_volume_to_margin(symbol, order.side, requested_volume, market_price)
            if volume <= 0:
                logger.error(f"MT5 ERROR: Not enough free margin for minimum lot on {symbol}.")
                order.status = "error"
                return order

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "order_type": mt5.ORDER_TYPE_BUY if order.side == "buy" else mt5.ORDER_TYPE_SELL,
                "price": market_price,
                "sl": float(sl) if sl else 0.0,
                "tp": float(tp) if tp else 0.0,
                "magic": magic_number,
                "comment": "Lumibot MT5 Trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

        result = mt5.order_send(request)

        placed_retcode = getattr(mt5, "TRADE_RETCODE_PLACED", None)
        successful_retcodes = {mt5.TRADE_RETCODE_DONE}
        if placed_retcode is not None:
            successful_retcodes.add(placed_retcode)

        if result.retcode in successful_retcodes:
            order.identifier = result.order if result.order else result.deal
            order.status = "submitted" if order_kind == "limit" else "filled"
        else:
            logger.error(f"MT5 ERROR: {result.comment.upper()} | Code: {result.retcode}")
            order.status = "error"
        return order

    def get_datetime(self, *args, **kwargs):
        tz = pytz.timezone(self.timezone)
        return datetime.now(tz)
    
    def get_asset_type(self, symbol):
        info = mt5.symbol_info(symbol)

        if info is None:
            return "stock"
        
        path = info.path.lower()

        if "forex" in path:
            return "forex"
        elif "crypto" in path:
            return "crypto"
        elif "future" in path:
            return "future"
        elif "option" in path:
            return "option"
        else:
            return "stock"

    def _symbol(self, asset):
        symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)

        if symbol.endswith("M"):
            symbol = symbol[:-1] + "m"
        return symbol

    def select_symbol(self, asset):
        symbol = self._symbol(asset)

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"{symbol} not found on this MT5 account/server.")

        if not symbol_info.visible:
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                raise RuntimeError(f"Failed to select {symbol}. MT5 error: {mt5.last_error()}")
            symbol_info = mt5.symbol_info(symbol)

        logger.info(f"Symbol Enabled: {symbol_info.name} | {symbol_info.description}")
        return True

    def _get_stream_object(self): return None
    def _register_stream_events(self): pass
    def _run_stream(self): pass
    def _modify_order(self, order): pass
    def _pull_broker_order(self, identifier): return None
    def _pull_broker_all_orders(self): return []
    def _parse_broker_order(self, response): return None
    def _pull_position(self, asset): return None
    def _update_datetime(self, *args, **kwargs): pass
    def get_historical_account_value(self): return []
    def cancel_order(self, order):
        if order is None:
            return None

        order_id = getattr(order, "identifier", None)
        if not order_id:
            return None

        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(order_id),
            "comment": "Lumibot MT5 Cancel Pending",
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            order.status = "canceled"
        else:
            logger.error(f"MT5 CANCEL ERROR: {result.comment.upper()} | Code: {result.retcode}")
        return order
