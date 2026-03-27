# ============================================================
# analysis/indicators.py — 순수 지표 계산 함수
# 외부 ta 라이브러리 미사용, 처음부터 직접 구현
# 모든 함수: pd.Series(float) → float (scalar)
# ============================================================

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    SHORT_TERM_RSI_BUY, SHORT_TERM_RSI_NEUTRAL, SHORT_TERM_VOL_MAX,
    EMA_SHORT, EMA_LONG, EMA_CROSS_WINDOW,
    ADX_PERIOD, ADX_TREND, ADX_FLAT,
    SUPPORT_LOOKBACK, SUPPORT_PROXIMITY,
    BINARY_TRUE, BINARY_FALSE,
)


# ── 유틸 ─────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    """지수이동평균 (pandas ewm 기반)"""
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def scale_binary(condition: bool) -> float:
    """바이너리 신호 → [0.3, 0.7] 스케일"""
    return BINARY_TRUE if condition else BINARY_FALSE


# ── RSI ──────────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> float:
    """
    RSI(14) 마지막 값 반환.
    Returns: float or nan
    """
    if len(close) < period + 1:
        return float("nan")

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / last_loss
    return float(100 - 100 / (1 + rs))


def score_rsi(close: pd.Series) -> float:
    """
    RSI 정규화 점수 [0, 1].
    RSI < RSI_BUY(30) → 1.0 (과매도 = 매수 기회)
    RSI > RSI_NEUTRAL(50) → 0.0
    그 사이 선형 보간
    """
    rsi = calc_rsi(close)
    if np.isnan(rsi):
        return float("nan")
    return float(max(0.0, min(1.0, (SHORT_TERM_RSI_NEUTRAL - rsi) / (SHORT_TERM_RSI_NEUTRAL - SHORT_TERM_RSI_BUY))))


# ── MACD ─────────────────────────────────────────────────────

