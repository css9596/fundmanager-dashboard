# FundManager 트레이딩 봇 설정 가이드

## 1단계: .env 파일 생성

```bash
cp .env.example .env
```

## 2단계: API 키 발급 및 입력

### 업비트
1. https://upbit.com → 마이페이지 → Open API 관리
2. 거래/조회 권한 선택 → Access Key, Secret Key 복사
3. `.env`에 입력

### 빗썸
1. https://www.bithumb.com → 마이페이지 → API 관리
2. API Key, Secret Key 발급 → `.env`에 입력

### 한국투자증권 KIS
1. https://apiportal.koreainvestment.com 가입
2. 앱 등록 → App Key, App Secret 발급
3. 계좌번호 확인 (8자리-2자리 형식)
4. **처음에는 KIS_IS_REAL=false (모의투자)로 시작 권장**

### Claude API
1. https://console.anthropic.com → API Keys
2. 기존 키 입력

## 3단계: 실행

### 모의투자 (추천: 처음 2-3일)
```bash
python3 main.py
```

### 실거래
```bash
python3 main.py --live
```

### 1회 테스트 실행
```bash
python3 main.py --once
```

## 리스크 설정 (config.py)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| max_position_pct | 20% | 종목당 최대 투자 비율 |
| stop_loss_pct | 3% | 손절 기준 |
| take_profit_pct | 6% | 익절 기준 |
| max_daily_loss_pct | 5% | 일일 최대 손실 (초과시 당일 거래 중단) |
| max_open_positions | 3 | 동시 최대 보유 종목 수 |

## 주의사항

- **반드시 모의투자로 1주일 이상 테스트 후 실거래 전환**
- 자동매매는 수익 보장 없음 - 손실 가능성 항상 존재
- API 키는 절대 공유 금지
