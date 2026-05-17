"""업비트 KRW 시총 상위 코인 일괄 백테스트 — 봇이 효과적인 종목 찾기."""
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import run_backtest
from config import RISK

# 시총/거래량 상위 코인 (수동 큐레이션)
CANDIDATES = [
    "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE", "KRW-ADA",
    "KRW-AVAX", "KRW-DOT", "KRW-LINK", "KRW-ATOM", "KRW-NEAR", "KRW-ALGO",
    "KRW-ETC", "KRW-HBAR", "KRW-VET", "KRW-INJ", "KRW-APT", "KRW-ARB",
    "KRW-OP", "KRW-SUI", "KRW-SEI", "KRW-TRX", "KRW-BCH",
]


def main():
    print(f"일봉 500일 일괄 백테스트 — {len(CANDIDATES)}종목\n", flush=True)
    rows = []
    t0 = time.time()
    for sym in CANDIDATES:
        df = pyupbit.get_ohlcv(sym, interval="day", count=500)
        if df is None or len(df) < 200:
            print(f"  {sym}: skip (data {len(df) if df is not None else 0})", flush=True)
            continue
        bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
        bp = {"min_confidence": 0.5,
              "take_profit_pct": RISK["take_profit_pct"],
              "stop_loss_pct": RISK["stop_loss_pct"]}
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

    rows.sort(key=lambda r: r["alpha"], reverse=True)

    print(f"\n{'='*80}")
    print(f"{'종목':>10}  {'단순보유':>10} {'매매':>10} {'알파':>10} {'거래':>5} {'승률':>5}")
    print(f"{'='*80}")
    for r in rows:
        mark = "✅" if r["alpha"] > 0 else "❌"
        print(f"{r['sym']:>10}  {r['bnh']:+8.2f}%  {r['ret']:+8.2f}%  {r['alpha']:+8.2f}%p  {r['trades']:>5} {r['wr']:>4.0f}%  {mark}")

    # 추천 그룹
    positives = [r for r in rows if r["alpha"] > 0]
    print(f"\n알파 양수: {len(positives)}/{len(rows)} 종목")
    print(f"평균 알파 (전체): {mean(r['alpha'] for r in rows):+.2f}%p")
    print(f"평균 알파 (양수만): {mean(r['alpha'] for r in positives):+.2f}%p" if positives else "n/a")

    top5 = rows[:5]
    print(f"\n=== 봇 효과 TOP 5 종목 ===")
    for r in top5:
        print(f"  {r['sym']}: 단순 {r['bnh']:+.1f}% → 봇 {r['ret']:+.1f}% (알파 {r['alpha']:+.1f}%p)")

    print(f"\n소요: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