def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD 라인, 시그널 라인, 히스토그램 반환.
    Returns: (macd_line, signal_line, histogram) — 마지막 값 scalar
    """
    if len(close) < slow + signal:
        return float("nan"), float("nan"), float("nan")

    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line

    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def score_macd(close: pd.Series) -> float:
    """
    MACD 바이너리 점수.
    macd > signal → BINARY_TRUE(0.7), 아니면 BINARY_FALSE(0.3)
    """
    macd, signal, _ = calc_macd(close)
    if np.isnan(macd):
        return float("nan")
    return scale_binary(macd > signal)


# ── Bollinger Bands ───────────────────────────────────────────

def calc_bollinger(close: pd.Series, period: int = 20, std_k: float = 2.0):
    """
    볼린저 밴드 upper, middle, lower, %B 반환.
    Returns: (upper, middle, lower, pct_b) — 마지막 값 scalar
    """
    if len(close) < period:
        return float("nan"), float("nan"), float("nan"), float("nan")

    middle = _sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()

    upper = middle + std_k * std
    lower = middle - std_k * std

    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]
    last_close = close.iloc[-1]

    band_width = last_upper - last_lower
    if band_width == 0 or np.isnan(band_width):
        pct_b = float("nan")
    else:
        pct_b = float((last_close - last_lower) / band_width)

    return (
        float(last_upper),
        float(middle.iloc[-1]),
        float(last_lower),
        pct_b,
    )


def score_bb(close: pd.Series) -> float:
    """
    볼린저 밴드 %B 정규화 점수 [0, 1].
    %B 낮을수록 (하단 근처) 매수 기회 → 점수 높음
    score = 1 - %B  (클램프 [0,1])
    """
    _, _, _, pct_b = calc_bollinger(close)
    if np.isnan(pct_b):
        return float("nan")
    return float(max(0.0, min(1.0, 1.0 - pct_b)))


def score_bb_width(close: pd.Series) -> float:
    """
    볼린저 밴드 폭 정규화 점수 [0, 1] — 장기 전략용.
    밴드 폭이 넓을수록(변동성 높음) 점수 높음: width / (2 * std_k * price)
    """
    upper, middle, lower, _ = calc_bollinger(close)
    if np.isnan(upper) or middle == 0:
        return float("nan")
    width_pct = (upper - lower) / middle  # 중간값 대비 밴드 폭
    return float(min(1.0, width_pct / 0.20))  # 20% 이상이면 만점


# ── EMA 크로스 (스윙 전략) ────────────────────────────────────

def calc_ema_cross(close: pd.Series, short: int = EMA_SHORT, long: int = EMA_LONG):
    """
    EMA 골든크로스 감지.
    Returns: (crossed_recently: bool, bars_since_cross: int or None)
    """
    if len(close) < long + EMA_CROSS_WINDOW:
        return False, None

    ema_s = _ema(close, short)
    ema_l = _ema(close, long)
    diff = ema_s - ema_l

    # 부호 전환 감지 (음→양 = 골든크로스)
    cross_indices = []
    for i in range(1, len(diff)):
        if diff.iloc[i - 1] < 0 and diff.iloc[i] >= 0:
            cross_indices.append(i)

    if not cross_indices:
        return False, None

    last_cross = cross_indices[-1]
    bars_since = len(diff) - 1 - last_cross
    crossed_recently = bars_since <= EMA_CROSS_WINDOW

    return crossed_recently, bars_since


def score_ema_cross(close: pd.Series) -> float:
    """
    EMA 크로스 바이너리 점수.
    최근 EMA_CROSS_WINDOW일 이내 골든크로스 → BINARY_TRUE(0.7)
    """
    crossed, _ = calc_ema_cross(close)
    if len(close) < EMA_LONG + EMA_CROSS_WINDOW:
        return float("nan")
    return scale_binary(crossed)


# ── ADX (스윙 전략) ───────────────────────────────────────────

def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = ADX_PERIOD) -> float:
    """
    ADX(14) 마지막 값 반환.
    Wilder 평활화 방식.
    """
    min_len = period * 2 + 1
    if len(close) < min_len:
        return float("nan")

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Directional Movement
    up_move   = high.diff()
    down_move = (-low.diff())

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_s  = pd.Series(plus_dm,  index=close.index).ewm(com=period - 1, adjust=False).mean()
    minus_dm_s = pd.Series(minus_dm, index=close.index).ewm(com=period - 1, adjust=False).mean()
    atr        = tr.ewm(com=period - 1, adjust=False).mean()

    # DI
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di  = 100 * plus_dm_s  / atr.replace(0, np.nan)
        minus_di = 100 * minus_dm_s / atr.replace(0, np.nan)

    dx_denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / dx_denom
    adx = dx.ewm(com=period - 1, adjust=False).mean()

    val = adx.iloc[-1]
    return float("nan") if np.isnan(val) else float(val)


def score_adx(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    """
    ADX 정규화 점수 [0, 1].
    ADX > ADX_TREND(25) → 1.0 (강한 추세)
    ADX < ADX_FLAT(15)  → 0.0 (횡보)
    """
    adx = calc_adx(high, low, close)
    if np.isnan(adx):
        return float("nan")
    return float(max(0.0, min(1.0, (adx - ADX_FLAT) / (ADX_TREND - ADX_FLAT))))


# ── 거래량 비율 (단기 전략) ───────────────────────────────────

def score_volume(volume: pd.Series, window: int = 20) -> float:
    """
    거래량 비율 정규화 점수 [0, 1].
    오늘 거래량 / 20일 평균 거래량 = vol_ratio
    vol_ratio >= SHORT_TERM_VOL_MAX(2.0) → 1.0
    """
    if len(volume) < window + 1:
        return float("nan")

    avg_vol = volume.iloc[-(window + 1):-1].mean()
    if avg_vol == 0 or np.isnan(avg_vol):
        return float("nan")

    vol_ratio = float(volume.iloc[-1]) / avg_vol
    return float(min(1.0, vol_ratio / SHORT_TERM_VOL_MAX))


# ── 거래량 트렌드 (장기 전략) ─────────────────────────────────

def score_volume_trend(volume: pd.Series, short: int = 20, long: int = 100) -> float:
    """
    장기 거래량 트렌드 점수 [0, 1].
    최근 short일 평균 > long일 평균 → BINARY_TRUE(0.7) 방향
    비율: min(1, short_avg / long_avg)
    """
    if len(volume) < long:
        return float("nan")

    short_avg = volume.iloc[-short:].mean()
    long_avg  = volume.iloc[-long:].mean()

    if long_avg == 0 or np.isnan(long_avg):
        return float("nan")

    ratio = short_avg / long_avg
    return float(min(1.0, ratio))


# ── 지지선 (스윙 전략) ────────────────────────────────────────

def score_support(close: pd.Series, lookback: int = SUPPORT_LOOKBACK) -> float:
    """
    지지선 근접도 점수 [0, 1].
    최근 lookback일 최저가를 지지선으로 정의.
    현재가가 지지선의 SUPPORT_PROXIMITY(5%) 이내 → 1.0
    멀어질수록 0.0
    """
    if len(close) < lookback:
        return float("nan")

    support = close.iloc[-lookback:].min()
    current = close.iloc[-1]

    if support == 0 or np.isnan(support):
        return float("nan")

    dist = (current - support) / support  # 지지선 대비 상승폭
    return float(max(0.0, min(1.0, 1.0 - dist / SUPPORT_PROXIMITY)))


# ── MA 위치 (장기 전략) ───────────────────────────────────────

def score_ma_position(close: pd.Series, period: int) -> float:
    """
    현재가 vs MA 위치 점수 [0, 1].
    현재가 > MA → BINARY_TRUE(0.7), 아니면 BINARY_FALSE(0.3)
    """
    if len(close) < period:
        return float("nan")

    ma = _sma(close, period).iloc[-1]
    current = close.iloc[-1]

    if np.isnan(ma):
        return float("nan")

    return scale_binary(current > ma)


# ── 52주 고가 근접도 (장기 전략) ──────────────────────────────

def score_week52_high(close: pd.Series) -> float:
    """
    52주 고가 대비 현재가 위치 점수 [0, 1].
    WEEK52_HIGH_PROXIMITY(0.20): 고가의 80% 이상 → 1.0
    """
    days = min(252, len(close))
    if days < 20:
        return float("nan")

    high_52w = close.iloc[-days:].max()
    current  = close.iloc[-1]

    if high_52w == 0 or np.isnan(high_52w):
        return float("nan")

    from config import WEEK52_HIGH_PROXIMITY
    ratio = current / high_52w  # 1.0 = 52주 고가
    threshold = 1.0 - WEEK52_HIGH_PROXIMITY  # 0.80

    return float(max(0.0, min(1.0, (ratio - threshold) / WEEK52_HIGH_PROXIMITY)))
