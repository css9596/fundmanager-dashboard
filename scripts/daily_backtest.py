"""일봉 500일 (약세장 포함) 백테스트 — 봇 전략 진가 검증."""
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-DOGE"]
DAYS = 500


def main():
    print(f"일봉 {DAYS}일 백테스트 — 약세장 손실 방어 검증\n", flush=True)
    t0 = time.time()
    rows = []

    for sym in SYMBOLS:
        df = pyupbit.get_ohlcv(sym, interval="day", count=DAYS)
        if df is None or len(df) < 200:
            print(f"  {sym}: 데이터 부족", flush=True)
            continue

        # 단순보유 = 100번째 봉(window 끝 시점)부터 마지막까지
        start_price = df["close"].iloc[100]
        end_price = df["close"].iloc[-1]
        bnh = (end_price - start_price) / start_price * 100

        from config import RISK
        bp = {"min_confidence": 0.5,
              "take_profit_pct": RISK["take_profit_pct"],
              "stop_loss_pct": RISK["stop_loss_pct"]}
        res = run_backtest(df, sym, "crypto", bp)
        trades = res["trades"]
        sells = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sells if t.get("pnl_pct", 0) > 0]

        eq = [e[1] for e in res["equity_curve"]]
        peak, mdd = eq[0] if eq else 0, 0
        for v in eq:
            if v > peak: peak = v
            dd = (v - peak) / peak * 100 if peak else 0
            if dd < mdd: mdd = dd

        rows.append({
            "sym": sym, "bnh": bnh, "ret": res["return_pct"],
            "alpha": res["return_pct"] - bnh,
            "trades": len(trades),
            "wr": len(wins) / len(sells) * 100 if sells else None,
            "mdd": mdd,
        })
        print(f"  {sym}: 매매 {res['return_pct']:+7.2f}% / 단순보유 {bnh:+7.2f}% / "
              f"알파 {res['return_pct']-bnh:+6.2f}%p / 거래 {len(trades)} / "
              f"승률 {len(wins)/len(sells)*100 if sells else 0:.0f}% / MDD {mdd:.2f}%", flush=True)

    print()
    print(f"=== 6종목 평균 ===")
    print(f"  매매 전략:    {mean(r['ret'] for r in rows):+.2f}%")
    print(f"  단순보유:     {mean(r['bnh'] for r in rows):+.2f}%")
    print(f"  알파:        {mean(r['alpha'] for r in rows):+.2f}%p")
    print(f"  거래 평균:    {mean(r['trades'] for r in rows):.0f}건")
    if any(r['wr'] for r in rows):
        print(f"  승률 평균:    {mean(r['wr'] for r in rows if r['wr']):.0f}%")
    print(f"  최악 MDD:    {min(r['mdd'] for r in rows):.2f}%")
    print(f"  소요:        {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
