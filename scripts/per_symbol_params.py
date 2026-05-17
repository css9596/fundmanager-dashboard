"""종목 그룹별 다른 파라미터 시도.

가설: 메이저(BTC/ETH)는 강한 추세 자주 발생 → 좀 더 공격적 매수
      알트(XRP/ADA/SOL/DOGE)는 변동성 큼 → 현재 보수적 유지
"""
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import fetch_crypto, run_backtest

MAJORS = ["KRW-BTC", "KRW-ETH"]
ALTS   = ["KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]
ALL    = MAJORS + ALTS

# 시나리오별 파라미터
SCENARIOS = {
    "균일 (현재 적용)": {
        s: {"buy_score_threshold": 5, "resistance_filter_pct": 3.0, "sell_score_threshold": 7}
        for s in ALL
    },
    "메이저 공격": {
        **{s: {"buy_score_threshold": 4, "resistance_filter_pct": 2.0, "sell_score_threshold": 7} for s in MAJORS},
        **{s: {"buy_score_threshold": 5, "resistance_filter_pct": 3.0, "sell_score_threshold": 7} for s in ALTS},
    },
    "알트 보수 더": {
        **{s: {"buy_score_threshold": 5, "resistance_filter_pct": 3.0, "sell_score_threshold": 7} for s in MAJORS},
        **{s: {"buy_score_threshold": 6, "resistance_filter_pct": 4.0, "sell_score_threshold": 7} for s in ALTS},
    },
    "메이저 공격 + 알트 보수": {
        **{s: {"buy_score_threshold": 4, "resistance_filter_pct": 2.0, "sell_score_threshold": 7} for s in MAJORS},
        **{s: {"buy_score_threshold": 6, "resistance_filter_pct": 4.0, "sell_score_threshold": 7} for s in ALTS},
    },
}


def eval_scenario(dfs, params_map, label):
    rows = []
    for sym, df in dfs.items():
        bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
        from config import RISK
        bp = {"min_confidence": 0.5,
              "take_profit_pct": RISK["take_profit_pct"],
              "stop_loss_pct": RISK["stop_loss_pct"]}
        rp = params_map.get(sym, {})
        res = run_backtest(df, sym, "crypto", bp, rule_params=rp)
        rows.append({"sym": sym, "ret": res["return_pct"], "bnh": bnh,
                     "trades": len(res["trades"])})
    return mean(r["ret"] for r in rows), mean(r["bnh"] for r in rows), mean(r["trades"] for r in rows)


def main():
    print("일봉 500일 로드...", flush=True)
    dfs_day = {s: pyupbit.get_ohlcv(s, interval="day", count=500) for s in ALL}
    dfs_day = {s: d for s, d in dfs_day.items() if d is not None and len(d) >= 200}

    print("분봉 90일 로드...", flush=True)
    dfs_min = {s: fetch_crypto(s, "minute15", 90*96) for s in ALL}
    dfs_min = {s: d for s, d in dfs_min.items() if d is not None and len(d) >= 200}

    print(f"\n{'시나리오':>22}  {'일봉500':>9} {'분봉90':>9}  {'평균알파':>9}", flush=True)
    print("="*70)
    for label, params in SCENARIOS.items():
        d_ret, d_bnh, d_tr = eval_scenario(dfs_day, params, label)
        m_ret, m_bnh, m_tr = eval_scenario(dfs_min, params, label)
        alpha_avg = ((d_ret - d_bnh) + (m_ret - m_bnh)) / 2
        print(f"{label:>22}  {d_ret:+7.2f}% {m_ret:+7.2f}%  {alpha_avg:+7.2f}%p")

    print(f"\n단순보유: 일봉 {d_bnh:+.2f}% / 분봉 {m_bnh:+.2f}%")


if __name__ == "__main__":
    main()
