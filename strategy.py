import datetime
import io
import backtrader as bt
import pandas as pd
import backtrader.feeds as btfeeds
from binance.client import Client
from pandas import DataFrame
from backtrader.feeds import PandasData
from statistics import fmean
from backtrader.order import Order
from utils.strategy_utils import IndicatorCalculation, CustomAnalyzer, MyBuySell


class GridStrategy(bt.Strategy):
    """Реалізація стратегії торгівлі по сітці."""
    params = (
        ('rsi_values', None),
        ('bollinger_bands_values', None),
        ('atr_values', None),
        ('deposit', 0),
        ('weeks', 0),
        ('log_buffer', None)
    )

    def __init__(self):
        self.rsi_values = self.params.rsi_values
        self.bollinger_bands_values = self.params.bollinger_bands_values
        self.atr_values = self.params.atr_values
        self.deposit = self.params.deposit
        self.weeks_n = self.params.weeks
        self.levels = None
        self.stop_loss = 0
        self.take_profit = 0
        self.stop_or_take_hit = False
        self.position_size = 0
        self.quantity_per_order = 0
        self.orders = set()
        self.grid_num = 0
        self.orders_executed = 0
        self.log_buffer = self.params.log_buffer

    def log(self, message):
        self.log_buffer.write((message + '\n').encode('utf-8'))

    def nextstart(self):
        lower_bound, upper_bound = self._calculate_range()
        self.levels = list(zip(*self._calculate_grid_levels(lower_bound, upper_bound)))
        self.position_size = self.deposit / self.grid_num

    def next(self):
        data = self.data[0]
        if not self.stop_or_take_hit:
            self.quantity_per_order = self.position_size / data
            for buy_price, sell_price in self.levels:
                if buy_price not in self.orders:
                    buy_order = self.buy(price=buy_price, size=self.quantity_per_order, exectype=bt.Order.StopLimit,
                                         transmit=False)
                    self.sell(price=sell_price, size=buy_order.size, exectype=bt.Order.StopLimit, parent=buy_order)
                    self.orders.add(buy_price)
                    self.log(f"New buy order at {buy_price} for {self.quantity_per_order} units.")
                    self.log(f"New sell order at {sell_price} for {self.quantity_per_order} units.")
        if data <= self.stop_loss or data >= self.take_profit:
            self.close()
            for order in self.broker.get_orders_open():
                self.cancel(order)
            self.stop_or_take_hit = True

    def notify_order(self, order: Order) -> None:
        if order.status == order.Completed and order.issell() and not self.stop_or_take_hit:
            buy_price, sell_price = next((b, s) for b, s in self.levels if s == order.price)
            new_buy_order = self.buy(price=buy_price, size=order.size, exectype=bt.Order.StopLimit,
                                     transmit=False)
            self.sell(price=sell_price,
                      size=new_buy_order.size, exectype=bt.Order.StopLimit, parent=new_buy_order)
            self.orders_executed += 1
            self.log(
                f"Buy order at {buy_price} executed. New buy order placed at {buy_price} for {-order.size} units.",
            )
            self.log(
                f"New sell order placed at {sell_price} for {order.size} units.")

    def _calculate_range(self) -> tuple[float, float]:
        """Розрахунок діапазону стратегії"""
        current_rsi = fmean(self.rsi_values)
        _, bb_top, bb_bot = self.bollinger_bands_values[-1]
        current_atr = self.atr_values[-1]
        data = self.data.close[0]
        STOP_PERCENT = 0.03
        TAKE_PERCENT = 0.06
        lower_bound = data - 2 * current_atr
        upper_bound = data + 2 * current_atr

        if current_rsi < 30:
            lower_bound -= current_atr
            upper_bound += 2 * current_atr
        elif current_rsi > 70:
            lower_bound -= 2 * current_atr
            upper_bound += current_atr

        distance_to_top = bb_top - data
        distance_to_bot = data - bb_bot

        multiplier = 1 + 0.01 * self.weeks_n
        lower_bound -= distance_to_bot * 0.5
        upper_bound += distance_to_top * 0.5

        upper_bound *= multiplier
        lower_bound /= multiplier

        self.stop_loss = lower_bound * (1 - STOP_PERCENT)
        self.take_profit = upper_bound * (1 + TAKE_PERCENT)
        return lower_bound, upper_bound

    def _calculate_grid_levels(self,
                               lower_bound: float,
                               upper_bound: float,
                               step_percentage: float = 0.02,
                               profit_percentage: float = 0.03) -> tuple[list[float], list[float]]:
        """Розрахунок рівнів сітки"""
        range_width = upper_bound - lower_bound
        step = range_width * step_percentage
        num_levels = int(range_width / step)

        buy_levels = [lower_bound + i * step for i in range(num_levels)]
        sell_levels = [price * (1 + profit_percentage) for price in buy_levels]
        self.grid_num = len(buy_levels)
        return buy_levels, sell_levels

    def get_log(self):
        return self.log_buffer


