"""결정 로그 (JSONL).

매 결정(buy/sell/hold)을 지표 풀세트와 함께 1줄씩 append.
나중에 backfill_outcomes로 N분/시간 뒤 가격을 채워넣어 학습 데이터로 사용.
"""
import json
import os
import uuid
from datetime import datetime
from threading import Lock
from typing import Optional

DECISION_LOG_PATH = os.path.join("logs", "decisions.jsonl")
_lock = Lock()


def log_decision(
    symbol: str,
    market_type: str,
    strategy: str,
    indicators: dict,
    decision: dict,
    position: Optional[dict],
    price: float,
    mode: str = "sim",
) -> str:
    """결정 1건을 JSONL에 append. decision_id 반환 (백필 시 참조용)."""
    decision_id = uuid.uuid4().hex[:12]
    record = {
        "id": decision_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,                 # sim | dry | live
        "strategy": strategy,         # ai | rule
        "symbol": symbol,
        "market_type": market_type,   # crypto | stock
        "price": price,
        "indicators": indicators,
        "decision": {
            "action": decision.get("action"),
            "confidence": decision.get("confidence"),
            "reason": decision.get("reason"),
            "risk_level": decision.get("risk_level"),
            "suggested_position_pct": decision.get("suggested_position_pct"),
        },
        "position": {
            "has_position": bool(position and position.get("volume", 0) > 0),
            "avg_price": position.get("avg_price") if position else None,
            "profit_pct": position.get("profit_pct") if position else None,
        },
        "outcome": None,  # 백필러가 채움
    }

    os.makedirs(os.path.dirname(DECISION_LOG_PATH), exist_ok=True)
    with _lock:
        with open(DECISION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return decision_id
