import backtrader as bt
from backtrader.indicators import RSI, BollingerBands, ATR


class MyBuySell(bt.observers.BuySell):
    """Кастомний обсервер"""
    plotlines = dict(
        buy=dict(markersize=10.0, color='lime'),
        sell=dict(markersize=10.0, color='blue')
    )


class CustomAnalyzer(bt.Analyzer):
    """Аналізатор для обчислення основних статистичних даних стратегії."""
    def start(self):
        self.start_cash = self.strategy.broker.get_cash()

    def stop(self):
        self.final_cash = self.strategy.broker.get_cash()
        self.final_portfolio_value = self.strategy.broker.get_value()
        self.total_profit_loss_percent = 100 * (self.final_portfolio_value - self.start_cash) / self.start_cash
        self.total_profit_loss_cash = self.final_portfolio_value - self.start_cash
        self.total_trades = self.strategy.orders_executed

    def get_analysis(self) -> dict[str, float | int]:
        return {
            "Profit/Loss (%)": self.total_profit_loss_percent,
            "Profit/Loss ($)": self.total_profit_loss_cash,
            "Total Trades": self.total_trades
        }


class IndicatorCalculation(bt.Strategy):
    """Стратегія для обчислення технічних індикаторів."""
    def __init__(self):
        self.rsi = RSI(self.data.close, period=14)
        self.bollinger_bands = BollingerBands(self.data.close, period=14)
        self.atr = ATR(self.data, period=14)
        self.rsi_values = []
        self.bb_v = []
        self.atr_values = []

    def next(self):
        self.rsi_values.append(self.rsi[0])
        self.bb_v.append((self.bollinger_bands.lines.mid[0],
                          self.bollinger_bands.lines.top[0],
                          self.bollinger_bands.lines.bot[0]))
        self.atr_values.append(self.atr[0])

    def get_rsi_values(self) -> list[float]:
        return self.rsi_values

    def get_bollinger_bands_values(self) -> list[tuple[float, float, float]]:
        return self.bb_v

    def get_atr_values(self) -> list[float]:
        return self.atr_values