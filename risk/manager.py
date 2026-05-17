import time
from datetime import datetime, date
from config import RISK


class RiskManager:
    def __init__(self):
        self.daily_pnl = 0.0
        self.daily_reset_date = date.today()
        self.open_positions: dict = {}  # symbol -> {volume, avg_price, entry_time}

    def _reset_daily_if_needed(self):
        if date.today() != self.daily_reset_date:
            self.daily_pnl = 0.0
            self.daily_reset_date = date.today()

    def can_open_position(self, symbol: str, total_assets: float) -> tuple[bool, str]:
        self._reset_daily_if_needed()

        if len(self.open_positions) >= RISK["max_open_positions"]:
            return False, f"최대 동시 포지션 수({RISK['max_open_positions']})에 도달"

        if self.daily_pnl / total_assets < -RISK["max_daily_loss_pct"]:
            return False, f"일일 최대 손실({RISK['max_daily_loss_pct']*100:.0f}%) 도달 - 오늘 거래 중단"

        if symbol in self.open_positions:
            return False, "이미 해당 종목 포지션 보유 중"

        return True, "OK"

    def calc_order_amount(self, total_assets: float, confidence: float, suggested_pct: float) -> float:
        base_pct = min(suggested_pct, RISK["max_position_pct"])
        adjusted_pct = base_pct * confidence
        adjusted_pct = max(0.05, min(adjusted_pct, RISK["max_position_pct"]))
        amount = total_assets * adjusted_pct
        cap = RISK.get("max_position_krw")
        if cap:
            amount = min(amount, cap)
        return amount

    def should_stop_loss(self, symbol: str, current_price: float) -> bool:
        pos = self.open_positions.get(symbol)
        if not pos:
            return False
        loss_pct = (current_price - pos["avg_price"]) / pos["avg_price"]
        return loss_pct <= -RISK["stop_loss_pct"]

    def should_take_profit(self, symbol: str, current_price: float) -> bool:
        pos = self.open_positions.get(symbol)
        if not pos:
            return False
        profit_pct = (current_price - pos["avg_price"]) / pos["avg_price"]
        return profit_pct >= RISK["take_profit_pct"]

    def get_profit_pct(self, symbol: str, current_price: float) -> float:
        pos = self.open_positions.get(symbol)
        if not pos or not pos["avg_price"]:
            return 0.0
        return (current_price - pos["avg_price"]) / pos["avg_price"] * 100

    def open_position(self, symbol: str, volume: float, avg_price: float):
        self.open_positions[symbol] = {
            "volume": volume,
            "avg_price": avg_price,
            "entry_time": time.time(),
        }

    def close_position(self, symbol: str, exit_price: float):
        pos = self.open_positions.pop(symbol, None)
        if pos and pos["avg_price"]:
            pnl_pct = (exit_price - pos["avg_price"]) / pos["avg_price"]
            self.daily_pnl += pnl_pct
        return pos

    def get_position(self, symbol: str) -> dict:
        return self.open_positions.get(symbol, {})

    def get_status(self) -> dict:
        self._reset_daily_if_needed()
        return {
            "open_positions": len(self.open_positions),
            "daily_pnl_pct": round(self.daily_pnl * 100, 2),
            "positions": list(self.open_positions.keys()),
        }
