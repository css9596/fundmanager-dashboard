"""regime-aware 효과 검증."""
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest
from config import RISK

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]


def eval_one(dfs, daily_map, regime_aware: bool, label: str):
    rets, bnhs, trade_counts = [], [], []
    for sym, df in dfs.items():
        bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
        res = run_backtest(df, sym, "crypto",
            {"min_confidence": 0.5,
             "take_profit_pct": RISK["take_profit_pct"],
             "stop_loss_pct": RISK["stop_loss_pct"],
             "regime_aware": regime_aware},
            daily_df=daily_map.get(sym))
        rets.append(res["return_pct"])
        bnhs.append(bnh)
        trade_counts.append(len(res["trades"]))
    avg_ret = mean(rets); avg_bnh = mean(bnhs)
    print(f"  [{label}] 매매 {avg_ret:+.2f}% / 단순보유 {avg_bnh:+.2f}% / "
          f"알파 {avg_ret-avg_bnh:+.2f}%p / 거래 {mean(trade_counts):.0f}건", flush=True)
    return avg_ret, avg_bnh


def main():
    print("일봉 500일 로드...", flush=True)
    daily = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in SYMBOLS}
    daily = {s: d for s, d in daily.items() if d is not None and len(d) >= 100}

    print("분봉 90일 로드...", flush=True)
    mins = {s: fetch_crypto(s, "minute15", 90*96) for s in SYMBOLS}
    mins = {s: d for s, d in mins.items() if d is not None and len(d) >= 200}

    print("\n=== 약세장 (일봉 500일, daily_df는 자기 자신) ===", flush=True)
    daily_self_map = daily  # 일봉 백테스트는 자기 자신을 daily_df로
    d_off, d_bnh = eval_one(daily, daily_self_map, False, "regime OFF")
    d_on, _ = eval_one(daily, daily_self_map, True, "regime ON ")

    print("\n=== 강세장 (분봉 90일, daily_df는 500일 일봉) ===", flush=True)
    m_off, m_bnh = eval_one(mins, daily, False, "regime OFF")
    m_on, _ = eval_one(mins, daily, True, "regime ON ")

    print("\n=== 종합 비교 ===")
    print(f"{'':>14}  {'일봉500':>10s}  {'분봉90':>10s}  {'평균알파':>10s}")
    alpha_off = ((d_off-d_bnh) + (m_off-m_bnh)) / 2
    alpha_on  = ((d_on -d_bnh) + (m_on -m_bnh)) / 2
    print(f"{'regime OFF':>14}  {d_off:+8.2f}%  {m_off:+8.2f}%  {alpha_off:+8.2f}%p")
    print(f"{'regime ON':>14}  {d_on:+8.2f}%  {m_on:+8.2f}%  {alpha_on:+8.2f}%p")
    print(f"{'개선':>14}  {d_on-d_off:+8.2f}%p {m_on-m_off:+8.2f}%p  {alpha_on-alpha_off:+8.2f}%p")


if __name__ == "__main__":
    main()
