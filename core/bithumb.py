import pybithumb
import pandas as pd
from config import BITHUMB_API_KEY, BITHUMB_SECRET_KEY


class BithumbClient:
    def __init__(self):
        self.client = None
        if BITHUMB_API_KEY and BITHUMB_SECRET_KEY:
            self.client = pybithumb.Bithumb(BITHUMB_API_KEY, BITHUMB_SECRET_KEY)

    def get_balance(self, ticker="KRW"):
        if not self.client:
            return 0
        return self.client.get_balance(ticker)

    def get_current_price(self, ticker: str) -> float:
        # ticker 예: "BTC", "ETH"
        return pybithumb.get_current_price(ticker)

    def get_ohlcv(self, ticker: str, interval: str = "minute15", count: int = 100) -> pd.DataFrame:
        return pybithumb.get_ohlcv(ticker, interval=interval, count=count)

    def get_orderbook(self, ticker: str) -> dict:
        return pybithumb.get_orderbook(ticker)

    def buy_market_order(self, ticker: str, price: float):
        if not self.client:
            raise RuntimeError("API 키가 설정되지 않았습니다")
        return self.client.buy_market_order(ticker, price)

    def sell_market_order(self, ticker: str, units: float):
        if not self.client:
            raise RuntimeError("API 키가 설정되지 않았습니다")
        return self.client.sell_market_order(ticker, units)

    def normalize_ticker(self, upbit_ticker: str) -> str:
        """KRW-BTC → BTC"""
        return upbit_ticker.replace("KRW-", "")
