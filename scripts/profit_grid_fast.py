"""빠른 익절/손절/임계 그리드 — 핵심 조합만, 진행상황 출력."""
import itertools
import json
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-ADA", "KRW-XRP"]  # 강세 2 + 약세 2
DAYS = 90


def main():
    print(f"빠른 그리드: {len(SYMBOLS)}종목 × {DAYS}일", flush=True)
    print("데이터 로드...", flush=True)
    dfs = {}
    for sym in SYMBOLS:
        df = fetch_crypto(sym, "minute15", DAYS * 96)
        if df is not None and len(df) >= 200:
            dfs[sym] = df
            print(f"  {sym}: {len(df)}봉", flush=True)

    bnh = {s: (d["close"].iloc[-1] - d["close"].iloc[100]) / d["close"].iloc[100] * 100
           for s, d in dfs.items()}
    bnh_mean = mean(bnh.values())
    print(f"\n단순보유 평균: {bnh_mean:+.2f}%\n", flush=True)

    # 좁힌 그리드
    grid = {
        "take_profit_pct": [0.06, 0.15, 0.30],
        "stop_loss_pct":   [0.03, 0.05],
        "buy_score_threshold": [4, 5],
        "resistance_filter_pct": [1.5, 3.0],
    }
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"조합 수: {len(combos)} × {len(SYMBOLS)}종목 = {len(combos)*len(SYMBOLS)} 백테스트\n", flush=True)

    rows = []
    t0 = time.time()
    for i, combo in enumerate(combos, 1):
        p = dict(zip(keys, combo))
        rets = {}
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
            rets[sym] = res["return_pct"]
            trade_counts.append(len(trades))
            if sells:
                win_rates.append(len(wins) / len(sells) * 100)

        ret_vals = list(rets.values())
        rows.append({
            "params": p,
            "per_symbol": rets,
            "mean_return": mean(ret_vals),
            "best": max(ret_vals),
            "worst": min(ret_vals),
            "trades": mean(trade_counts),
            "win_rate": mean(win_rates) if win_rates else None,
        })
        elapsed = time.time() - t0
        print(f"  [{i:2d}/{len(combos)}] TP={p['take_profit_pct']*100:.0f}% SL={p['stop_loss_pct']*100:.0f}% "
              f"Bsc={p['buy_score_threshold']} R={p['resistance_filter_pct']} "
              f"→ 평균 {mean(ret_vals):+.2f}%  ({elapsed:.0f}s)", flush=True)

    rows.sort(key=lambda r: r["mean_return"], reverse=True)

    print(f"\n{'='*110}")
    print(f"{'#':>3} {'평균':>7} {'최선':>7} {'최악':>7} {'거래':>5} {'승률':>5}  파라미터")
    print(f"{'='*110}")
    for i, r in enumerate(rows, 1):
        p = r["params"]
        wr = f"{r['win_rate']:.0f}%" if r["win_rate"] else " —"
        ps = f"TP={p['take_profit_pct']*100:>3.0f}% SL={p['stop_loss_pct']*100:>2.0f}% Bsc={p['buy_score_threshold']} R={p['resistance_filter_pct']}"
        print(f"{i:>3} {r['mean_return']:+6.2f}% {r['best']:+6.2f}% {r['worst']:+6.2f}% "
              f"{r['trades']:>5.0f} {wr:>5}  {ps}")

    print(f"\n단순보유 평균: {bnh_mean:+.2f}%")

    Path("logs").mkdir(exist_ok=True)
    with open("logs/profit_grid_result.json", "w", encoding="utf-8") as f:
        json.dump({"bnh_mean": bnh_mean, "results": rows}, f, ensure_ascii=False, default=str, indent=2)


if __name__ == "__main__":
    main()
