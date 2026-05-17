import time
import logging
from datetime import datetime
from core.upbit import UpbitClient
from core.bithumb import BithumbClient
from core.kis import KISClient
from strategy.analyzer import TechnicalAnalyzer
from strategy.ai_decision import AIDecisionMaker
from strategy.decision_log import log_decision
from risk.manager import RiskManager
from config import TRADING, RISK

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.upbit = UpbitClient()
        self.bithumb = BithumbClient()
        self.kis = KISClient()
        self.analyzer = TechnicalAnalyzer()
        self.ai = AIDecisionMaker()
        self.risk = RiskManager()
        self.trade_log: list = []

    # ── 자산 조회 ──────────────────────────────────────────────

    def get_total_assets(self) -> float:
        try:
            krw = float(self.upbit.get_balance("KRW") or 0)
        except Exception:
            krw = 0
        return krw

    def get_crypto_position(self, ticker: str) -> dict:
        try:
            currency = ticker.replace("KRW-", "")
            volume = float(self.upbit.get_balance(currency) or 0)
            avg_price = float(self.upbit.get_avg_buy_price(ticker) or 0)
            current_price = self.upbit.get_current_price(ticker) or 0
            profit_pct = (current_price - avg_price) / avg_price * 100 if avg_price else 0
            return {"volume": volume, "avg_price": avg_price, "profit_pct": profit_pct}
        except Exception:
            return {"volume": 0, "avg_price": 0, "profit_pct": 0}

    # ── 코인 트레이딩 ────────────────────────────────────────

    def analyze_crypto(self, ticker: str) -> dict:
        df = self.upbit.get_ohlcv(ticker, interval=f"minute{TRADING['candle_interval']}", count=100)
        return self.analyzer.analyze(df)

    def trade_crypto(self, ticker: str):
        try:
            indicators = self.analyze_crypto(ticker)
            if not indicators:
                return

            position = self.get_crypto_position(ticker)
            if position["volume"] > 0:
                self.risk.open_position(ticker, position["volume"], position["avg_price"])

            current_price = indicators["current_price"]

            # 손절/익절 우선 체크
            if self.risk.should_stop_loss(ticker, current_price):
                self._execute_crypto_sell(ticker, position["volume"], current_price, "손절")
                return
            if self.risk.should_take_profit(ticker, current_price):
                self._execute_crypto_sell(ticker, position["volume"], current_price, "익절")
                return

            # AI 판단
            decision = self.ai.decide(ticker, "crypto", indicators, position)
            log_decision(
                symbol=ticker,
                market_type="crypto",
                strategy="ai",
                indicators=indicators,
                decision=decision,
                position=position,
                price=current_price,
                mode="live" if not self.dry_run else "dry",
            )
            self._log_decision(ticker, decision, current_price)

            if decision["confidence"] < 0.6:
                return

            action = decision["action"]
            total_assets = self.get_total_assets()

            if action == "buy" and position["volume"] == 0:
                can_open, reason = self.risk.can_open_position(ticker, total_assets)
                if not can_open:
                    logger.info(f"[{ticker}] 매수 불가: {reason}")
                    return
                amount = self.risk.calc_order_amount(
                    total_assets, decision["confidence"], decision.get("suggested_position_pct", 0.1)
                )
                if amount >= TRADING["min_order_krw"]:
                    self._execute_crypto_buy(ticker, amount, current_price, decision["reason"])

            elif action == "sell" and position["volume"] > 0:
                self._execute_crypto_sell(ticker, position["volume"], current_price, decision["reason"])

        except Exception as e:
            logger.error(f"[{ticker}] 코인 트레이딩 오류: {e}")

    def _execute_crypto_buy(self, ticker: str, amount: float, price: float, reason: str):
        log_entry = {
            "time": datetime.now().isoformat(),
            "market": "crypto",
            "symbol": ticker,
            "action": "buy",
            "price": price,
            "amount": amount,
            "reason": reason,
            "dry_run": self.dry_run,
        }
        if not self.dry_run:
            result = self.upbit.buy_market_order(ticker, amount)
            log_entry["result"] = result
            estimated_volume = amount / price
            self.risk.open_position(ticker, estimated_volume, price)
        logger.info(f"{'[모의]' if self.dry_run else '[실거래]'} 매수 {ticker} {amount:,.0f}원 @ {price:,} | {reason}")
        self.trade_log.append(log_entry)

    def _execute_crypto_sell(self, ticker: str, volume: float, price: float, reason: str):
        log_entry = {
            "time": datetime.now().isoformat(),
            "market": "crypto",
            "symbol": ticker,
            "action": "sell",
            "price": price,
            "volume": volume,
            "reason": reason,
            "dry_run": self.dry_run,
        }
        if not self.dry_run:
            result = self.upbit.sell_market_order(ticker, volume)
            log_entry["result"] = result
            self.risk.close_position(ticker, price)
        logger.info(f"{'[모의]' if self.dry_run else '[실거래]'} 매도 {ticker} {volume} @ {price:,} | {reason}")
        self.trade_log.append(log_entry)

    # ── 주식 트레이딩 ────────────────────────────────────────

    def analyze_stock(self, code: str) -> dict:
        import pandas as pd
        raw = self.kis.get_ohlcv(code, period="D", count=100)
        if not raw:
            return {}
        rows = []
        for r in raw:
            try:
                rows.append({
                    "open": float(r.get("stck_oprc", 0)),
                    "high": float(r.get("stck_hgpr", 0)),
                    "low": float(r.get("stck_lwpr", 0)),
                    "close": float(r.get("stck_clpr", 0)),
                    "volume": float(r.get("acml_vol", 0)),
                })
            except Exception:
                continue
        if not rows:
            return {}
        df = pd.DataFrame(rows[::-1])
        return self.analyzer.analyze(df)

    def trade_stock(self, code: str):
        try:
            price_info = self.kis.get_current_price(code)
            current_price = price_info["price"]
            if not current_price:
                return

            indicators = self.analyze_stock(code)
            if not indicators:
                return
            indicators["current_price"] = current_price

            position = self.risk.get_position(code)
            decision = self.ai.decide(code, "stock", indicators, position if position else None)
            log_decision(
                symbol=code,
                market_type="stock",
                strategy="ai",
                indicators=indicators,
                decision=decision,
                position=position if position else None,
                price=current_price,
                mode="live" if not self.dry_run else "dry",
            )
            self._log_decision(code, decision, current_price)

            if decision["confidence"] < 0.65:
                return

            action = decision["action"]
            total_assets = self.get_total_assets()

            if action == "buy" and not position:
                can_open, reason = self.risk.can_open_position(code, total_assets)
                if not can_open:
                    logger.info(f"[{code}] 매수 불가: {reason}")
                    return
                amount = self.risk.calc_order_amount(
                    total_assets, decision["confidence"], decision.get("suggested_position_pct", 0.1)
                )
                qty = int(amount // current_price)
                if qty > 0:
                    self._execute_stock_buy(code, qty, current_price, decision["reason"])

            elif action == "sell" and position:
                qty = position.get("volume", 0)
                if qty > 0:
                    self._execute_stock_sell(code, int(qty), current_price, decision["reason"])

            # 보유 중 손절/익절
            if position:
                if self.risk.should_stop_loss(code, current_price):
                    self._execute_stock_sell(code, int(position["volume"]), current_price, "손절")
                elif self.risk.should_take_profit(code, current_price):
                    self._execute_stock_sell(code, int(position["volume"]), current_price, "익절")

        except Exception as e:
            logger.error(f"[{code}] 주식 트레이딩 오류: {e}")

    def _execute_stock_buy(self, code: str, qty: int, price: float, reason: str):
        log_entry = {
            "time": datetime.now().isoformat(),
            "market": "stock",
            "symbol": code,
            "action": "buy",
            "price": price,
            "qty": qty,
            "reason": reason,
            "dry_run": self.dry_run,
        }
        if not self.dry_run:
            result = self.kis.buy_order(code, qty)
            log_entry["result"] = result
            self.risk.open_position(code, qty, price)
        logger.info(f"{'[모의]' if self.dry_run else '[실거래]'} 매수 {code} {qty}주 @ {price:,} | {reason}")
        self.trade_log.append(log_entry)

    def _execute_stock_sell(self, code: str, qty: int, price: float, reason: str):
        log_entry = {
            "time": datetime.now().isoformat(),
            "market": "stock",
            "symbol": code,
            "action": "sell",
            "price": price,
            "qty": qty,
            "reason": reason,
            "dry_run": self.dry_run,
        }
        if not self.dry_run:
            result = self.kis.sell_order(code, qty)
            log_entry["result"] = result
            self.risk.close_position(code, price)
        logger.info(f"{'[모의]' if self.dry_run else '[실거래]'} 매도 {code} {qty}주 @ {price:,} | {reason}")
        self.trade_log.append(log_entry)

    # ── 메인 루프 ────────────────────────────────────────────

    def run_once(self):
        logger.info(f"=== 분석 시작 {datetime.now().strftime('%H:%M:%S')} ===")

        for ticker in TRADING["crypto_symbols"]:
            self.trade_crypto(ticker)
            time.sleep(0.5)

        for code in TRADING["stock_symbols"]:
            self.trade_stock(code)
            time.sleep(0.5)

    def run(self):
        logger.info(f"트레이딩 봇 시작 ({'모의투자' if self.dry_run else '실거래'} 모드)")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("봇 종료")
                break
            except Exception as e:
                logger.error(f"메인 루프 오류: {e}")
            time.sleep(TRADING["analysis_interval"])

    def _log_decision(self, symbol: str, decision: dict, price: float):
        action_emoji = {"buy": "🟢 매수", "sell": "🔴 매도", "hold": "⚪ 홀드"}.get(decision["action"], "?")
        logger.info(
            f"[{symbol}] {action_emoji} | 신뢰도: {decision.get('confidence', 0):.0%} | "
            f"리스크: {decision.get('risk_level', '?')} | {decision.get('reason', '')}"
        )
