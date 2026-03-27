# 📈 Danta Advisor

> RSI · MACD · 볼린저밴드 기반 한국 주식 자동 스크리닝 & 매수/매도 가이드라인 도구

---

## 프로젝트 소개

한국 주식(KOSPI/KOSDAQ) 종목을 기술적 지표로 자동 분석해 단타 매매 후보를 추천하는 Streamlit 웹 애플리케이션입니다.
단타·스윙·장기 모두 제공하는 pro 모드는 결제 후 사용 가능합니다.


| 버전 | 경로 | 전략 | 특징 |
|------|------|------|------|
| **stock_advisor** | `stock_advisor/` | 단타 전문 | 시총 상위 200개 자동 스캔, 점수 기반 추천 |
| **stock_advisor_pro** | `stock_advisor_pro/` | 단기 / 스윙 / 장기 | 3가지 전략 전환, TradingView 차트 |

---

## 주요 기능

- 시총 상위 N개 종목 자동 스캔 (pykrx)
- RSI · MACD · 볼린저밴드 · ATR · 거래량 기반 점수 산출
- 매수 구간 / 손절가 / 1차·2차 목표가 자동 계산
- 투자금 기반 분할 매수 수량 및 예상 손익 제공
- Streamlit 웹 대시보드 + Plotly 인터랙티브 차트

---

## 설치

```bash
# 저장소 클론
git clone <your-repo-url>
cd toy-project

# 의존성 설치
pip install -r requirements.txt
```

### 요구 사항

- Python 3.9 이상
- 주요 라이브러리: `pykrx`, `FinanceDataReader`, `streamlit`, `plotly`, `pandas`, `numpy`

---

## 실행 방법

### stock_advisor (단타 전문)

```bash
# 웹 대시보드
streamlit run stock_advisor/ui/dashboard.py --server.port 8501

# CLI
cd stock_advisor
python main.py                  # 기본 (투자금 100만원, 상위 10개)
python main.py --top 5          # 상위 5개 종목
python main.py --invest 500000  # 50만원 기준
```

### stock_advisor_pro (3가지 전략)

```bash
streamlit run stock_advisor_pro/app.py --server.port 8503
```

---

## 화면 구성 (stock_advisor)

| 영역 | 내용 |
|------|------|
| 사이드바 | 투자금 · 추천 종목 수 설정, 분석 시작 버튼, 현재 분석 기준 |
| 추천 종목 리스트 | 점수순 카드형 목록, 매수/매도 가이드라인, 기술적 지표 요약 |
| 종목 상세 차트 | 캔들차트 + 볼린저밴드, RSI, MACD, 거래량 4패널 |

---

## 점수 계산 방식 (stock_advisor)

```
총점 (0~100) = RSI점수 + 거래량점수 + BB점수 + MACD점수 + 시그널보너스

RSI점수   (최대 30점): RSI < 30 → 30점 / RSI < 40 → 20점 / RSI < 50 → 10점
거래량점수 (최대 30점): 거래량배율 × 6 (상한 30점)
BB점수    (최대 20점): 볼린저밴드 하단에 가까울수록 높은 점수
MACD점수  (최대 10점): MACD 히스토그램이 양수일 때 부여
시그널보너스 (최대 10점): 유효 시그널 수 × 3점
```

**등급 기준**

| 등급 | 점수 | 의미 |
|------|------|------|
| S | 70점↑ | 강력 추천 |
| A | 55~69점 | 추천 |
| B | 40~54점 | 관망 |
| C | 40점↓ | 보류 |

---

## 매매 가이드라인 계산 방식

```
매수 구간  = max(BB 하단, 현재가 × 0.995) ~ 현재가 × 1.005
손절가     = 매수 기준가 - (ATR × 1.5)
1차 목표   = 매수 기준가 × 1.02  (+2%)
2차 목표   = 매수 기준가 × 1.05  (+5%)
분할 매수  = 1차 70% / 2차 30%
```

---

## 설정 튜닝 (`stock_advisor/config.py`)

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `DATA_SOURCE` | `"pykrx"` | 데이터 소스 (`"kis"` 변경 시 KIS API 사용) |
| `MAX_SCAN_STOCKS` | `200` | 스캔할 최대 종목 수 |
| `MIN_VOLUME_SURGE` | `0.3` | 최소 거래량 배율 (20일 평균 대비) |
| `MIN_PRICE` | `1,000` | 최소 주가 |
| `MAX_PRICE` | `500,000` | 최대 주가 |
| `MAX_RSI` | `85` | RSI 상한 |
| `STOP_LOSS_ATR_MULT` | `1.5` | 손절 ATR 배수 |
| `TARGET1_RATIO` | `0.02` | 1차 목표 수익률 |
| `TARGET2_RATIO` | `0.05` | 2차 목표 수익률 |
| `TOP_N_STOCKS` | `10` | 기본 추천 종목 수 |

---

## 데이터 소스

현재 기본값은 **pykrx** (한국 주식 비공식 라이브러리)입니다.

- 장중 약 15분 지연
- 별도 인증 불필요
- KIS API로 전환 시 `config.py`에서 `DATA_SOURCE = "kis"` 변경 후 API 키 설정

---

## 프로젝트 구조

```
toy-project/
├── requirements.txt
├── stock_advisor/
│   ├── config.py               # 전역 설정 (SSOT)
│   ├── main.py                 # CLI 진입점
│   ├── data/
│   │   ├── fetcher.py          # 데이터 소스 팩토리
│   │   └── kis_fetcher.py      # KIS API 구현체
│   ├── analysis/
│   │   ├── indicators.py       # 기술적 지표 계산
│   │   ├── screener.py         # 종목 스크리닝
│   │   └── price_guide.py      # 매매 가이드라인 계산
│   └── ui/
│       └── dashboard.py        # Streamlit 웹 UI
└── stock_advisor_pro/
    ├── config.py
    ├── app.py                  # 진입점
    ├── data/
    ├── analysis/
    ├── strategies/
    │   ├── short_term.py       # 단기 전략
    │   ├── swing.py            # 스윙 전략
    │   └── long_term.py        # 장기 전략
    ├── charts/
    └── ui/
```

---

## 테스트

```
# 스톡 스크리닝 테스트
python dashboard_v2
```

---

## 면책사항

> **본 도구는 투자 참고용으로만 제공됩니다.**
> 제공되는 분석 결과는 투자 권유가 아니며, 이를 바탕으로 한 투자 결정 및 손실에 대한 책임은 전적으로 투자자 본인에게 있습니다.
