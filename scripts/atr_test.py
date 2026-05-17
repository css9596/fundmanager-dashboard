"""ATR 기반 동적 손절/익절 검증."""
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest
from config import RISK

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]


def eval_set(dfs, label, extra_params):
    rets, bnhs, trades_cnt = [], [], []
    for sym, df in dfs.items():
        bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
        bp = {"min_confidence": 0.5,
              "take_profit_pct": RISK["take_profit_pct"],
              "stop_loss_pct": RISK["stop_loss_pct"], **extra_params}
        res = run_backtest(df, sym, "crypto", bp)
        rets.append(res["return_pct"]); bnhs.append(bnh); trades_cnt.append(len(res["trades"]))
    avg_ret = mean(rets); avg_bnh = mean(bnhs)
    print(f"  [{label}] 매매 {avg_ret:+.2f}% / 단순보유 {avg_bnh:+.2f}% / "
          f"알파 {avg_ret-avg_bnh:+.2f}%p / 거래 {mean(trades_cnt):.0f}", flush=True)
    return avg_ret, avg_bnh


VARIANTS = [
    ("기본 (고정 5%/15%)", {}),
    ("ATR 손절만 (×2)", {"atr_mode": "sl", "atr_sl_mult": 2.0}),
    ("ATR 손절만 (×3)", {"atr_mode": "sl", "atr_sl_mult": 3.0}),
    ("ATR 손절+익절 (2x/5x)", {"atr_mode": "both", "atr_sl_mult": 2.0, "atr_tp_mult": 5.0}),
    ("ATR 손절+익절 (3x/8x)", {"atr_mode": "both", "atr_sl_mult": 3.0, "atr_tp_mult": 8.0}),
]


def main():
    print("일봉 500일 + 분봉 90일 로드...", flush=True)
    daily = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in SYMBOLS}
    daily = {s: d for s, d in daily.items() if d is not None and len(d) >= 200}
    mins = {s: fetch_crypto(s, "minute15", 90*96) for s in SYMBOLS}
    mins = {s: d for s, d in mins.items() if d is not None and len(d) >= 200}

    print("\n=== 약세장 (일봉 500일) ===", flush=True)
    for label, params in VARIANTS:
        eval_set(daily, label, params)

    print("\n=== 강세장 (분봉 90일) ===", flush=True)
    for label, params in VARIANTS:
        eval_set(mins, label, params)


if __name__ == "__main__":
    main()
