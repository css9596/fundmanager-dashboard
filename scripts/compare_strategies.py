"""전략 비교 — 기본 / 트레일링 / 추세 가중치 / 종합."""
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]


VARIANTS = {
    "기본":            {"trailing_pct": None},
    "트레일링 5%":      {"trailing_pct": 0.05},
    "트레일링 10%":     {"trailing_pct": 0.10},
    "큰익절+트레일링":   {"trailing_pct": 0.05, "take_profit_pct": 0.30},  # TP를 트레일링 활성화 트리거로 사용
}


def evaluate(dfs, variant_params, label, period_label):
    rows = []
    for sym, df in dfs.items():
        bnh_start = df["close"].iloc[100]
        bnh = (df["close"].iloc[-1] - bnh_start) / bnh_start * 100

        from config import RISK
        bp = {"min_confidence": 0.5,
              "take_profit_pct": variant_params.get("take_profit_pct", RISK["take_profit_pct"]),
              "stop_loss_pct": RISK["stop_loss_pct"],
              "trailing_pct": variant_params.get("trailing_pct")}
        res = run_backtest(df, sym, "crypto", bp)
        trades = res["trades"]
        sells = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
        rows.append({
            "sym": sym, "bnh": bnh, "ret": res["return_pct"],
            "alpha": res["return_pct"] - bnh,
            "trades": len(trades),
            "wr": len(wins)/len(sells)*100 if sells else 0,
        })

    avg_ret = mean(r["ret"] for r in rows)
    avg_bnh = mean(r["bnh"] for r in rows)
    print(f"  [{label:>15s}] 매매 {avg_ret:+6.2f}% / 단순보유 {avg_bnh:+6.2f}% / 알파 {avg_ret-avg_bnh:+6.2f}%p / "
          f"거래 {mean(r['trades'] for r in rows):.0f}건 / 승률 {mean(r['wr'] for r in rows):.0f}%", flush=True)
    return {"label": label, "rows": rows, "avg_ret": avg_ret, "avg_bnh": avg_bnh, "avg_alpha": avg_ret-avg_bnh}


def main():
    # 일봉 500일 (약세장)
    print("=== 일봉 500일 (약세장 환경) ===", flush=True)
    dfs_day = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in SYMBOLS}
    dfs_day = {s: d for s, d in dfs_day.items() if d is not None and len(d) >= 200}
    results_day = []
    for label, params in VARIANTS.items():
        results_day.append(evaluate(dfs_day, params, label, "일봉 500일"))
    print()

    # 분봉 90일 (강세장)
    print("=== 분봉 15m 90일 (강세장 환경) ===", flush=True)
    dfs_min = {s: fetch_crypto(s, "minute15", 90*96) for s in SYMBOLS}
    dfs_min = {s: d for s, d in dfs_min.items() if d is not None and len(d) >= 200}
    results_min = []
    for label, params in VARIANTS.items():
        results_min.append(evaluate(dfs_min, params, label, "분봉 90일"))
    print()

    # 요약
    print("=== 종합 비교 ===")
    print(f"{'전략':>15s}  {'일봉500':>12s}  {'분봉90':>12s}  {'평균알파':>10s}")
    for r_day, r_min in zip(results_day, results_min):
        combined_alpha = (r_day["avg_alpha"] + r_min["avg_alpha"]) / 2
        print(f"{r_day['label']:>15s}  매매{r_day['avg_ret']:+6.2f}%   매매{r_min['avg_ret']:+6.2f}%   {combined_alpha:+6.2f}%p")
    print(f"  (단순보유 평균 — 일봉: {results_day[0]['avg_bnh']:+.2f}% / 분봉: {results_min[0]['avg_bnh']:+.2f}%)")


if __name__ == "__main__":
    main()
