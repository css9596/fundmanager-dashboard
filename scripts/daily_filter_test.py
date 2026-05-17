"""D — 다중 타임프레임 필터 검증.

일봉 추세 ↑ (일봉 EMA20 > EMA60) 일 때만 분봉 매수 허용.
약세장 진입 차단 + 강세장 추격.
"""
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest
from config import RISK

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]


def main():
    print("일봉 데이터 로드 (필터용)...", flush=True)
    daily = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in SYMBOLS}
    daily = {s: d for s, d in daily.items() if d is not None and len(d) >= 100}

    print("분봉 90일 로드 (백테스트용)...", flush=True)
    mins = {s: fetch_crypto(s, "minute15", 90*96) for s in SYMBOLS}
    mins = {s: d for s, d in mins.items() if d is not None and len(d) >= 200}

    print()
    print(f"{'필터':>15s}  {'분봉 매매':>10} {'단순보유':>10} {'알파':>10}  {'거래':>5}", flush=True)
    print("="*60)

    for use in [False, True]:
        rets, bnhs, trades_cnt = [], [], []
        for sym, df in mins.items():
            bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
            res = run_backtest(df, sym, "crypto",
                {"min_confidence": 0.5,
                 "take_profit_pct": RISK["take_profit_pct"],
                 "stop_loss_pct": RISK["stop_loss_pct"],
                 "daily_trend_filter": use},
                daily_df=daily.get(sym))
            rets.append(res["return_pct"])
            bnhs.append(bnh)
            trades_cnt.append(len(res["trades"]))
        label = "일봉 필터 ON" if use else "필터 OFF"
        print(f"{label:>15s}  {mean(rets):+8.2f}% {mean(bnhs):+8.2f}% {mean(rets)-mean(bnhs):+8.2f}%p  {mean(trades_cnt):>5.0f}")


if __name__ == "__main__":
    main()
