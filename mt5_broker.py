import MetaTrader5 as mt5
import pandas as pd
from lumibot.brokers import Broker
from lumibot.entities import Position, Order

class MetaTrader5(Broker):
    def __init__(self, config):
        super().__init__(name="MT5", data_source=self)
        self.config = config
        self._initialize_mt5()

    def _initialize_mt5(self):

        if not mt5.initialize():
            raise RuntimeError(f"MT5 Initialize Failed: {mt5.last_error()}")

        # authorized = mt5.login(
        # login=self.config.get('login'),
        # password=self.config.get('password'),
        # server=self.config.get('server')
        # )

        # if not authorized:
        #     error = mt5.last_error()
        #     mt5.shutdown() # Close connection if login fails
        #     raise RuntimeError(f"MT5 Login failed for account {self.config['login']}: {error}")
        
        # print(f"Successfully logged into {self.config['server']} as {self.config['login']}")
    
    def _get_balances_at_broker(self):
        """
        This is the internal source for self.get_cash() 
        and self.get_portfolio_value()
        """
        account = mt5.account_info()
        if account is None:
            return {"cash": 0.0, "equity": 0.0}
        return {
            "cash": account.balance,
            "equity": account.equity
        }
    
    def _pull_positions(self):
        """
        This is the source for self.get_positions() 
        and self.get_position(asset)
        """

        mt5_positions = mt5.positions_get()
        lumibot_positions = []

        if mt5_positions:
            for p in mt5_positions:
                lumibot_positions.append(Position(
                    strategy_name=self.name,
                    symbol=p.symbol,
                    quantity=p.volume,
                    entry_price=p.price_open
                ))
        return lumibot_positions
        
    def get_last_price(self, asset):
        """Standard price fetcher for current tick data"""

        tick = mt5.symbol_info_tick(asset.symbol)
        if tick:
            return tick.last if tick.last != 0 else (tick.bid + tick.ask) / 2
        return None
    
    def get_historical_prices(self, asset, length, timestep="minute"):
        """Required for technical indicators and strategy logic"""

        tf_map = {"minute": mt5.TIMEFRAME_M1, "hour": mt5.TIMEFRAME_H1, "day": mt5.TIMEFRAME_D1}
        timeframe = tf_map.get(timestep)
        if timeframe is None:
            raise ValueError(f"Unsupported timestep: {timestep}. Use one of: {', '.join(tf_map.keys())}")

        rates = mt5.copy_rates_from_pos(asset.symbol, timeframe, 0, length)

        if rates is None:
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df.rename(columns={'real_volume': 'volume'}, inplace=True)
        
        return df
    
    def _submit_order(self, order: Order):
        """Sends orders to MT5 and updates order status"""

        symbol = order.asset.symbol
        sl = order.stop_loss_price
        tp = order.take_profit_price
        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            raise RuntimeError(f"No tick data available for symbol: {symbol}")

        price = tick.ask if order.side == "buy" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(order.quantity),
            "type": mt5.ORDER_TYPE_BUY if order.side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "magic": 199020,
            "comment": "Lumibot MT5 Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            order.identifier = result.order
            order.status = "filled"
        else:
            print(f"MT5 Order Error: {result.comment}")
            order.status = "failed"
        return order
    
    def _get_stream_object(self): return None
    def _register_stream_events(self): pass
    def _run_stream(self): pass
    def _modify_order(self, order): pass
    def _pull_broker_order(self, identifier): return None
    def _pull_broker_all_orders(self): return []
    def _parse_broker_order(self, response): return None
    def _pull_position(self, asset): return None
    def get_historical_account_value(self): return []
    def cancel_order(self, order): pass