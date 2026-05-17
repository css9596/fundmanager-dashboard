"""규칙 기반 전략 백테스터.

과거 OHLCV 데이터로 rule_decision을 돌려 매매 시뮬레이션 수행.
사용법:
    python3 scripts/backtest.py KRW-BTC --days 30 --interval minute15
    python3 scripts/backtest.py 005930 --market stock --days 90
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pyupbit

from strategy.analyzer import TechnicalAnalyzer
from strategy.rule_decision import RuleBasedDecisionMaker
from config import RISK, TRADING

FEE = 0.0005   # 매매수수료 (편도)
INITIAL_KRW = 1_000_000


def fetch_crypto(symbol: str, interval: str, count: int) -> pd.DataFrame:
    """pyupbit는 내부적으로 분할 호출을 처리해줌. 단일 호출로 충분."""
    return pyupbit.get_ohlcv(symbol, interval=interval, count=count)


def fetch_stock(symbol: str, count: int) -> pd.DataFrame:
    from core.kis import KISClient
    kis = KISClient()
    raw = kis.get_ohlcv(symbol, period="D", count=count)
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
    return pd.DataFrame(rows[::-1])


def run_backtest(df: pd.DataFrame, symbol: str, market_type: str, params: dict,
                 rule_params: dict = None):
    analyzer = TechnicalAnalyzer()
    rule = RuleBasedDecisionMaker(rule_params)

    krw = INITIAL_KRW
    position = None   # {"volume", "avg_price", "entry_idx"}
    trades = []       # {"side", "i", "price", "volume", "amount", "pnl_pct", "reason"}
    equity_curve = []

    window = 100  # analyzer 최소 데이터
    for i in range(window, len(df)):
        sub = df.iloc[i - window:i + 1].reset_index(drop=True)
        indicators = analyzer.analyze(sub)
        if not indicators:
            continue
        price = float(sub["close"].iloc[-1])

        pos_for_decision = None
        if position:
            profit_pct = (price - position["avg_price"]) / position["avg_price"] * 100
            pos_for_decision = {
                "volume": position["volume"],
                "avg_price": position["avg_price"],
                "profit_pct": profit_pct,
            }

        # 손절/익절 우선
        if position:
            profit_pct = (price - position["avg_price"]) / position["avg_price"]
            if profit_pct <= -RISK["stop_loss_pct"]:
                _close(position, price, "손절", trades, i)
                krw += position["volume"] * price * (1 - FEE)
                position = None
                equity_curve.append((i, krw))
                continue
            if profit_pct >= RISK["take_profit_pct"]:
                _close(position, price, "익절", trades, i)
                krw += position["volume"] * price * (1 - FEE)
                position = None
                equity_curve.append((i, krw))
                continue

        decision = rule.decide(symbol, market_type, indicators, pos_for_decision)
        action = decision["action"]
        confidence = decision["confidence"]
        if confidence < params["min_confidence"]:
            equity_curve.append((i, _equity(krw, position, price)))
            continue

        if action == "buy" and position is None:
            position_pct = params.get("position_pct", 0.20)
            cap = params.get("cap_krw")   # None이면 캡 없음 (백테스트 기본)
            amount = krw * position_pct
            if cap:
                amount = min(amount, cap)
            if amount < TRADING["min_order_krw"]:
                equity_curve.append((i, _equity(krw, position, price)))
                continue
            net = amount * (1 - FEE)
            volume = net / price
            krw -= amount
            position = {"volume": volume, "avg_price": price, "entry_idx": i}
            trades.append({"side": "buy", "i": i, "price": price, "volume": volume,
                           "amount": amount, "reason": decision["reason"]})

        elif action == "sell" and position is not None:
            _close(position, price, decision["reason"], trades, i)
            krw += position["volume"] * price * (1 - FEE)
            position = None

        equity_curve.append((i, _equity(krw, position, price)))

    final_price = float(df["close"].iloc[-1])
    final_equity = _equity(krw, position, final_price)
    return {
        "initial": INITIAL_KRW,
        "final": final_equity,
        "return_pct": (final_equity - INITIAL_KRW) / INITIAL_KRW * 100,
        "trades": trades,
        "equity_curve": equity_curve,
        "buy_hold_return_pct": (final_price - float(df["close"].iloc[window])) / float(df["close"].iloc[window]) * 100,
    }


def _close(position, price, reason, trades, i):
    pnl_pct = (price - position["avg_price"]) / position["avg_price"] * 100
    trades.append({"side": "sell", "i": i, "price": price, "volume": position["volume"],
                   "amount": position["volume"] * price, "pnl_pct": pnl_pct, "reason": reason})


def _equity(krw, position, price):
    if position is None:
        return krw
    return krw + position["volume"] * price


def summarize(result):
    trades = result["trades"]
    sells = [t for t in trades if t["side"] == "sell"]
    wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
    losses = [t for t in sells if t.get("pnl_pct", 0) <= 0]
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

    # MDD
    eq = [e[1] for e in result["equity_curve"]]
    peak, mdd = eq[0] if eq else 0, 0
    for v in eq:
        if v > peak:
            peak = v
        dd = (v - peak) / peak * 100 if peak else 0
        if dd < mdd:
            mdd = dd

    print(f"\n{'=' * 60}")
    print(f"백테스트 결과")
    print(f"{'=' * 60}")
    print(f"초기 자금: {result['initial']:,}원")
    print(f"최종 자금: {result['final']:,.0f}원")
    print(f"수익률   : {result['return_pct']:+.2f}%")
    print(f"단순보유  : {result['buy_hold_return_pct']:+.2f}%  (비교 기준)")
    print(f"최대낙폭  : {mdd:.2f}%")
    print()
    print(f"총 거래: {len(trades)}건 (매수 {len(trades)-len(sells)}, 매도 {len(sells)})")
    print(f"승률   : {len(wins)/len(sells)*100:.1f}%" if sells else "승률: 거래 없음")
    print(f"평균 익 : {avg_win:+.2f}%")
    print(f"평균 손 : {avg_loss:+.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", help="KRW-BTC 또는 005930")
    ap.add_argument("--market", choices=["crypto", "stock"], default="crypto")
    ap.add_argument("--days", type=int, default=30, help="크립토는 분봉 환산, 주식은 일봉")
    ap.add_argument("--interval", default="minute15", help="크립토 분봉 간격")
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--save", help="JSON 결과 저장 경로")
    args = ap.parse_args()

    print(f"백테스트: {args.symbol} ({args.market}) / 기간 {args.days}일 / 간격 {args.interval}")

    if args.market == "crypto":
        bars_per_day = {"minute1": 1440, "minute5": 288, "minute15": 96, "minute60": 24, "day": 1}
        count = bars_per_day.get(args.interval, 96) * args.days
        df = fetch_crypto(args.symbol, args.interval, count)
    else:
        df = fetch_stock(args.symbol, args.days)

    if df is None or df.empty or len(df) < 120:
        print(f"데이터 부족: {len(df) if df is not None else 0}개")
        return

    print(f"데이터: {len(df)}봉 ({df.index[0]} ~ {df.index[-1]})")

    result = run_backtest(df, args.symbol, args.market, {"min_confidence": args.min_confidence})
    summarize(result)

    if args.save:
        out = {
            "symbol": args.symbol, "market": args.market, "days": args.days,
            "interval": args.interval, "min_confidence": args.min_confidence,
            "summary": {
                "initial": result["initial"], "final": result["final"],
                "return_pct": result["return_pct"],
                "buy_hold_return_pct": result["buy_hold_return_pct"],
            },
            "trades": result["trades"],
            "equity_curve": result["equity_curve"],
        }
        os.makedirs(os.path.dirname(args.save) or ".", exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, default=str)
        print(f"\n결과 저장: {args.save}")


if __name__ == "__main__":
    main()
