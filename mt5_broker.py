import MetaTrader5 as mt5
import pandas as pd
from lumibot.brokers import Broker
from lumibot.entities import Asset, Position, Order

from datetime import datetime
import pytz
import zlib

def generate_magic_number(strategy_name):
    return zlib.adler32(strategy_name.encode()) & 0xFFFFFFFF

class MetaTrader5(Broker):

    def __init__(self, config):
        super().__init__(name="MT5", data_source=self)
        self.SOURCE = "PANDAS"
        self.config = config
        self.timezone = self.config.get("timezone", "Africa/Lagos")
        self._breakeven_entries = {}
        self._breakeven_moved = {}
        self._daily_drawdown = {}
        self._initialize_mt5()

    def _strategy_key(self, strategy):
        if strategy is None:
            return "default"
        if isinstance(strategy, str):
            return strategy
        return getattr(strategy, "name", strategy.__class__.__name__)

    def _ensure_strategy_state(self, strategy):
        key = self._strategy_key(strategy)
        if key not in self._breakeven_entries:
            self._breakeven_entries[key] = {}
        if key not in self._breakeven_moved:
            self._breakeven_moved[key] = set()
        if key not in self._daily_drawdown:
            self._daily_drawdown[key] = {
                "date": None,
                "equity_start": None,
                "realized_pnl": 0.0,
                "halted": False,
            }
        return key

    def register_entry_for_breakeven(self, strategy, asset, side, entry_price, risk_distance):
        key = self._ensure_strategy_state(strategy)
        symbol = self._symbol(asset)
        self._breakeven_entries[key][symbol] = {
            "entry_price": float(entry_price),
            "risk_distance": float(risk_distance),
            "side": side,
        }
        self._breakeven_moved[key].discard(symbol)

    def cleanup_breakeven_tracking(self, strategy, open_positions):
        key = self._ensure_strategy_state(strategy)
        open_symbols = {
            self._symbol(position.asset)
            for position in open_positions
            if position.asset is not None
        }
        for symbol in list(self._breakeven_entries[key].keys()):
            if symbol not in open_symbols:
                self._breakeven_entries[key].pop(symbol, None)
                self._breakeven_moved[key].discard(symbol)

    def move_stop_to_price(self, asset, entry_side, stop_price):
        symbol = self._symbol(asset)
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            raise RuntimeError(f"No open positions found for {symbol} to move stop-loss.")

        expected_type = mt5.POSITION_TYPE_BUY if entry_side == "buy" else mt5.POSITION_TYPE_SELL
        for pos in positions:
            if int(pos.type) != expected_type:
                continue
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": int(pos.ticket),
                "sl": float(stop_price),
                "tp": float(pos.tp) if pos.tp else 0.0,
                "magic": int(pos.magic),
                "comment": "Lumibot MT5 Breakeven Move",
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise RuntimeError(
                    f"Failed to move stop for {symbol} position {pos.ticket}: {result.comment} ({result.retcode})"
                )

    def manage_breakeven_positions(self, strategy, open_positions, get_last_price):
        key = self._ensure_strategy_state(strategy)
        for position in open_positions:
            if position.asset is None:
                continue

            symbol = self._symbol(position.asset)
            trade_info = self._breakeven_entries[key].get(symbol)
            if not trade_info or symbol in self._breakeven_moved[key]:
                continue

            current_price = get_last_price(position.asset)
            if current_price is None:
                continue

            entry_price = trade_info["entry_price"]
            risk_distance = trade_info["risk_distance"]
            side = trade_info["side"]

            trigger_hit = (
                current_price >= (entry_price + risk_distance)
                if side == "buy"
                else current_price <= (entry_price - risk_distance)
            )
            if not trigger_hit:
                continue

            breakeven_stop = entry_price * 1.0005 if side == "buy" else entry_price * 0.9995
            self.move_stop_to_price(position.asset, side, breakeven_stop)
            self._breakeven_moved[key].add(symbol)

    def reset_daily_drawdown(self, strategy, current_date, equity_start):
        key = self._ensure_strategy_state(strategy)
        self._daily_drawdown[key] = {
            "date": current_date,
            "equity_start": float(equity_start) if equity_start is not None else None,
            "realized_pnl": 0.0,
            "halted": False,
        }

    def is_daily_drawdown_halted(self, strategy, current_date, equity_start, max_daily_drawdown_pct):
        key = self._ensure_strategy_state(strategy)
        state = self._daily_drawdown[key]

        if state["date"] != current_date:
            self.reset_daily_drawdown(strategy, current_date, equity_start)
            state = self._daily_drawdown[key]

        if state["equity_start"] is None and equity_start is not None:
            state["equity_start"] = float(equity_start)

        if state["equity_start"] is None or state["equity_start"] <= 0:
            return False, state["realized_pnl"], 0.0

        max_loss = state["equity_start"] * float(max_daily_drawdown_pct)
        if state["realized_pnl"] <= -max_loss:
            state["halted"] = True
        return state["halted"], state["realized_pnl"], max_loss

    def handle_filled_order_risk(
        self, strategy, position, order, price, quantity, multiplier, open_positions,
        current_date, equity_start, max_daily_drawdown_pct
    ):
        key = self._ensure_strategy_state(strategy)
        state = self._daily_drawdown[key]

        if state["date"] != current_date:
            self.reset_daily_drawdown(strategy, current_date, equity_start)
            state = self._daily_drawdown[key]

        symbol = None
        if order is not None and getattr(order, "asset", None) is not None:
            symbol = self._symbol(order.asset)
        elif position is not None and getattr(position, "asset", None) is not None:
            symbol = self._symbol(position.asset)

        if symbol is None:
            return

        tracked_trade = self._breakeven_entries[key].get(symbol)
        order_side = str(getattr(order, "side", "")).lower()

        if tracked_trade and tracked_trade.get("side") in {"buy", "sell"} and price is not None and quantity is not None:
            entry_side = tracked_trade["side"]
            closing_side = "sell" if entry_side == "buy" else "buy"
            if order_side == closing_side:
                closed_qty = abs(float(quantity))
                fill_multiplier = float(multiplier) if multiplier is not None else 1.0
                if entry_side == "buy":
                    realized_pnl = (float(price) - tracked_trade["entry_price"]) * closed_qty * fill_multiplier
                else:
                    realized_pnl = (tracked_trade["entry_price"] - float(price)) * closed_qty * fill_multiplier
                state["realized_pnl"] += realized_pnl
                self.is_daily_drawdown_halted(strategy, current_date, equity_start, max_daily_drawdown_pct)

        self.cleanup_breakeven_tracking(strategy, open_positions)

    def _initialize_mt5(self):

        path = self.config.get("path")
        
        if not mt5.initialize(path=path, portable=True):
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
        
        print(f"Successfully logged into {self.config['server']} as {self.config['login']}")
    
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

                print(f"TRACKED POSITION: {pos.symbol} | Quantity: {pos.volume} | Entry: {pos.price_open}")
        return lumibot_positions

    def get_last_price(self, asset, *args, **kwargs):
        """Fetches the last price from MT5."""
        symbol = self._symbol(asset)

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            print(f"Could not get last price for {symbol}. Symbol might be wrong in MT5.")
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
    
    def _submit_order(self, order: Order):
        """Sends orders to MT5 and updates order status"""

        symbol = self._symbol(order.asset)

        sl = order.stop_loss_price
        tp = order.take_profit_price
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            print(f"ERROR: Could not get tick for {symbol}. Order aborted, but bot is still running.")
            order.status = "error"
            return order

        price = tick.ask if order.side == "buy" else tick.bid

        # Lumibot may provide order.strategy as either the strategy object or its name string.
        if isinstance(order.strategy, str):
            strategy_name = order.strategy
        elif order.strategy is not None and hasattr(order.strategy, "name"):
            strategy_name = order.strategy.name
        else:
            strategy_name = "Unknown"
        magic_number = generate_magic_number(strategy_name)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(order.quantity),
            "order_type": mt5.ORDER_TYPE_BUY if order.side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "magic": magic_number,
            "comment": "Lumibot MT5 Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            order.identifier = result.order
            order.status = "filled"
        else:
            print(f"MT5 ERROR: {result.comment.upper()} | Code: {result.retcode}")
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

        print(f"Symbol Enabled: {symbol_info.name} | {symbol_info.description}")
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
    def cancel_order(self, order): return None
