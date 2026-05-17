"""매도 임계 옵션 비교 — 일봉(약세장) + 분봉(강세장) 양쪽 검증."""
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]

THRESHOLDS = [99, 7, 5, 3]   # 99=무시, 3=즉시 매도


def eval_set(dfs, label, sell_threshold):
    rows = []
    for sym, df in dfs.items():
        bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
        from config import RISK
        bp = {"min_confidence": 0.5,
              "take_profit_pct": RISK["take_profit_pct"],
              "stop_loss_pct": RISK["stop_loss_pct"]}
        rp = {"sell_score_threshold": sell_threshold}
        res = run_backtest(df, sym, "crypto", bp, rule_params=rp)
        trades = res["trades"]
        sells = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
        rows.append({"ret": res["return_pct"], "bnh": bnh, "trades": len(trades),
                     "wr": len(wins)/len(sells)*100 if sells else 0})
    return mean(r["ret"] for r in rows), mean(r["bnh"] for r in rows), mean(r["trades"] for r in rows)


def main():
    print("일봉 500일 로드...", flush=True)
    dfs_day = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in SYMBOLS}
    dfs_day = {s: d for s, d in dfs_day.items() if d is not None and len(d) >= 200}
    print(f"  {len(dfs_day)}종목 OK\n", flush=True)

    print("분봉 90일 로드...", flush=True)
    dfs_min = {s: fetch_crypto(s, "minute15", 90*96) for s in SYMBOLS}
    dfs_min = {s: d for s, d in dfs_min.items() if d is not None and len(d) >= 200}
    print(f"  {len(dfs_min)}종목 OK\n", flush=True)

    print(f"{'sell_score':>12}  {'일봉 매매':>10} {'일봉 단순':>10}  {'분봉 매매':>10} {'분봉 단순':>10}  {'평균알파':>10}")
    for t in THRESHOLDS:
        d_ret, d_bnh, d_tr = eval_set(dfs_day, "일봉", t)
        m_ret, m_bnh, m_tr = eval_set(dfs_min, "분봉", t)
        alpha_avg = ((d_ret - d_bnh) + (m_ret - m_bnh)) / 2
        print(f"{t:>12}  {d_ret:+9.2f}% {d_bnh:+9.2f}%  {m_ret:+9.2f}% {m_bnh:+9.2f}%  {alpha_avg:+8.2f}%p")


if __name__ == "__main__":
    main()
