"""익절/손절/점수 임계 + 저항선 필터를 6종목 평균으로 그리드 평가.

목표: '평균 수익률 양수' + '단순보유 평균에 가깝거나 이김' 조합 찾기.
"""
import itertools
import json
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE", "KRW-ADA"]
DAYS = 90


def main():
    print(f"확장 그리드 — 6종목 × {DAYS}일\n")
    print("데이터 로드...")
    dfs = {}
    for sym in SYMBOLS:
        df = fetch_crypto(sym, "minute15", DAYS * 96)
        if df is not None and len(df) >= 200:
            dfs[sym] = df
    print(f"로드 완료: {list(dfs.keys())}\n")

    # 단순보유 평균 (비교 기준)
    bnh_per_sym = {}
    for sym, df in dfs.items():
        bnh_per_sym[sym] = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
    bnh_mean = mean(bnh_per_sym.values())
    print(f"단순보유 평균: {bnh_mean:+.2f}%\n")

    # 그리드 — 핵심 4축
    grid = {
        "take_profit_pct": [0.06, 0.10, 0.15, 0.25],   # 현재 6%, 키워서 트렌드 타기
        "stop_loss_pct":   [0.03, 0.05, 0.08],          # 현재 3%, 손절 여유
        "buy_score_threshold": [4, 5, 6],               # 현재 4, 더 강한 신호만
        "resistance_filter_pct": [1.5, 3.0],            # 1.5 vs 3.0
    }
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"조합 수: {len(combos)} (각 6종목 백테스트)\n")

    rows = []
    for i, combo in enumerate(combos, 1):
        p = dict(zip(keys, combo))
        rets = []
        alphas = []
        trade_counts = []
        win_rates = []
        for sym, df in dfs.items():
            bp = {"min_confidence": 0.5,
                  "take_profit_pct": p["take_profit_pct"],
                  "stop_loss_pct": p["stop_loss_pct"]}
            rule_p = {"buy_score_threshold": p["buy_score_threshold"],
                      "resistance_filter_pct": p["resistance_filter_pct"]}
            res = run_backtest(df, sym, "crypto", bp, rule_params=rule_p)
            trades = res["trades"]
            sells = [t for t in trades if t["side"] == "sell"]
            wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
            rets.append(res["return_pct"])
            alphas.append(res["return_pct"] - bnh_per_sym[sym])
            trade_counts.append(len(trades))
            if sells:
                win_rates.append(len(wins) / len(sells) * 100)

        rows.append({
            "params": p,
            "mean_return": mean(rets),
            "median_return": median(rets),
            "mean_alpha": mean(alphas),
            "mean_trades": mean(trade_counts),
            "mean_win_rate": mean(win_rates) if win_rates else None,
            "best_return": max(rets),
            "worst_return": min(rets),
        })

    # 평균 수익률 기준 정렬
    rows.sort(key=lambda r: r["mean_return"], reverse=True)

    print(f"{'='*120}")
    print(f"{'#':>3} {'평균수익':>9} {'중간수익':>9} {'평균알파':>9} {'최선':>8} {'최악':>8} {'거래':>5} {'승률':>6}  파라미터 (TP/SL/Bsc/R)")
    print(f"{'='*120}")
    for i, r in enumerate(rows[:20], 1):
        p = r["params"]
        wr = f"{r['mean_win_rate']:.0f}%" if r["mean_win_rate"] else "  —"
        ps = f"TP={p['take_profit_pct']*100:.0f}% SL={p['stop_loss_pct']*100:.0f}% Bsc={p['buy_score_threshold']} R={p['resistance_filter_pct']}"
        print(f"{i:>3} {r['mean_return']:+7.2f}% {r['median_return']:+7.2f}% {r['mean_alpha']:+7.2f}% "
              f"{r['best_return']:+6.2f}% {r['worst_return']:+6.2f}% {r['mean_trades']:>5.0f} {wr:>6}  {ps}")
    print(f"\n... 총 {len(rows)}개 중 상위 20개\n")
    print(f"단순보유 평균: {bnh_mean:+.2f}%")
    print(f"기준: 평균수익률 = 6종목 평균 (양수면 평균적으로 돈 벌었음)")

    Path("logs").mkdir(exist_ok=True)
    with open("logs/profit_grid_result.json", "w", encoding="utf-8") as f:
        json.dump({"bnh_mean": bnh_mean, "results": rows}, f, ensure_ascii=False, default=str, indent=2)
    print(f"\n저장: logs/profit_grid_result.json")


if __name__ == "__main__":
    main()
