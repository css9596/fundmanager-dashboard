import pyupbit
import pandas as pd
from config import UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY


class UpbitClient:
    def __init__(self):
        self.client = None
        if UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY:
            self.client = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)

    def get_balance(self, ticker="KRW"):
        if not self.client:
            return 0
        return self.client.get_balance(ticker)

    def get_all_balances(self):
        if not self.client:
            return {}
        balances = self.client.get_balances()
        return {b["currency"]: float(b["balance"]) for b in balances if float(b["balance"]) > 0}

    def get_current_price(self, ticker: str) -> float:
        return pyupbit.get_current_price(ticker)

    def get_ohlcv(self, ticker: str, interval: str = "minute15", count: int = 100) -> pd.DataFrame:
        return pyupbit.get_ohlcv(ticker, interval=interval, count=count)

    def get_orderbook(self, ticker: str) -> dict:
        return pyupbit.get_orderbook(ticker)

    def buy_market_order(self, ticker: str, price: float):
        if not self.client:
            raise RuntimeError("API 키가 설정되지 않았습니다")
        return self.client.buy_market_order(ticker, price)

    def sell_market_order(self, ticker: str, volume: float):
        if not self.client:
            raise RuntimeError("API 키가 설정되지 않았습니다")
        return self.client.sell_market_order(ticker, volume)

    def get_avg_buy_price(self, ticker: str) -> float:
        if not self.client:
            return 0
        currency = ticker.replace("KRW-", "")
        return self.client.get_avg_buy_price(currency)
