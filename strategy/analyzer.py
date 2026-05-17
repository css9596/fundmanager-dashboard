import pandas as pd
import numpy as np


class TechnicalAnalyzer:
    def analyze(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < 20:
            return {}

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        return {
            "rsi": self._rsi(close),
            "macd": self._macd(close),
            "bollinger": self._bollinger(close),
            "trend": self._trend(close),
            "volume_signal": self._volume_signal(volume),
            "support_resistance": self._support_resistance(high, low, close),
            "current_price": float(close.iloc[-1]),
            "price_change_1h": self._price_change(close, 4),   # 4 * 15분 = 1시간
            "price_change_4h": self._price_change(close, 16),
            "price_change_24h": self._price_change(close, 96),
        }

    def _rsi(self, close: pd.Series, period: int = 14) -> dict:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        value = float(rsi.iloc[-1])
        return {
            "value": round(value, 2),
            "signal": "oversold" if value < 30 else "overbought" if value > 70 else "neutral",
        }

    def _macd(self, close: pd.Series) -> dict:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        macd_val = float(macd_line.iloc[-1])
        signal_val = float(signal_line.iloc[-1])
        hist_val = float(histogram.iloc[-1])
        prev_hist = float(histogram.iloc[-2]) if len(histogram) > 1 else 0

        cross = "golden" if prev_hist < 0 and hist_val > 0 else "dead" if prev_hist > 0 and hist_val < 0 else "none"
        return {
            "macd": round(macd_val, 4),
            "signal": round(signal_val, 4),
            "histogram": round(hist_val, 4),
            "cross": cross,
            "bullish": macd_val > signal_val,
        }

    def _bollinger(self, close: pd.Series, period: int = 20) -> dict:
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + 2 * std
        lower = sma - 2 * std

        price = float(close.iloc[-1])
        upper_val = float(upper.iloc[-1])
        lower_val = float(lower.iloc[-1])
        mid_val = float(sma.iloc[-1])
        band_width = (upper_val - lower_val) / mid_val if mid_val else 0

        pct_b = (price - lower_val) / (upper_val - lower_val) if (upper_val - lower_val) else 0.5
        position = "above_upper" if price > upper_val else "below_lower" if price < lower_val else "middle"

        return {
            "upper": round(upper_val, 2),
            "middle": round(mid_val, 2),
            "lower": round(lower_val, 2),
            "pct_b": round(pct_b, 3),
            "band_width": round(band_width, 4),
            "position": position,
        }

    def _trend(self, close: pd.Series) -> dict:
        ema5 = float(close.ewm(span=5).mean().iloc[-1])
        ema20 = float(close.ewm(span=20).mean().iloc[-1])
        ema60 = float(close.ewm(span=60).mean().iloc[-1]) if len(close) >= 60 else ema20

        direction = "up" if ema5 > ema20 > ema60 else "down" if ema5 < ema20 < ema60 else "sideways"
        return {
            "ema5": round(ema5, 2),
            "ema20": round(ema20, 2),
            "ema60": round(ema60, 2),
            "direction": direction,
        }

    def _volume_signal(self, volume: pd.Series) -> dict:
        avg_vol = float(volume.rolling(20).mean().iloc[-1])
        cur_vol = float(volume.iloc[-1])
        ratio = cur_vol / avg_vol if avg_vol else 1
        return {
            "current": round(cur_vol),
            "average": round(avg_vol),
            "ratio": round(ratio, 2),
            "surge": ratio > 1.5,
        }

    def _support_resistance(self, high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
        recent_high = float(high.tail(20).max())
        recent_low = float(low.tail(20).min())
        price = float(close.iloc[-1])
        dist_to_resistance = (recent_high - price) / price * 100
        dist_to_support = (price - recent_low) / price * 100
        return {
            "resistance": round(recent_high, 2),
            "support": round(recent_low, 2),
            "dist_to_resistance_pct": round(dist_to_resistance, 2),
            "dist_to_support_pct": round(dist_to_support, 2),
        }

    def _price_change(self, close: pd.Series, periods: int) -> float:
        if len(close) <= periods:
            return 0
        old = float(close.iloc[-periods - 1])
        now = float(close.iloc[-1])
        return round((now - old) / old * 100, 2) if old else 0
