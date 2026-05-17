DEFAULT_PARAMS = {
    # 차단 필터 (None 또는 0이면 끔)
    "resistance_filter_pct": 1.5,    # 저항선 N% 이내면 매수 차단 (90일 그리드 검증)
    "downtrend_filter_rsi": None,    # 하락추세 필터 OFF (90일 그리드: +1.08% 최적)
    "volatility_filter_bw": 0.08,    # 밴드폭 > N 이면 매수 차단

    # 임계값
    "buy_score_threshold": 4,        # 매수 점수 임계
    "sell_score_threshold": 3,       # 매도 점수 임계

    # 가중치 (튜닝 가능)
    "w_rsi_strong_oversold": 3,      # RSI < 30
    "w_rsi_oversold": 2,             # RSI < 40
    "w_macd_golden": 3,
    "w_macd_bullish": 1,
    "w_macd_dead": -3,
    "w_bb_below_lower": 2,
    "w_bb_lower_zone": 1,            # pct_b < 0.2
    "w_bb_above_upper": -2,
    "w_trend_up": 2,
    "w_volume_surge_trending": 2,    # 추세장 + 거래량 2배 이상
    "w_volume_increase": 1,          # 거래량 1.5배 이상 + score>0
    "w_support_near": 1,
}


class RuleBasedDecisionMaker:
    """개선된 규칙 기반 전략 - 추세 필터 + 가중치 + 변동성 반영"""

    def __init__(self, params: dict = None):
        self.p = {**DEFAULT_PARAMS, **(params or {})}

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
        vol_thresh = self.p.get("volatility_filter_bw") or float("inf")
        is_volatile = bb_width > vol_thresh

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
        p = self.p

        # [필터] 하락추세 매수 차단 (None이면 끔)
        dt_rsi = p.get("downtrend_filter_rsi")
        if dt_rsi is not None and direction == "down" and rsi_val > dt_rsi:
            return self._hold(f"하락추세 매수 차단 (RSI:{rsi_val:.0f})")

        # [필터] 과도한 변동성
        if is_volatile:
            return self._hold("변동성 과다 - 관망")

        # [필터] 저항선 근접 (None이면 끔)
        rf = p.get("resistance_filter_pct")
        dist_resistance = sr.get("dist_to_resistance_pct", 10)
        if rf is not None and dist_resistance < rf:
            return self._hold(f"저항선 근접({dist_resistance:.1f}%) - 돌파 확인 후 진입")

        # RSI
        if rsi_val < 30:
            score += p["w_rsi_strong_oversold"]
            reasons.append(f"RSI 강한 과매도({rsi_val:.0f})")
        elif rsi_val < 40:
            score += p["w_rsi_oversold"]
            reasons.append(f"RSI 과매도({rsi_val:.0f})")
        elif rsi_val > 60:
            score -= 2
        elif rsi_val > 55:
            score -= 1

        # MACD
        if macd.get("cross") == "golden":
            score += p["w_macd_golden"]
            reasons.append("MACD 골든크로스")
        elif macd.get("bullish") and macd.get("cross") == "none":
            score += p["w_macd_bullish"]
            reasons.append("MACD 강세")
        elif macd.get("cross") == "dead":
            score += p["w_macd_dead"]
            reasons.append("MACD 데드크로스")

        # 볼린저밴드
        if bb_pos == "below_lower":
            score += p["w_bb_below_lower"]
            reasons.append("볼린저 하단 이탈(반등 기대)")
        elif pct_b < 0.2:
            score += p["w_bb_lower_zone"]
            reasons.append("볼린저 하단권")
        elif bb_pos == "above_upper":
            score += p["w_bb_above_upper"]

        # 추세
        if direction == "up":
            score += p["w_trend_up"]
            reasons.append("상승추세")
        elif direction == "down" and rsi_val < 30:
            reasons.append("하락추세+극과매도(반등 주의)")

        # 거래량
        if is_trending and vol_ratio > 2.0:
            score += p["w_volume_surge_trending"]
            reasons.append(f"강한 거래량({vol_ratio:.1f}배)")
        elif vol_ratio > 1.5 and score > 0:
            score += p["w_volume_increase"]
            reasons.append(f"거래량 증가({vol_ratio:.1f}배)")

        # 지지선 근처
        dist_support = sr.get("dist_to_support_pct", 10)
        if dist_support < 1.0:
            score += p["w_support_near"]
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
        threshold = self.p["buy_score_threshold"]
        if score >= threshold:
            confidence = min(score / 8.0, 0.9)
            pct = 0.20 if score >= threshold + 2 else 0.15
            return {"action": "buy", "confidence": round(confidence, 2),
                    "reason": reason_str, "risk_level": "low" if score >= threshold + 2 else "medium",
                    "suggested_position_pct": pct}
        return self._hold(reason_str if reasons else f"신호 불명확(score={score})")

    def _make_decision_sell(self, score, reasons):
        reason_str = " / ".join(reasons) if reasons else "신호 없음"
        threshold = self.p["sell_score_threshold"]
        if score >= threshold:
            confidence = min(score / 7.0, 0.9)
            return {"action": "sell", "confidence": round(confidence, 2),
                    "reason": reason_str, "risk_level": "medium",
                    "suggested_position_pct": 0}
        return self._hold(reason_str if reasons else f"매도신호 불충분(score={score})")

    def _hold(self, reason: str) -> dict:
        return {"action": "hold", "confidence": 0.5, "reason": reason,
                "risk_level": "medium", "suggested_position_pct": 0}
