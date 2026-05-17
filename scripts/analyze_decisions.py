"""결정 로그 분석 (Phase 2).

decisions.jsonl 의 각 결정에 대해:
1) 누적 통계: 액션 분포, 전략별 분포, 평균 신뢰도
2) AI vs Rule 일치율: AI 결정에 같은 indicators로 Rule을 돌려 비교
3) 성과 분석 (outcome 채워진 결정 한정):
   - 액션별 평균 수익률 (15m/1h/4h)
   - 신뢰도 구간별 적중률
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.rule_decision import RuleBasedDecisionMaker

LOG_PATH = "logs/decisions.jsonl"


def _load():
    if not os.path.exists(LOG_PATH):
        return []
    out = []
    for line in open(LOG_PATH, encoding="utf-8"):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def section(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def basic_stats(records):
    section("1. 누적 통계")
    print(f"총 결정 수: {len(records)}")
    if not records:
        return

    by_strategy = defaultdict(int)
    by_action = defaultdict(int)
    by_symbol = defaultdict(int)
    confidences = []
    for r in records:
        by_strategy[r["strategy"]] += 1
        by_action[r["decision"]["action"]] += 1
        by_symbol[r["symbol"]] += 1
        c = r["decision"].get("confidence")
        if c is not None:
            confidences.append(c)

    print(f"전략별: {dict(by_strategy)}")
    print(f"액션별: {dict(by_action)}")
    print(f"종목별: {dict(by_symbol)}")
    if confidences:
        print(f"신뢰도 평균: {mean(confidences):.2f} (min={min(confidences):.2f}, max={max(confidences):.2f})")


def ai_vs_rule(records):
    """AI 결정에 대해 동일 indicators로 Rule을 돌려 비교."""
    section("2. AI vs Rule 일치율")
    ai_records = [r for r in records if r["strategy"] == "ai"]
    if not ai_records:
        print("AI 결정 없음 - 시뮬에 ANTHROPIC_API_KEY 설정 후 실행 필요")
        return

    rule = RuleBasedDecisionMaker()
    match = 0
    mismatch = []
    confusion = defaultdict(int)
    for r in ai_records:
        ind = r["indicators"]
        pos = None
        if r["position"].get("has_position"):
            pos = {
                "volume": 1,
                "avg_price": r["position"].get("avg_price") or r["price"],
                "profit_pct": r["position"].get("profit_pct") or 0,
            }
        try:
            rule_dec = rule.decide(r["symbol"], r["market_type"], ind, pos)
        except Exception as e:
            continue
        ai_action = r["decision"]["action"]
        rule_action = rule_dec["action"]
        confusion[(ai_action, rule_action)] += 1
        if ai_action == rule_action:
            match += 1
        else:
            mismatch.append((r["symbol"], r["ts"], ai_action, rule_action,
                             r["decision"].get("reason", "")[:60]))

    total = len(ai_records)
    print(f"AI 결정 수: {total} / 일치: {match} ({match/total*100:.1f}%)" if total else "n/a")
    print()
    print("Confusion (AI → Rule):")
    for (ai, ru), n in sorted(confusion.items()):
        print(f"  {ai:5s} → {ru:5s}: {n}")

    if mismatch:
        print()
        print(f"불일치 사례 (최대 5건):")
        for s, ts, ai, ru, rsn in mismatch[:5]:
            print(f"  {ts} {s} AI={ai} vs Rule={ru} | AI사유: {rsn}")


def outcome_analysis(records):
    section("3. 성과 분석 (outcome 채워진 결정만)")
    with_outcome = [r for r in records if r.get("outcome")]
    print(f"outcome 채워진 결정: {len(with_outcome)} / {len(records)}")
    if not with_outcome:
        print("아직 outcome 없음 - 시간 지난 뒤 백필러 실행 필요")
        return

    for horizon in ["15m", "60m", "240m"]:
        section_key = f"return_{horizon}"
        by_action = defaultdict(list)
        for r in with_outcome:
            ret = (r["outcome"] or {}).get(section_key)
            if ret is not None:
                by_action[r["decision"]["action"]].append(ret)
        if not any(by_action.values()):
            continue
        print(f"\n[{horizon}] 액션별 평균 수익률:")
        for act, returns in sorted(by_action.items()):
            if returns:
                print(f"  {act:5s}: n={len(returns):3d} avg={mean(returns):+.3f}% "
                      f"win_rate={sum(1 for x in returns if x>0)/len(returns)*100:.0f}%")


def main():
    records = _load()
    basic_stats(records)
    ai_vs_rule(records)
    outcome_analysis(records)


if __name__ == "__main__":
    main()
