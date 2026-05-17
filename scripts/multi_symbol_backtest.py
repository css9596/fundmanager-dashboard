"""주요 코인 종목 다종목 백테스트 — 같은 파라미터로 종목별 성과 비교."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import fetch_crypto, run_backtest

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE", "KRW-ADA"]
DAYS = 90
INTERVAL = "minute15"


def main():
    print(f"다종목 90일 백테스트 (현재 rule_decision 기본값)\n")
    rows = []
    for sym in SYMBOLS:
        try:
            df = fetch_crypto(sym, INTERVAL, DAYS * 96)
            if df is None or len(df) < 200:
                print(f"  {sym}: 데이터 부족 ({len(df) if df is not None else 0})")
                continue
            bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
            res = run_backtest(df, sym, "crypto", {"min_confidence": 0.5})
            trades = res["trades"]
            sells = [t for t in trades if t["side"] == "sell"]
            wins = [t for t in sells if t.get("pnl_pct", 0) > 0]

            # MDD
            eq = [e[1] for e in res["equity_curve"]]
            peak, mdd = eq[0] if eq else 0, 0
            for v in eq:
                if v > peak: peak = v
                dd = (v - peak) / peak * 100 if peak else 0
                if dd < mdd: mdd = dd

            rows.append({
                "symbol": sym,
                "bnh": bnh,
                "return_pct": res["return_pct"],
                "alpha": res["return_pct"] - bnh,
                "trades": len(trades),
                "win_rate": len(wins) / len(sells) * 100 if sells else None,
                "mdd": mdd,
            })
        except Exception as e:
            print(f"  {sym}: 에러 {e}")

    print(f"{'='*90}")
    print(f"{'종목':>10} {'단순보유':>10} {'매매전략':>10} {'알파':>9} {'거래':>5} {'승률':>6} {'최대낙폭':>9}")
    print(f"{'='*90}")
    # 알파 기준 정렬
    rows.sort(key=lambda r: r["alpha"], reverse=True)
    for r in rows:
        wr = f"{r['win_rate']:.0f}%" if r["win_rate"] is not None else "  —"
        print(f"{r['symbol']:>10} {r['bnh']:+9.2f}% {r['return_pct']:+9.2f}% "
              f"{r['alpha']:+8.2f}% {r['trades']:>5} {wr:>6} {r['mdd']:8.2f}%")

    print()
    print("알파 = 매매전략 수익률 - 단순보유 수익률 (+면 매매가 더 좋음)")


if __name__ == "__main__":
    main()
