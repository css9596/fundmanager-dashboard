import json
import anthropic
from config import ANTHROPIC_API_KEY, AI, RISK


class AIDecisionMaker:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = AI["model"]

    def decide(self, symbol: str, market_type: str, indicators: dict, position: dict = None) -> dict:
        prompt = self._build_prompt(symbol, market_type, indicators, position)
        message = self.client.messages.create(
            model=self.model,
            max_tokens=AI["max_tokens"],
            system=self._system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(message.content[0].text)

    def _system_prompt(self) -> str:
        return f"""당신은 전문 퀀트 트레이더입니다. 기술적 지표를 분석하여 매수/매도/홀드 결정을 내립니다.

리스크 관리 원칙:
- 최대 포지션: 총 자산의 {RISK['max_position_pct']*100:.0f}%
- 손절: -{RISK['stop_loss_pct']*100:.0f}%
- 익절: +{RISK['take_profit_pct']*100:.0f}%
- 소액 투자자 기준으로 보수적으로 판단

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "action": "buy" | "sell" | "hold",
  "confidence": 0.0~1.0,
  "reason": "한국어로 간단한 이유",
  "risk_level": "low" | "medium" | "high",
  "suggested_position_pct": 0.05~0.20
}}"""

    def _build_prompt(self, symbol: str, market_type: str, indicators: dict, position: dict) -> str:
        pos_info = ""
        if position and position.get("volume", 0) > 0:
            pos_info = f"""
현재 보유 포지션:
- 보유량: {position['volume']}
- 평균 매수가: {position['avg_price']:,}원
- 현재 수익률: {position.get('profit_pct', 0):.2f}%
"""

        return f"""종목: {symbol} ({market_type})
현재가: {indicators.get('current_price', 0):,}원
{pos_info}
기술적 지표:
- RSI: {indicators.get('rsi', {}).get('value', 0):.1f} ({indicators.get('rsi', {}).get('signal', '')})
- MACD 신호: {indicators.get('macd', {}).get('cross', '')} / 강세: {indicators.get('macd', {}).get('bullish', False)}
- 볼린저밴드 위치: {indicators.get('bollinger', {}).get('position', '')} / %B: {indicators.get('bollinger', {}).get('pct_b', 0):.2f}
- 추세: {indicators.get('trend', {}).get('direction', '')} (EMA5:{indicators.get('trend', {}).get('ema5', 0):,.0f} / EMA20:{indicators.get('trend', {}).get('ema20', 0):,.0f})
- 거래량 비율: {indicators.get('volume_signal', {}).get('ratio', 1):.2f}배 (급증: {indicators.get('volume_signal', {}).get('surge', False)})
- 가격 변화: 1H {indicators.get('price_change_1h', 0):+.2f}% / 4H {indicators.get('price_change_4h', 0):+.2f}% / 24H {indicators.get('price_change_24h', 0):+.2f}%
- 저항선: {indicators.get('support_resistance', {}).get('resistance', 0):,}원 (현재가 대비 {indicators.get('support_resistance', {}).get('dist_to_resistance_pct', 0):+.2f}%)
- 지지선: {indicators.get('support_resistance', {}).get('support', 0):,}원 (현재가 대비 -{indicators.get('support_resistance', {}).get('dist_to_support_pct', 0):.2f}%)

매수/매도/홀드 결정을 JSON으로 응답하세요."""

    def _parse_response(self, text: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        return {
            "action": "hold",
            "confidence": 0.0,
            "reason": "응답 파싱 실패 - 안전하게 홀드",
            "risk_level": "high",
            "suggested_position_pct": 0.0,
        }