class Controller:
    """Контролер для управління процесом бектестування."""
    def __init__(self, start_date: str, end_date: str, symbol: str, deposit: int, api_key, secret_key):
        self.api_key = api_key
        self.api_secret = secret_key
        self.start_date = start_date
        self.end_date = end_date
        self.symbol = symbol
        self.deposit = deposit
        self.data_indicators, self.data_strategy = self._prepare_test_data()

    def _prepare_test_data(self) -> tuple[PandasData, PandasData]:
        """Підготовка даних"""
        df_indicators, df_strategy = self._fetch_historical_data(self.api_key,
                                                                self.api_secret,
                                                                self.symbol,
                                                                self.start_date,
                                                                self.end_date)
        data_indicators = self._dataframe_to_backtrader(df_indicators)
        data_strategy = self._dataframe_to_backtrader(df_strategy)
        return data_indicators, data_strategy

    def _calculate_range_weeks(self) -> int:
        """Розрахунок кількісті тижнів в діапазоні"""
        date_start_obj = datetime.datetime.strptime(self.start_date, '%Y-%m-%d')
        date_end_obj = datetime.datetime.strptime(self.end_date, '%Y-%m-%d')
        days_difference = (date_end_obj - date_start_obj).days
        weeks_difference = days_difference // 7
        return max(1, weeks_difference)

    @staticmethod
    def _fetch_historical_data(api_key: str,
                              api_secret: str,
                              symbol: str,
                              start_date: str,
                              end_date: str) -> tuple[DataFrame, DataFrame]:
        """Взяття історичних данних і приведення їх до потрібної форми"""
        indicators_start_date = (pd.to_datetime(start_date) - pd.Timedelta(weeks=2)).strftime('%Y-%m-%d')
        client = Client(api_key, api_secret)
        klines_combined = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1HOUR, indicators_start_date,
                                                       end_date)

        df_combined = pd.DataFrame(klines_combined, columns=['timestamp', 'open', 'high',
                                                             'low', 'close', 'volume',
                                                             'close_time', 'quote_asset_volume', 'number_of_trades',
                                                             'taker_buy_base', 'taker_buy_quote', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df_combined[col] = pd.to_numeric(df_combined[col])
        df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], unit='ms')
        df_combined.set_index('timestamp', inplace=True)
        df_indicators = df_combined[df_combined.index < start_date]
        df_strategy = df_combined[df_combined.index >= start_date]
        return df_indicators, df_strategy

    @staticmethod
    def _dataframe_to_backtrader(dataframe: DataFrame) -> PandasData:
        """Утиліта для приведення даних"""
        datafeed = btfeeds.PandasData(dataname=dataframe,
                                      datetime=-1,
                                      open=-1,
                                      high=-1,
                                      low=-1,
                                      close=-1,
                                      volume=-1,
                                      openinterest=-1)
        return datafeed

    def _compute_indicators(self) -> None:
        """Запуск cerebro для розрахунку індикаторів"""
        cerebro = bt.Cerebro()
        cerebro.adddata(self.data_indicators)
        cerebro.addstrategy(IndicatorCalculation)
        results = cerebro.run()
        strategy_instance = results[0]
        self.rsi_values = strategy_instance.get_rsi_values()
        self.bb_v = strategy_instance.get_bollinger_bands_values()
        self.atr_v = strategy_instance.get_atr_values()

    @staticmethod
    def _calculate_drawdown(analyzer):
        max_dd = round(analyzer.max.drawdown, 2)
        max_md = round(analyzer.max.moneydown, 2)
        return {'Max drawdown (%)': max_dd,
                'Max drawdown ($)': max_md}

    @staticmethod
    def _saveplots(cerebro, numfigs=1, iplot=True, start=None, end=None,
                  width=16, height=9, dpi=300, tight=True, use=None, file_path='', **kwargs):

        from backtrader import plot
        if cerebro.p.oldsync:
            plotter = plot.Plot_OldSync(**kwargs)
        else:
            plotter = plot.Plot(**kwargs)

        figs = []
        for stratlist in cerebro.runstrats:
            for si, strat in enumerate(stratlist):
                rfig = plotter.plot(strat, figid=si * 100,
                                    numfigs=numfigs, iplot=iplot,
                                    start=start, end=end, use=use)
                figs.append(rfig)

        # for fig in figs:
        #     for f in fig:
        #         f.savefig(file_path, bbox_inches='tight')
        # return figs
        images_bytes = []
        for fig in figs:
            for f in fig:
                buf = io.BytesIO()
                f.savefig(buf, format='png', bbox_inches='tight')
                images_bytes.append(buf)
        return images_bytes[-1]

    def _run_strategy(self) -> tuple[dict[str, float], io.BytesIO, io.BytesIO]:
        """Запуск основної стратегії"""
        order_buff = io.BytesIO()
        weeks_n = self._calculate_range_weeks()
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_stats")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
        cerebro.addanalyzer(CustomAnalyzer)
        cerebro.adddata(self.data_strategy)
        cerebro.addstrategy(GridStrategy,
                            rsi_values=self.rsi_values,
                            bollinger_bands_values=self.bb_v,
                            atr_values=self.atr_v,
                            deposit=self.deposit,
                            weeks=weeks_n,
                            log_buffer=order_buff)
        cerebro.addobserver(MyBuySell, bardist=0)
        cerebro.addobserver(bt.observers.Broker)
        cerebro.broker.setcash(self.deposit)
        results = cerebro.run()[0]
        analysis = results.analyzers.customanalyzer.get_analysis()
        drawdown_info = results.analyzers.dd.get_analysis()
        analysis.update(self._calculate_drawdown(drawdown_info))
        plot_buff = self._saveplots(cerebro, file_path='plot.png', style='candlestick')
        return analysis, plot_buff, order_buff

    def run(self) -> tuple[dict[str, float], io.BytesIO, io.BytesIO]:
        """Запуск роботи індикаторів та основної стратегії"""
        self._compute_indicators()
        data = self._run_strategy()
        return data
