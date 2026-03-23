import MetaTrader5 as mt5
import pandas as pd
from lumibot.brokers import Broker
from lumibot.entities import Asset, Position, Order

from datetime import datetime, timedelta
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
        self._initialize_mt5()

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
        df['time'] = pd.to_datetime(df['time'], unit='s')
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
    def cancel_order(self, order): pass
