"""핵심 파라미터 조합을 모든 종목에 적용해 평균 성과 비교.

목적: 한 종목에 과적합 안 된, '모든 종목에서 평균적으로 괜찮은' 파라미터 찾기.
"""
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE", "KRW-ADA"]
DAYS = 90

# 후보 파라미터
CANDIDATES = {
    "현재기본(BTC 최적)": {"resistance_filter_pct": 1.5, "downtrend_filter_rsi": None},
    "ADA 최적":          {"resistance_filter_pct": 3.0, "downtrend_filter_rsi": 35},
    "중간A":             {"resistance_filter_pct": 2.0, "downtrend_filter_rsi": 35},
    "중간B":             {"resistance_filter_pct": 2.5, "downtrend_filter_rsi": None},
    "보수적":             {"resistance_filter_pct": 3.0, "downtrend_filter_rsi": None},
}


def main():
    print(f"6종목 × {DAYS}일 × 5조합 평가\n")

    # 데이터 미리 로드
    print("데이터 로드 중...")
    dfs = {}
    for sym in SYMBOLS:
        df = fetch_crypto(sym, "minute15", DAYS * 96)
        if df is not None and len(df) >= 200:
            dfs[sym] = df
            print(f"  {sym}: {len(df)}봉")
    print()

    rows = []
    for name, params in CANDIDATES.items():
        alphas = []
        rets = []
        wins = []
        trade_counts = []
        for sym, df in dfs.items():
            bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
            res = run_backtest(df, sym, "crypto", {"min_confidence": 0.5}, rule_params=params)
            trades = res["trades"]
            sells = [t for t in trades if t["side"] == "sell"]
            win = [t for t in sells if t.get("pnl_pct", 0) > 0]
            alphas.append(res["return_pct"] - bnh)
            rets.append(res["return_pct"])
            trade_counts.append(len(trades))
            if sells:
                wins.append(len(win) / len(sells) * 100)

        rows.append({
            "name": name,
            "params": params,
            "mean_return": mean(rets),
            "mean_alpha": mean(alphas),
            "median_alpha": median(alphas),
            "mean_trades": mean(trade_counts),
            "mean_win_rate": mean(wins) if wins else None,
            "worst_alpha": min(alphas),
            "best_alpha": max(alphas),
        })

    print(f"{'='*100}")
    print(f"{'조합':>18} {'평균수익률':>10} {'평균알파':>10} {'중간알파':>10} {'최악알파':>10} {'최선알파':>10} {'평균거래':>8} {'평균승률':>8}")
    print(f"{'='*100}")
    rows.sort(key=lambda r: r["mean_alpha"], reverse=True)
    for r in rows:
        wr = f"{r['mean_win_rate']:.0f}%" if r["mean_win_rate"] else "  —"
        print(f"{r['name']:>18} {r['mean_return']:+8.2f}% {r['mean_alpha']:+8.2f}% "
              f"{r['median_alpha']:+8.2f}% {r['worst_alpha']:+8.2f}% {r['best_alpha']:+8.2f}% "
              f"{r['mean_trades']:>7.0f} {wr:>8}")

    print()
    print("기준: 평균 알파 (= 매매 - 단순보유의 평균)")
    print("긍정 = 평균적으로 단순보유보다 좋음")


if __name__ == "__main__":
    main()
