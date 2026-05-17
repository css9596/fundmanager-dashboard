"""Rule 전략 파라미터 그리드 서치.

주요 차단 필터 + 임계 score 조합을 백테스트로 평가.
사용법:
    python3 scripts/grid_search.py
"""
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
from scripts.backtest import run_backtest, fetch_crypto


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--symbol", default="KRW-BTC")
    args = ap.parse_args()
    print(f"{args.days}일치 {args.symbol} 15m 데이터 로드 중...")
    df = fetch_crypto(args.symbol, "minute15", args.days * 96)
    print(f"데이터: {len(df)}봉 ({df.index[0]} ~ {df.index[-1]})")
    bnh = (df["close"].iloc[-1] - df["close"].iloc[100]) / df["close"].iloc[100] * 100
    print(f"단순 보유(buy & hold) 수익률: {bnh:+.2f}%\n")

    # 그리드 — 핵심 4개
    grid = {
        "resistance_filter_pct": [None, 1.5, 3.0],   # None=끔, 1.5=현재, 3.0=완화
        "downtrend_filter_rsi": [None, 35, 50],       # None=끔, 35=현재, 50=완화
        "buy_score_threshold": [2, 3, 4],             # 4=현재
        "sell_score_threshold": [2, 3],               # 3=현재
    }

    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"조합 수: {len(combos)}\n")

    results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        res = run_backtest(df, args.symbol, "crypto", {"min_confidence": 0.5}, rule_params=params)
        trades = res["trades"]
        sells = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
        results.append({
            "params": params,
            "return_pct": res["return_pct"],
            "vs_bnh": res["return_pct"] - bnh,
            "trades": len(trades),
            "win_rate": len(wins) / len(sells) * 100 if sells else None,
        })

    # 정렬: 절대 수익률 내림차순
    results.sort(key=lambda r: r["return_pct"], reverse=True)

    print(f"{'='*100}")
    print(f"{'#':>3} {'수익률':>8} {'vs단순보유':>10} {'거래':>5} {'승률':>6}  파라미터")
    print(f"{'='*100}")
    for i, r in enumerate(results[:15], 1):
        win = f"{r['win_rate']:.0f}%" if r["win_rate"] is not None else "  —"
        p = r["params"]
        ps = f"R={p['resistance_filter_pct']} D={p['downtrend_filter_rsi']} B={p['buy_score_threshold']} S={p['sell_score_threshold']}"
        print(f"{i:>3} {r['return_pct']:+7.2f}% {r['vs_bnh']:+9.2f}% {r['trades']:>5} {win:>6}  {ps}")

    print(f"\n... (총 {len(results)}개 중 상위 15개)")
    print(f"\n범례: R=저항선필터(%), D=하락추세RSI임계, B=매수score, S=매도score")
    print(f"단순보유 기준선: {bnh:+.2f}%")

    # 저장
    out_path = Path("logs/grid_search_result.json")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"bnh": bnh, "results": results}, f, ensure_ascii=False, default=str, indent=2)
    print(f"\n전체 결과 저장: {out_path}")


if __name__ == "__main__":
    main()
