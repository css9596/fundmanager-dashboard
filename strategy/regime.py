"""시장 regime 감지 — 일봉 데이터 기준 강세/약세/횡보 판별.

매수 빈도와 손절/익절 비율을 regime에 맞춰 자동 조정.
"""
import pandas as pd


def detect_regime(daily_df: pd.DataFrame, short_lookback: int = 30, long_lookback: int = 60) -> str:
    """일봉으로 시장 regime 감지.

    Returns: "bull" | "bear" | "sideways"
    """
    if daily_df is None or len(daily_df) < long_lookback:
        return "sideways"

    closes = daily_df["close"]
    long_seg = closes.tail(long_lookback)
    short_seg = closes.tail(short_lookback)

    long_mom = (long_seg.iloc[-1] - long_seg.iloc[0]) / long_seg.iloc[0]
    short_mom = (short_seg.iloc[-1] - short_seg.iloc[0]) / short_seg.iloc[0]

    # 강세: 60일 +10% 이상 + 단기도 양수
    if long_mom > 0.10 and short_mom > 0:
        return "bull"
    # 약세: 60일 -10% 이상 하락 + 단기도 음수
    if long_mom < -0.10 and short_mom < 0:
        return "bear"
    return "sideways"


# Regime별 파라미터 (sideways는 DEFAULT_PARAMS 사용)
REGIME_OVERRIDES = {
    "bull": {
        "buy_score_threshold": 4,         # 약간 공격적 (5→4)
        "resistance_filter_pct": 2.0,      # 저항선 완화 (3.0→2.0)
    },
    "bear": {
        "buy_score_threshold": 99,        # 사실상 매수 안 함 (보수)
    },
    "sideways": {},   # 기본값 유지
}


# Regime별 익절/손절 비율
REGIME_RISK = {
    "bull": {"take_profit_pct": 0.20, "stop_loss_pct": 0.05},  # 익절 20% (30%은 너무 컸음)
    "bear": {"take_profit_pct": 0.10, "stop_loss_pct": 0.04},  # 빠른 익절 + 빠른 손절
    "sideways": {},   # 기본값 유지
}
