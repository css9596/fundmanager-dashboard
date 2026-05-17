import os
from dotenv import load_dotenv

load_dotenv()

# Claude AI
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Upbit
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")

# Bithumb
BITHUMB_API_KEY = os.getenv("BITHUMB_API_KEY")
BITHUMB_SECRET_KEY = os.getenv("BITHUMB_SECRET_KEY")

# KIS
KIS_APP_KEY = os.getenv("KIS_APP_KEY")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO")
KIS_ACCOUNT_PROD_CD = os.getenv("KIS_ACCOUNT_PROD_CD", "01")
KIS_IS_REAL = os.getenv("KIS_IS_REAL", "false").lower() == "true"

# 리스크 관리 설정 (소액 기준)
RISK = {
    "max_position_pct": 0.20,    # 총 자산의 최대 20%를 단일 종목에
    "max_position_krw": 50_000,  # 종목당 절대 금액 상한 (실거래 초기 안전장치)
    "stop_loss_pct": 0.05,       # 5% 손절 (이전 3%, 매도 신호 무시 전략에 맞춰 여유)
    "take_profit_pct": 0.15,     # 15% 익절 (이전 6%, 큰 익절 추구)
    "max_daily_loss_pct": 0.05,  # 하루 최대 손실 5%
    "max_open_positions": 3,     # 동시 최대 포지션 수
}

# 트레이딩 설정
TRADING = {
    "crypto_symbols": ["KRW-BTC", "KRW-ADA", "KRW-SOL"],  # universe_scan 결과 봇 알파 ≥+7%p 종목
    "stock_symbols": ["005930"],            # 삼성전자
    "candle_interval": 15,    # 분봉 (15분)
    "analysis_interval": 900, # 분석 주기 (초)
    "min_order_krw": 5000,   # 최소 주문 금액
}

# AI 설정
AI = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 512,    # 응답 길이 제한 (비용 절감)
}
