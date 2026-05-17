"""매도 임계를 올려 익절까지 보유하게 하는 효과 검증.

가설: 현재 sell_score=3에서 너무 일찍 팔아서 큰 익절을 못 탄다.
sell_score 올리면 더 강한 매도 신호만 트리거 → 익절(15%)까지 보유 가능.
"""
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-ADA", "KRW-XRP"]
DAYS = 90


def main():
    print("매도 임계 + 익절 비율 조합 테스트\n", flush=True)
    print("데이터 로드...", flush=True)
    dfs = {}
    for sym in SYMBOLS:
        df = fetch_crypto(sym, "minute15", DAYS * 96)
        dfs[sym] = df
        print(f"  {sym}: {len(df)}봉", flush=True)

    bnh = {s: (d["close"].iloc[-1] - d["close"].iloc[100]) / d["close"].iloc[100] * 100
           for s, d in dfs.items()}
    print(f"\n단순보유: {bnh}\n", flush=True)

    # 기본: Bsc=5 R=3.0 (직전 그리드 최선) + 매도 임계 + 익절 조합
    combos = [
        # (sell_score, take_profit_pct, label)
        (3, 0.06,  "현재 (sell=3, TP=6%)"),
        (5, 0.15,  "매도 강화 (sell=5, TP=15%)"),
        (7, 0.15,  "매도 매우 강화 (sell=7, TP=15%)"),
        (7, 0.25,  "큰 익절 (sell=7, TP=25%)"),
        (99, 0.15, "매도 신호 무시 (TP/SL만, TP=15%)"),
        (99, 0.30, "매도 신호 무시 (TP=30%)"),
    ]

    t0 = time.time()
    for sell_score, tp, label in combos:
        rets = {}
        trade_counts = []
        for sym, df in dfs.items():
            bp = {"min_confidence": 0.5,
                  "take_profit_pct": tp,
                  "stop_loss_pct": 0.05}
            rule_p = {
                "buy_score_threshold": 5,
                "sell_score_threshold": sell_score,
                "resistance_filter_pct": 3.0,
                "downtrend_filter_rsi": None,
            }
            res = run_backtest(df, sym, "crypto", bp, rule_params=rule_p)
            rets[sym] = res["return_pct"]
            trade_counts.append(len(res["trades"]))

        avg = mean(rets.values())
        elapsed = time.time() - t0
        print(f"[{elapsed:>5.0f}s] {label}", flush=True)
        for s, r in rets.items():
            mark = "✅" if r > 0 else ("⚪" if r >= -0.5 else "❌")
            print(f"    {s}: {r:+6.2f}%  {mark}", flush=True)
        print(f"    → 평균 {avg:+.2f}%  거래 평균 {mean(trade_counts):.0f}건", flush=True)
        print(flush=True)


if __name__ == "__main__":
    main()
