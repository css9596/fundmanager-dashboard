"""logs/decisions.jsonl + 최근 백테스트 결과를 web/data/*.json 으로 export.

대시보드(web/index.html)가 fetch해서 렌더링.
"""
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "logs" / "decisions.jsonl"
WEB_DATA = ROOT / "docs" / "data"
WEB_DATA.mkdir(parents=True, exist_ok=True)

MAX_DECISIONS_FOR_WEB = 500


def _load_records():
    if not LOG_PATH.exists():
        return []
    out = []
    for line in open(LOG_PATH, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _bot_running():
    """simulate.py 프로세스가 떠 있는지 ps로 확인."""
    try:
        out = subprocess.run(["pgrep", "-f", "simulate.py"], capture_output=True, text=True)
        return bool(out.stdout.strip())
    except Exception:
        return False


def export_status(records):
    by_action = Counter(r["decision"]["action"] for r in records)
    by_strategy = Counter(r["strategy"] for r in records)
    by_symbol = Counter(r["symbol"] for r in records)
    latest_strategy = records[-1]["strategy"] if records else None

    status = {
        "last_update": datetime.now().isoformat(timespec="seconds"),
        "bot_running": _bot_running(),
        "total_decisions": len(records),
        "first_ts": records[0]["ts"] if records else None,
        "last_ts": records[-1]["ts"] if records else None,
        "strategy": latest_strategy,
        "by_action": dict(by_action),
        "by_strategy": dict(by_strategy),
        "by_symbol": dict(by_symbol),
    }
    with open(WEB_DATA / "status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False)


def export_decisions(records):
    recent = records[-MAX_DECISIONS_FOR_WEB:]
    slim = []
    for r in recent:
        rsi = (r.get("indicators") or {}).get("rsi", {}).get("value")
        slim.append({
            "ts": r["ts"],
            "symbol": r["symbol"],
            "market_type": r["market_type"],
            "strategy": r["strategy"],
            "price": r["price"],
            "action": r["decision"]["action"],
            "confidence": r["decision"].get("confidence"),
            "reason": (r["decision"].get("reason") or "")[:200],
            "rsi": rsi,
            "outcome": r.get("outcome"),
        })
    with open(WEB_DATA / "decisions.json", "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False)


def export_backtest():
    """최신 BTC 백테스트 결과를 만들어 저장. 실패해도 export 자체는 멈추지 않음."""
    bt_path = WEB_DATA / "backtest.json"
    try:
        subprocess.run(
            ["python3", str(ROOT / "scripts" / "backtest.py"),
             "KRW-BTC", "--days", "30", "--interval", "minute15",
             "--save", str(bt_path)],
            check=True, capture_output=True, text=True,
        )
        # 요약 보강
        with open(bt_path, encoding="utf-8") as f:
            data = json.load(f)
        trades = data.get("trades", [])
        sells = [t for t in trades if t["side"] == "sell"]
        wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
        data["summary"]["total_trades"] = len(trades)
        data["summary"]["win_rate"] = (len(wins) / len(sells) * 100) if sells else None
        with open(bt_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        print(f"백테스트 export 실패: {e}", file=sys.stderr)
        return False


def main():
    records = _load_records()
    print(f"records: {len(records)}")
    export_status(records)
    print("  status.json 저장")
    export_decisions(records)
    print("  decisions.json 저장")
    ok = export_backtest()
    print(f"  backtest.json {'저장' if ok else '실패'}")


if __name__ == "__main__":
    main()
