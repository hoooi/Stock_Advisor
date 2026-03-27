# ============================================================
# config.py - stock_advisor_pro 중앙 설정
# 모든 상수는 여기서 관리. 튜닝 시 이 파일만 수정.
# ============================================================

# ── 실행 환경 ────────────────────────────────────────────────
PORT = 8503
DATA_SOURCE = "pykrx"   # "pykrx" | "kis" (KIS API 전환 시 변경)

# ── 데이터 수집 ──────────────────────────────────────────────
# 지표 계산용 기간 (모든 모드 공통 — ADX/EMA50 워밍업 보장)
OHLCV_YEARS = 2          # 2년치 OHLCV 수집
TOP_N_TICKERS = 100      # 시가총액 상위 N종목 스크리닝

# 캐시 TTL (초)
CACHE_TTL_OHLCV = 3600       # OHLCV: 1시간
CACHE_TTL_TICKERS = 86400    # 종목 리스트: 1일

# ── 단기 전략 설정 ────────────────────────────────────────────
SHORT_TERM_TOP_N = 10

SHORT_TERM_WEIGHTS = {
    "rsi":    0.25,
    "volume": 0.30,
    "bb":     0.25,
    "macd":   0.20,
}
SHORT_TERM_MIN_VOLUME = 1_000_000   # 일 거래량 필터 (주)

# RSI 정규화: RSI < RSI_BUY → 만점, RSI > RSI_NEUTRAL → 0점
SHORT_TERM_RSI_BUY     = 30
SHORT_TERM_RSI_NEUTRAL = 50

# 거래량 정규화: 비율 > VOL_MAX → 만점
SHORT_TERM_VOL_MAX = 2.0   # 20일 평균 대비 2배

# ── 스윙 전략 설정 ────────────────────────────────────────────
SWING_TOP_N = 10

SWING_WEIGHTS = {
    "ema_cross": 0.30,
    "macd":      0.25,
    "adx":       0.25,
    "support":   0.20,
}

EMA_SHORT  = 20
EMA_LONG   = 50
EMA_CROSS_WINDOW = 5   # 최근 N일 이내 크로스만 인정

# ADX 정규화: > ADX_TREND → 만점, < ADX_FLAT → 0점
ADX_PERIOD = 14
ADX_TREND  = 25
ADX_FLAT   = 15

# 지지선: 최근 N일 최저가
SUPPORT_LOOKBACK = 50
SUPPORT_PROXIMITY = 0.05   # 현재가가 지지선의 5% 이내

# ── 장기 전략 설정 ────────────────────────────────────────────
LONG_TERM_TOP_N = 20

LONG_TERM_WEIGHTS = {
    "ma200":     0.25,
    "ma50":      0.20,
    "week52":    0.20,
    "vol_trend": 0.15,
    "bb_width":  0.20,
}

MA200_PERIOD = 200
MA50_PERIOD  = 50

# 52주 위치: 현재가가 52주 고가 대비 N% 이내
WEEK52_HIGH_PROXIMITY = 0.20   # 52주 고가의 80% 이상이면 만점

# 장기 거래량 트렌드: 최근 20일 평균 vs 100일 평균
VOL_TREND_SHORT = 20
VOL_TREND_LONG  = 100

# ── 공통 스코어 ───────────────────────────────────────────────
# 바이너리 신호 스케일링 ([0.3, 0.7])
BINARY_TRUE  = 0.7
BINARY_FALSE = 0.3

# 스크리닝 최소 데이터 요건
MIN_OHLCV_DAYS = 220   # ADX(14) + EMA50 + MA200 워밍업

# ── 가이드라인 ────────────────────────────────────────────────
DEFAULT_INVESTMENT = 1_000_000   # 기본 투자금 (원)
