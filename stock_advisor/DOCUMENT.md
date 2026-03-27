# 단타 주식 어드바이저 - 기술 문서

> 작성일: 2026-03-25
> 버전: pykrx 기반 프로토타입 (KIS API 전환 준비 완료)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [아키텍처 구조](#2-아키텍처-구조)
3. [사용 API 및 라이브러리](#3-사용-api-및-라이브러리)
4. [파일별 상세 설명](#4-파일별-상세-설명)
5. [데이터 흐름](#5-데이터-흐름)
6. [스크리닝 로직](#6-스크리닝-로직)
7. [점수 계산 로직](#7-점수-계산-로직)
8. [매매 가이드라인 계산 로직](#8-매매-가이드라인-계산-로직)
9. [설정값 (config.py) 전체 정리](#9-설정값-configpy-전체-정리)
10. [실행 방법](#10-실행-방법)
11. [KIS API 전환 방법](#11-kis-api-전환-방법)

---

## 1. 프로젝트 개요

한국 주식 시장(KOSPI/KOSDAQ)에서 단타 매매에 적합한 종목을 자동으로 스크리닝하고,
매수 구간·손절가·목표가·수량 가이드라인을 제공하는 도구.

### 주요 기능

| 기능 | 설명 |
|------|------|
| 종목 스크리닝 | 시총 상위 200개 종목을 기술적 지표 기반으로 필터링 |
| 점수 계산 | RSI·거래량·볼린저밴드·MACD·시그널 가중 합산 (0~100점) |
| 매매 가이드라인 | 매수 구간, 손절가, 1·2차 목표가, R/R 비율, 분할 매수 수량 |
| 웹 대시보드 | Streamlit 기반 라이트 테마 UI (실시간 진행률, 차트 포함) |
| CLI | 터미널에서 직접 실행 가능 (main.py) |
| 데이터 소스 교체 | config.py 한 줄만 바꿔 pykrx → KIS API 전환 가능 |

---

## 2. 아키텍처 구조

```
stock_advisor/
├── config.py                  # 전역 설정 (SSOT)
├── main.py                    # CLI 진입점
├── data/
│   ├── fetcher.py             # 팩토리 패턴 - 데이터 소스 추상화
│   └── kis_fetcher.py         # KIS API 구현체 (전환 시 활성화)
├── analysis/
│   ├── indicators.py          # 기술적 지표 계산
│   ├── screener.py            # 종목 스크리닝 핵심 로직
│   └── price_guide.py         # 매매 가이드라인 계산
└── ui/
    └── dashboard.py           # Streamlit 웹 대시보드
```

### 레이어 의존 관계

```
ui/dashboard.py  ──┐
main.py          ──┤──▶ analysis/screener.py ──▶ data/fetcher.py ──▶ pykrx / KIS API
                   │                         ├──▶ analysis/indicators.py
                   │                         └──▶ analysis/price_guide.py
                   │
                   └──▶ (모두) config.py
```

> **규칙:** config.py는 어디에도 의존하지 않음. 모든 파일이 config.py를 import.

---

## 3. 사용 API 및 라이브러리

### 3-1. 외부 데이터 API

#### pykrx (현재 사용)
- **종류:** 비공식 KRX 크롤링 라이브러리
- **지연:** 장중 약 15분 지연 (실시간 아님)
- **사용 함수:**

| 함수 | 용도 |
|------|------|
| `stock.get_market_ohlcv(start, end, ticker)` | 일봉 OHLCV 데이터 조회 |
| `stock.get_market_cap(date, date, ticker)` | 시가총액 조회 |

#### FinanceDataReader (종목 리스트 전용)
- pykrx의 종목 목록 API가 KRX 서버 응답 오류로 불안정
- `fdr.StockListing("KOSPI")` / `fdr.StockListing("KOSDAQ")`으로 대체

#### KIS OpenAPI (전환 준비 완료)
- **종류:** 한국투자증권 공식 REST API
- **인증:** OAuth2 Bearer Token (24시간 유효, 자동 갱신)
- **도메인:**
  - 모의투자: `https://openapivts.koreainvestment.com:29443`
  - 실계좌: `https://openapi.koreainvestment.com:9443`
- **사용 엔드포인트:**

| TR_ID | 엔드포인트 | 용도 |
|-------|-----------|------|
| `FHKST01010100` | `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | 일봉 OHLCV |
| `FHKST01010100` | `/uapi/domestic-stock/v1/quotations/inquire-price` | 현재가 |

### 3-2. Python 라이브러리

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| `pykrx` | ≥1.0.47 | 한국 주식 데이터 조회 |
| `finance-datareader` | ≥0.9.0 | 종목 리스트 조회 |
| `pandas` | ≥2.0.0 | DataFrame 데이터 처리 |
| `numpy` | ≥2.0.0 | 수치 계산, NaN 처리 |
| `streamlit` | ≥1.32.0 | 웹 대시보드 프레임워크 |
| `plotly` | ≥5.19.0 | 인터랙티브 차트 |
| `requests` | ≥2.31.0 | KIS API HTTP 요청 |

---

## 4. 파일별 상세 설명

### 4-1. config.py — 전역 설정

모든 파라미터의 단일 진실 공급원(SSOT). 이 파일 하나만 수정하면 시스템 전체 동작이 바뀜.

```python
DATA_SOURCE = "pykrx"   # "pykrx" | "kis"

# KIS 인증 (DATA_SOURCE = "kis" 시 입력)
KIS_APP_KEY    = ""
KIS_APP_SECRET = ""
KIS_ACCOUNT_NO = ""
KIS_IS_MOCK    = True   # True=모의투자, False=실계좌

# 기술적 지표
RSI_PERIOD   = 14
MACD_FAST    = 12 / MACD_SLOW = 26 / MACD_SIGNAL = 9
BB_PERIOD    = 20 / BB_STD = 2.0
ATR_PERIOD   = 14

# 스크리닝 조건
MIN_VOLUME_SURGE = 0.5    # 20일 평균 대비 거래량 배수
MIN_PRICE        = 1000   # 최소 주가
MAX_PRICE        = 500000 # 최대 주가
MAX_SCAN_STOCKS  = 200    # 스캔 종목 수
MAX_RSI          = 85     # RSI 상한
MIN_MACD_HIST    = -500   # MACD 히스토그램 하한
MIN_RISK_REWARD  = 0.8    # 최소 R/R 비율

# 매매 가이드라인
STOP_LOSS_ATR_MULT = 1.5  # 손절 = 매수가 - ATR × 1.5
TARGET1_RATIO      = 0.02 # 1차 목표 +2%
TARGET2_RATIO      = 0.05 # 2차 목표 +5%
```

---

### 4-2. data/fetcher.py — 데이터 수집 추상화

**팩토리 패턴** 적용. `get_fetcher()` 호출만 하면 DATA_SOURCE에 따라 적절한 구현체 반환.

```python
def get_fetcher():
    if DATA_SOURCE == "kis":
        return KISFetcher()
    return PykrxFetcher()
```

#### PykrxFetcher 메서드

| 메서드 | 반환 | 설명 |
|--------|------|------|
| `get_stock_list(market)` | `DataFrame[ticker, name, market]` | FinanceDataReader로 종목 목록 조회 |
| `get_ohlcv(ticker, days, end_date)` | `DataFrame[open,high,low,close,volume]` | 일봉 OHLCV (60일 기본) |
| `get_current_price(ticker)` | `{ticker, price, change_rate, volume}` | 당일 현재가 |
| `get_market_cap(ticker)` | `int` (억원) | 시가총액 |

> **주의:** pykrx 컬럼 수가 버전마다 6개 또는 7개로 다름 → 위치 기반 rename으로 처리.

---

### 4-3. analysis/indicators.py — 기술적 지표 계산

OHLCV DataFrame을 입력받아 지표 컬럼을 추가하고, 최신 봉 기준 시그널을 생성.

#### 계산 지표

| 함수 | 추가 컬럼 | 계산식 |
|------|----------|--------|
| `add_rsi` | `rsi` | RS = EMA(상승) / EMA(하락), RSI = 100 - 100/(1+RS) |
| `add_macd` | `macd, macd_signal, macd_hist` | MACD = EMA12 - EMA26, Signal = EMA9(MACD), Hist = MACD - Signal |
| `add_bollinger_bands` | `bb_upper, bb_middle, bb_lower, bb_width, bb_pct` | SMA±2σ, bb_pct = (close-lower)/(upper-lower) |
| `add_atr` | `atr` | ATR = EMA(True Range, 14) |
| `add_volume_ratio` | `volume_ma, volume_ratio` | 현재 거래량 / 20일 평균 거래량 |
| `add_moving_averages` | `ma5, ma20, ma60` | 단순 이동평균 |

#### 생성 시그널 (get_latest_signals)

| 조건 | 시그널 텍스트 |
|------|-------------|
| RSI < 30 | "RSI 강한 과매도" |
| RSI < 40 | "RSI 과매도 구간" |
| MACD 골든크로스 | "MACD 골든크로스 (매수 전환)" |
| MACD 히스토그램 증가 | "MACD 상승 모멘텀" |
| bb_pct < 0.1 | "볼린저 하단 근접" |
| volume_ratio ≥ 3.0 | "거래량 급등" |
| volume_ratio ≥ 2.0 | "거래량 증가" |
| MA20 ±1% 이내 | "20일 이평선 지지" |

---

### 4-4. analysis/screener.py — 스크리닝 핵심

전체 종목을 순회하며 조건 필터링 + 점수 계산 + 정렬 반환.

#### run_screening() 반환 DataFrame 컬럼

```
ticker, name, market, price, change_rate, score,
rsi, macd_hist, volume_ratio, bb_pct, signals,
entry_low, entry_high, stop_loss, loss_pct,
target1, target1_pct, target2, target2_pct,
risk_reward, qty_first, qty_second,
expected_profit1, expected_loss
```

#### 필터링 순서 (AND 조건)

```
1. OHLCV 데이터 30일 이상 존재
2. MIN_PRICE ≤ 현재가 ≤ MAX_PRICE
3. volume_ratio ≥ MIN_VOLUME_SURGE (0.5)
4. rsi ≤ MAX_RSI (85)
5. macd_hist ≥ MIN_MACD_HIST (-500)
6. risk_reward ≥ MIN_RISK_REWARD (0.8)   ← price_guide 결과 기반
```

---

### 4-5. analysis/price_guide.py — 매매 가이드라인

#### 계산 흐름

```
현재가(close), ATR, BB 하단(bb_lower)
       ↓
매수 구간:
  entry_low  = max(bb_lower, close × 0.995)
  entry_high = close × 1.005
  entry_mid  = (entry_low + entry_high) / 2
       ↓
손절가:
  stop_loss = entry_mid - (ATR × 1.5)   ← 호가 단위 반올림
  loss_pct  = (entry_mid - stop_loss) / entry_mid
       ↓
목표가:
  target1 = entry_mid × 1.02   ← +2%
  target2 = entry_mid × 1.05   ← +5%
       ↓
R/R 비율:
  risk_reward1 = gain1_pct / loss_pct
       ↓
수량:
  qty_total  = investment / entry_mid
  qty_first  = qty_total × 0.7   (1차 70%)
  qty_second = qty_total × 0.3   (2차 30%)
       ↓
예상 손익:
  expected_profit1 = qty × (target1 - entry_mid)
  expected_loss    = qty × (entry_mid - stop_loss)
```

#### 한국 호가 단위 (_round_price)

| 주가 범위 | 호가 단위 |
|----------|---------|
| ~1,000원 미만 | 1원 |
| 1,000 ~ 5,000원 | 5원 |
| 5,000 ~ 10,000원 | 10원 |
| 10,000 ~ 50,000원 | 50원 |
| 50,000 ~ 100,000원 | 100원 |
| 100,000 ~ 500,000원 | 500원 |
| 500,000원 이상 | 1,000원 |

---

### 4-6. ui/dashboard.py — 웹 대시보드

Streamlit 기반. 라이트 테마, 색상 팔레트 통일.

#### 색상 팔레트

| 변수 | 색상 | 용도 |
|------|------|------|
| C_PRIMARY `#2563EB` | 파랑 | 브랜드, 매수 구간 |
| C_SUCCESS `#16A34A` | 초록 | 수익, 목표가 |
| C_DANGER `#DC2626` | 빨강 | 손실, 손절가 |
| C_WARNING `#D97706` | 주황 | 주의 (RSI 과매수 등) |
| C_NEUTRAL `#64748B` | 회색 | 보조 텍스트 |

#### 추천 점수 등급

| 등급 | 점수 | 색상 | 의미 |
|------|------|------|------|
| S | 70점↑ | 보라 `#7C3AED` | 강력 추천 |
| A | 55~69점 | 초록 | 추천 |
| B | 40~54점 | 주황 | 관심 종목 |
| C | 40점↓ | 회색 | 낮은 우선순위 |

#### Streamlit session_state 키

| 키 | 타입 | 설명 |
|----|------|------|
| `result_df` | DataFrame | 스크리닝 결과 |
| `investment` | int | 분석 시 투자금 |
| `last_run` | str | 마지막 분석 시간 |
| `analysis_ran` | bool | 분석 실행 여부 |

#### 차트 구성 (Plotly, 4패널)

```
Row 1 (52%): 캔들차트 + 볼린저밴드 + MA5/MA20 + 수평선(매수/손절/목표)
Row 2 (16%): RSI (30/70 기준선)
Row 3 (16%): MACD + Signal + 히스토그램
Row 4 (16%): 거래량 + 거래량 MA
```

---

### 4-7. main.py — CLI 진입점

```bash
python main.py                    # 기본 (투자금 100만원, 상위 10개)
python main.py --top 5            # 상위 5개
python main.py --invest 500000    # 50만원 기준
python main.py --verbose          # 상세 로그
```

---

## 5. 데이터 흐름

### 웹 대시보드 실행 흐름

```
[사용자 입력: 투자금, 추천 종목 수]
        ↓
    분석 시작 클릭
        ↓
run_screening(investment, top_n)
        ↓
   [종목 200개 반복]
        ↓
fetcher.get_stock_list()     → [ticker, name, market] × 200
fetcher.get_ohlcv(ticker)    → OHLCV DataFrame (60일)
fetcher.get_current_price()  → {price, change_rate}
add_all_indicators(df)       → RSI, MACD, BB, ATR, Volume, MA
get_latest_signals(df)       → 지표값 dict + 시그널 리스트
        ↓
   [6단계 필터링]
        ↓
_calculate_score(ind)        → 점수 (0~100)
calculate_price_guide(df)    → 매매 가이드라인 dict
        ↓
[점수 내림차순 정렬 → 상위 N개]
        ↓
st.session_state 저장 → st.rerun()
        ↓
_render_stock_card() × N     → HTML 카드 렌더링
_render_chart()              → Plotly 차트 (탭 2)
```

---

## 6. 스크리닝 로직

### 필터 조건 (모두 AND)

```python
# 1. 데이터 충분성
len(df) >= 30

# 2. 주가 범위
1,000 <= price <= 500,000

# 3. 거래량 급등 (필수)
volume_ratio >= 0.5

# 4. RSI 과매수 제외
rsi <= 85

# 5. MACD 극단적 약세 제외
macd_hist >= -500

# 6. 리스크/리워드 검증
risk_reward >= 0.8
```

---

## 7. 점수 계산 로직

```
총점 (0~100) = RSI점수 + 거래량점수 + 볼린저점수 + MACD점수 + 시그널보너스
```

| 항목 | 최대 | 계산 방식 |
|------|------|---------|
| RSI (낮을수록 유리) | 30점 | rsi<30: 30점, <40: 20점, <50: 10점 |
| 거래량 급등 | 30점 | min(volume_ratio × 6, 30) |
| 볼린저 하단 근접 | 20점 | max(0, (0.5 - bb_pct) × 40) |
| MACD 모멘텀 | 10점 | macd_hist>0이면 min(macd_hist/100, 10) |
| 시그널 개수 보너스 | 10점 | min(signal_count × 3, 10) |

---

## 8. 매매 가이드라인 계산 로직

### 매수 구간
- 하단: `max(볼린저밴드 하단, 현재가 × 0.995)`
- 상단: `현재가 × 1.005`

### 손절가
- `entry_mid - (ATR × 1.5)`
- ATR: 14일 평균 변동폭 (일별 True Range의 지수이동평균)

### 목표가
- 1차: `entry_mid × 1.02` (+2%)
- 2차: `entry_mid × 1.05` (+5%)

### R/R 비율
- `기대 수익률 / 손실률`
- 예) 손실 1.5%, 수익 3% → R/R = 2.0 → "1:2.0"

### 분할 매수 수량
- 1차: `(투자금 / entry_mid) × 0.7` (70%)
- 2차: `(투자금 / entry_mid) × 0.3` (30%)

---

## 9. 설정값 (config.py) 전체 정리

| 설정 | 현재값 | 변경 영향 |
|------|--------|---------|
| `DATA_SOURCE` | `"pykrx"` | `"kis"` 로 변경 시 KIS API 전환 |
| `MARKET` | `"ALL"` | `"KOSPI"` / `"KOSDAQ"` 으로 범위 축소 가능 |
| `RSI_PERIOD` | `14` | 높일수록 완만한 RSI |
| `BB_PERIOD` | `20` | 높일수록 넓은 밴드 |
| `ATR_PERIOD` | `14` | 손절가 민감도 조절 |
| `MIN_VOLUME_SURGE` | `0.5` | 낮출수록 더 많은 종목 통과 |
| `MAX_RSI` | `85` | 높일수록 더 많은 종목 통과 |
| `MIN_MACD_HIST` | `-500` | 낮출수록 더 많은 종목 통과 |
| `MIN_RISK_REWARD` | `0.8` | 낮출수록 더 많은 종목 통과 |
| `MAX_SCAN_STOCKS` | `200` | 높일수록 분석 시간 증가 |
| `STOP_LOSS_ATR_MULT` | `1.5` | 높일수록 손절 범위 넓어짐 |
| `TARGET1_RATIO` | `0.02` | 1차 목표 수익률 |
| `TARGET2_RATIO` | `0.05` | 2차 목표 수익률 |
| `TOP_N_STOCKS` | `10` | 기본 추천 종목 수 |

---

## 10. 실행 방법

### 웹 대시보드

```bash
cd stock_advisor
python -m streamlit run ui/dashboard.py
# 브라우저에서 http://localhost:8501 접속

# 포트 변경 시
python -m streamlit run ui/dashboard.py --server.port 8080
```

### CLI

```bash
cd stock_advisor
python main.py
python main.py --top 5 --invest 500000
python main.py --verbose
```

### 패키지 설치

```bash
pip install -r requirements.txt

# Python 3.14 환경에서 numpy 설치 오류 시
pip install "numpy>=2.0.0" --only-binary :all:

# setuptools 오류 시
pip install "setuptools<71"
```

---

## 11. KIS API 전환 방법

1. **config.py 수정**
   ```python
   DATA_SOURCE    = "kis"
   KIS_APP_KEY    = "발급받은 앱키"
   KIS_APP_SECRET = "발급받은 시크릿"
   KIS_ACCOUNT_NO = "계좌번호 (예: 50012345-01)"
   KIS_IS_MOCK    = False  # 실계좌 사용 시
   ```

2. **kis_fetcher.py에서 미구현 메서드 완성**
   - `get_stock_list()`: FHKUP03500100 API 연동
   - `get_market_cap()`: 상장주식수 × 현재가 계산

3. **나머지 코드 변경 없음** — fetcher.py의 팩토리 패턴이 자동 라우팅

---

## 참고

- pykrx는 비공식 라이브러리로 KRX 서버 응답에 따라 불안정할 수 있음
- 본 도구의 분석 결과는 참고용이며 투자 손실 책임은 본인에게 있음
- 장중 데이터는 약 15분 지연 (pykrx 기준)
