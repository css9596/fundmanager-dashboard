"""결정 로그에 outcome(N분/시간 뒤 가격 + 수익률)을 채워넣는 백필러.

사용법:
    python3 scripts/backfill_outcomes.py

동작:
- logs/decisions.jsonl 의 각 결정에 대해
- 결정 시각 + 15분/1h/4h 시점의 OHLCV close 가격을 조회
- outcome 필드에 채워넣어 logs/decisions.jsonl 로 원자적 교체
- 이미 outcome 채워진 행 또는 시점이 미래인 행은 건너뜀
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyupbit
import pandas as pd

from core.kis import KISClient

LOG_PATH = "logs/decisions.jsonl"
HORIZONS_MIN = [15, 60, 240]  # 15분 / 1시간 / 4시간

_kis = None


def _get_kis():
    global _kis
    if _kis is None:
        _kis = KISClient()
    return _kis


def _crypto_price_at(symbol: str, ts: datetime) -> Optional[float]:
    df = pyupbit.get_ohlcv(symbol, interval="minute1", count=5, to=ts + timedelta(minutes=2))
    if df is None or df.empty:
        return None
    target = ts.replace(second=0, microsecond=0)
    idx = df.index.tolist()
    candidates = [i for i in idx if i.to_pydatetime().replace(tzinfo=None) <= target.replace(tzinfo=None)]
    if not candidates:
        return float(df["close"].iloc[0])
    return float(df.loc[max(candidates), "close"])


def _stock_price_at(symbol: str, ts: datetime) -> Optional[float]:
    """KIS 분봉(당일) 또는 일봉(과거)으로 ts에 가장 가까운 종가."""
    now = datetime.now()
    kis = _get_kis()
    same_day = ts.date() == now.date()
    if same_day:
        # 당일 분봉: ts 이전 30개 중 ts에 가장 가까운 봉의 종가
        # 분봉이 미래시각으로 들어오면 안되므로 ts 시각으로 조회
        hhmmss = ts.strftime("%H%M%S")
        bars = kis.get_intraday_minute(symbol, hhmmss=hhmmss)
        if not bars:
            return None
        # bars: 최신 → 과거 순. ts 이하의 가장 큰 시각.
        target = ts.strftime("%H%M%S")
        candidates = [b for b in bars if b.get("stck_cntg_hour") and b["stck_cntg_hour"] <= target]
        if not candidates:
            candidates = bars
        chosen = candidates[0]
        try:
            return float(chosen.get("stck_prpr") or chosen.get("stck_clpr") or 0) or None
        except Exception:
            return None
    # 다른 날 → 일봉 종가
    bars = kis.get_ohlcv(symbol, period="D", count=30)
    if not bars:
        return None
    target_date = ts.strftime("%Y%m%d")
    for b in bars:
        d = b.get("stck_bsop_date") or b.get("bsop_date")
        if d and d == target_date:
            try:
                return float(b.get("stck_clpr") or 0) or None
            except Exception:
                return None
    return None


def _price_at(symbol: str, market_type: str, ts: datetime) -> Optional[float]:
    if market_type == "crypto":
        return _crypto_price_at(symbol, ts)
    if market_type == "stock":
        return _stock_price_at(symbol, ts)
    return None


def _backfill_record(rec: dict) -> dict:
    if rec.get("outcome") and all(f"price_{h}m" in rec["outcome"] for h in HORIZONS_MIN):
        return rec  # 이미 완전히 채워짐
    ts = datetime.fromisoformat(rec["ts"])
    now = datetime.now()
    outcome = rec.get("outcome") or {}
    price0 = rec.get("price")
    for h in HORIZONS_MIN:
        key_p = f"price_{h}m"
        key_r = f"return_{h}m"
        if key_p in outcome and outcome[key_p] is not None:
            continue
        target_ts = ts + timedelta(minutes=h)
        if target_ts > now:
            continue  # 미래 — 다음 백필 때
        p = _price_at(rec["symbol"], rec["market_type"], target_ts)
        if p is None:
            continue
        outcome[key_p] = p
        outcome[key_r] = round((p - price0) / price0 * 100, 3) if price0 else None
    rec["outcome"] = outcome if outcome else None
    return rec


def main():
    if not os.path.exists(LOG_PATH):
        print(f"{LOG_PATH} 없음. 시뮬레이션을 먼저 돌려서 결정 로그를 만들어주세요.")
        return

    filled = 0
    total = 0
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False,
                                       dir=os.path.dirname(LOG_PATH), suffix=".tmp")
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                rec = json.loads(line)
                before = json.dumps(rec.get("outcome"), sort_keys=True)
                rec = _backfill_record(rec)
                after = json.dumps(rec.get("outcome"), sort_keys=True)
                if before != after:
                    filled += 1
                tmp.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        tmp.close()
        os.replace(tmp.name, LOG_PATH)
    except Exception:
        os.unlink(tmp.name)
        raise

    print(f"처리: {total}건 / 새로 채움: {filled}건")


if __name__ == "__main__":
    main()
