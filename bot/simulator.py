import time
import logging
import os
from datetime import datetime
from core.upbit import UpbitClient
from strategy.analyzer import TechnicalAnalyzer
from strategy.rule_decision import RuleBasedDecisionMaker
from strategy.decision_log import log_decision
from risk.manager import RiskManager
from config import TRADING, RISK

logger = logging.getLogger(__name__)

INITIAL_KRW = 1_000_000  # 모의 시작 자금 100만원


class SimulationBot:
    """API 키 없이 실제 업비트 시세로 모의투자"""

    def __init__(self):
        self.upbit = UpbitClient()  # 시세 조회만 (인증 불필요)
        self.analyzer = TechnicalAnalyzer()
        self.ai, self.strategy_name = self._load_decision_maker()
        self.risk = RiskManager()

        # 가상 포트폴리오
        self.krw_balance = INITIAL_KRW
        self.holdings: dict = {}  # symbol -> {volume, avg_price}
        self.trade_log: list = []
        self.started_at = datetime.now()

    def _load_decision_maker(self):
        force_rule = os.getenv("USE_RULE_STRATEGY", "").lower() in ("1", "true", "yes")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and not force_rule:
            try:
                from strategy.ai_decision import AIDecisionMaker
                logger.info("Claude AI 전략 사용")
                return AIDecisionMaker(), "ai"
            except Exception:
                pass
        logger.info("규칙 기반 전략 사용" + (" (강제)" if force_rule else " (Claude API 키 없음)"))
        return RuleBasedDecisionMaker(), "rule"

    # ── 자산 계산 ──────────────────────────────────────────

    def get_total_assets(self) -> float:
        total = self.krw_balance
        for symbol, h in self.holdings.items():
            price = self.upbit.get_current_price(symbol) or h["avg_price"]
            total += h["volume"] * price
        return total

    def get_portfolio(self) -> list:
        rows = []
        for symbol, h in self.holdings.items():
            price = self.upbit.get_current_price(symbol) or h["avg_price"]
            pnl_pct = (price - h["avg_price"]) / h["avg_price"] * 100 if h["avg_price"] else 0
            rows.append({
                "symbol": symbol,
                "volume": h["volume"],
                "avg_price": h["avg_price"],
                "current_price": price,
                "value": h["volume"] * price,
                "pnl_pct": pnl_pct,
            })
        return rows

    def get_total_return_pct(self) -> float:
        return (self.get_total_assets() - INITIAL_KRW) / INITIAL_KRW * 100

    # ── 가상 매수/매도 ──────────────────────────────────────

    def _virtual_buy(self, symbol: str, amount_krw: float, price: float, reason: str):
        if self.krw_balance < amount_krw:
            amount_krw = self.krw_balance
        if amount_krw < TRADING["min_order_krw"]:
            return

        fee = amount_krw * 0.0005  # 업비트 수수료 0.05%
        net_krw = amount_krw - fee
        volume = net_krw / price

        self.krw_balance -= amount_krw
        self.holdings[symbol] = {"volume": volume, "avg_price": price}
        self.risk.open_position(symbol, volume, price)

        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "buy",
            "symbol": symbol,
            "price": price,
            "amount": amount_krw,
            "volume": volume,
            "reason": reason,
        }
        self.trade_log.append(entry)
        logger.info(f"[매수] {symbol} | {amount_krw:,.0f}원 | {volume:.6f}개 @ {price:,} | {reason}")

    def _virtual_sell(self, symbol: str, reason: str):
        h = self.holdings.pop(symbol, None)
        if not h:
            return
        price = self.upbit.get_current_price(symbol) or h["avg_price"]
        proceeds = h["volume"] * price
        fee = proceeds * 0.0005
        net = proceeds - fee
        pnl_pct = (price - h["avg_price"]) / h["avg_price"] * 100 if h["avg_price"] else 0

        self.krw_balance += net
        self.risk.close_position(symbol, price)

        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "sell",
            "symbol": symbol,
            "price": price,
            "amount": net,
            "volume": h["volume"],
            "pnl_pct": pnl_pct,
            "reason": reason,
        }
        self.trade_log.append(entry)
        logger.info(f"[매도] {symbol} | {pnl_pct:+.2f}% | {net:,.0f}원 | {reason}")

    # ── 분석 & 결정 ─────────────────────────────────────────

    def analyze_and_trade(self, symbol: str):
        try:
            df = self.upbit.get_ohlcv(symbol, interval=f"minute{TRADING['candle_interval']}", count=100)
            indicators = self.analyzer.analyze(df)
            if not indicators:
                return

            current_price = indicators["current_price"]
            holding = self.holdings.get(symbol)
            position = {"volume": holding["volume"], "avg_price": holding["avg_price"],
                        "profit_pct": self.risk.get_profit_pct(symbol, current_price)} if holding else None

            # 손절/익절 우선
            if holding:
                if self.risk.should_stop_loss(symbol, current_price):
                    self._virtual_sell(symbol, f"손절 (-{RISK['stop_loss_pct']*100:.0f}%)")
                    return
                if self.risk.should_take_profit(symbol, current_price):
                    self._virtual_sell(symbol, f"익절 (+{RISK['take_profit_pct']*100:.0f}%)")
                    return

            # AI 판단
            decision = self.ai.decide(symbol, "crypto", indicators, position)
            action = decision["action"]
            confidence = decision["confidence"]
            reason = decision.get("reason", "")

            log_decision(
                symbol=symbol,
                market_type="crypto",
                strategy=self.strategy_name,
                indicators=indicators,
                decision=decision,
                position=position,
                price=current_price,
                mode="sim",
            )

            logger.info(
                f"[{symbol}] {'매수' if action=='buy' else '매도' if action=='sell' else '홀드'} "
                f"| 신뢰도 {confidence:.0%} | {reason}"
            )

            min_confidence = 0.45 if not os.getenv("ANTHROPIC_API_KEY") else 0.6
            if confidence < min_confidence:
                return

            total = self.get_total_assets()
            if action == "buy" and not holding:
                can, msg = self.risk.can_open_position(symbol, total)
                if not can:
                    logger.info(f"[{symbol}] 매수 불가: {msg}")
                    return
                amount = self.risk.calc_order_amount(
                    self.krw_balance, confidence, decision.get("suggested_position_pct", 0.15)
                )
                self._virtual_buy(symbol, amount, current_price, reason)

            elif action == "sell" and holding:
                self._virtual_sell(symbol, reason)

        except Exception as e:
            logger.error(f"[{symbol}] 오류: {e}")

    def run_once(self):
        for symbol in TRADING["crypto_symbols"]:
            self.analyze_and_trade(symbol)
            time.sleep(1)

    def run(self):
        logger.info(f"모의투자 시작 | 초기자금: {INITIAL_KRW:,}원 | 종목: {TRADING['crypto_symbols']}")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"루프 오류: {e}")
            time.sleep(TRADING["analysis_interval"])
