class RuleBasedDecisionMaker:
    """개선된 규칙 기반 전략 - 추세 필터 + 가중치 + 변동성 반영"""

    def decide(self, symbol: str, market_type: str, indicators: dict, position: dict = None) -> dict:
        rsi = indicators.get("rsi", {})
        macd = indicators.get("macd", {})
        bb = indicators.get("bollinger", {})
        trend = indicators.get("trend", {})
        volume = indicators.get("volume_signal", {})
        sr = indicators.get("support_resistance", {})

        rsi_val = rsi.get("value", 50)
        direction = trend.get("direction", "sideways")
        bb_width = bb.get("band_width", 0.03)
        pct_b = bb.get("pct_b", 0.5)
        bb_pos = bb.get("position", "middle")
        vol_ratio = volume.get("ratio", 1.0)

        # ── 1. 시장 상태 판단 ─────────────────────────────
        # 볼린저밴드 폭으로 추세장/횡보장 구분
        is_trending = bb_width > 0.04
        is_volatile = bb_width > 0.08  # 과도한 변동성

        # ── 2. 매수 조건 (보유 없을 때) ───────────────────
        if not position or position.get("volume", 0) == 0:
            return self._buy_decision(
                rsi_val, direction, macd, bb_pos, pct_b,
                vol_ratio, sr, is_trending, is_volatile, symbol
            )

        # ── 3. 매도 조건 (보유 중일 때) ───────────────────
        else:
            return self._sell_decision(
                rsi_val, direction, macd, bb_pos, pct_b,
                vol_ratio, position, is_trending, symbol
            )

    def _buy_decision(self, rsi_val, direction, macd, bb_pos, pct_b,
                      vol_ratio, sr, is_trending, is_volatile, symbol):
        reasons = []
        score = 0

        # [필터] 하락추세면 매수 차단 (가장 중요)
        if direction == "down" and rsi_val > 35:
            return self._hold(f"하락추세 매수 차단 (RSI:{rsi_val:.0f})")

        # [필터] 과도한 변동성 구간 매수 차단
        if is_volatile:
            return self._hold("변동성 과다 - 관망")

        # [필터] 저항선 바로 아래면 매수 불리
        dist_resistance = sr.get("dist_to_resistance_pct", 10)
        if dist_resistance < 1.5:
            return self._hold(f"저항선 근접({dist_resistance:.1f}%) - 돌파 확인 후 진입")

        # RSI (가중치 높음)
        if rsi_val < 30:
            score += 3
            reasons.append(f"RSI 강한 과매도({rsi_val:.0f})")
        elif rsi_val < 40:
            score += 2
            reasons.append(f"RSI 과매도({rsi_val:.0f})")
        elif rsi_val > 60:
            score -= 2
        elif rsi_val > 55:
            score -= 1

        # MACD 크로스 (가중치 높음)
        if macd.get("cross") == "golden":
            score += 3
            reasons.append("MACD 골든크로스")
        elif macd.get("bullish") and macd.get("cross") == "none":
            score += 1
            reasons.append("MACD 강세")
        elif macd.get("cross") == "dead":
            score -= 3
            reasons.append("MACD 데드크로스")

        # 볼린저밴드
        if bb_pos == "below_lower":
            score += 2
            reasons.append("볼린저 하단 이탈(반등 기대)")
        elif pct_b < 0.2:
            score += 1
            reasons.append("볼린저 하단권")
        elif bb_pos == "above_upper":
            score -= 2

        # 추세 (하락추세 + RSI 극과매도는 반등 기대)
        if direction == "up":
            score += 2
            reasons.append("상승추세")
        elif direction == "down" and rsi_val < 30:
            score += 0  # 하락추세지만 극과매도 - 중립
            reasons.append("하락추세+극과매도(반등 주의)")
        elif direction == "sideways":
            score += 0

        # 거래량 (추세장에서만 의미 있음)
        if is_trending and vol_ratio > 2.0:
            score += 2
            reasons.append(f"강한 거래량({vol_ratio:.1f}배)")
        elif vol_ratio > 1.5 and score > 0:
            score += 1
            reasons.append(f"거래량 증가({vol_ratio:.1f}배)")

        # 지지선 근처
        dist_support = sr.get("dist_to_support_pct", 10)
        if dist_support < 1.0:
            score += 1
            reasons.append(f"지지선 근접({dist_support:.1f}%)")

        return self._make_decision_buy(score, reasons)

    def _sell_decision(self, rsi_val, direction, macd, bb_pos, pct_b,
                       vol_ratio, position, is_trending, symbol):
        reasons = []
        score = 0
        profit_pct = position.get("profit_pct", 0)

        # RSI 과매수
        if rsi_val > 75:
            score += 3
            reasons.append(f"RSI 강한 과매수({rsi_val:.0f})")
        elif rsi_val > 65:
            score += 2
            reasons.append(f"RSI 과매수({rsi_val:.0f})")

        # MACD 데드크로스
        if macd.get("cross") == "dead":
            score += 3
            reasons.append("MACD 데드크로스")
        elif not macd.get("bullish"):
            score += 1

        # 볼린저밴드 상단 돌파
        if bb_pos == "above_upper":
            score += 2
            reasons.append("볼린저 상단 돌파(과열)")
        elif pct_b > 0.85:
            score += 1

        # 하락추세 전환 시 빠른 매도
        if direction == "down":
            score += 2
            reasons.append("추세 하락 전환")

        # 수익 중일 때 매도 신호 더 민감하게
        if profit_pct > 3.0 and score >= 2:
            score += 1
            reasons.append(f"수익 중 매도신호({profit_pct:.1f}%)")

        # 손실 중일 때 추가 하락 방어
        if profit_pct < -1.5 and direction == "down":
            score += 2
            reasons.append(f"손실+하락추세 방어매도({profit_pct:.1f}%)")

        return self._make_decision_sell(score, reasons)

    def _make_decision_buy(self, score, reasons):
        reason_str = " / ".join(reasons) if reasons else "신호 없음"
        if score >= 4:
            confidence = min(score / 8.0, 0.9)
            pct = 0.20 if score >= 6 else 0.15
            return {"action": "buy", "confidence": round(confidence, 2),
                    "reason": reason_str, "risk_level": "low" if score >= 6 else "medium",
                    "suggested_position_pct": pct}
        return self._hold(reason_str if reasons else f"신호 불명확(score={score})")

    def _make_decision_sell(self, score, reasons):
        reason_str = " / ".join(reasons) if reasons else "신호 없음"
        if score >= 3:
            confidence = min(score / 7.0, 0.9)
            return {"action": "sell", "confidence": round(confidence, 2),
                    "reason": reason_str, "risk_level": "medium",
                    "suggested_position_pct": 0}
        return self._hold(reason_str if reasons else f"매도신호 불충분(score={score})")

    def _hold(self, reason: str) -> dict:
        return {"action": "hold", "confidence": 0.5, "reason": reason,
                "risk_level": "medium", "suggested_position_pct": 0}
