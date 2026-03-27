# ============================================================
# analysis/indicators.py - 기술적 지표 계산
# ============================================================
# pandas-ta 라이브러리 사용 (Windows ta-lib 설치 불필요)
# ============================================================

from __future__ import annotations
import pandas as pd
import numpy as np
import sys

sys.path.append("../..")
from config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD, ATR_PERIOD
)


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV DataFrame에 모든 기술적 지표 추가.

    Args:
        df: columns=[open, high, low, close, volume]

    Returns:
        지표 컬럼이 추가된 DataFrame
    """
    df = df.copy()
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_volume_ratio(df)
    df = add_moving_averages(df)
    return df


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """
    RSI (Relative Strength Index) 계산.
    - RSI < 30: 과매도 (매수 신호)
    - RSI > 70: 과매수 (매도 신호)
    """
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(com=RSI_PERIOD - 1, min_periods=RSI_PERIOD).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """
    MACD (Moving Average Convergence Divergence) 계산.
    - macd_hist > 0 & 증가 중: 상승 모멘텀
    - macd 선이 signal 선 상향 돌파: 매수 신호 (골든크로스)
    """
    ema_fast = df["close"].ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = df["close"].ewm(span=MACD_SLOW, adjust=False).mean()

    df["macd"]        = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]
    return df


def add_bollinger_bands(df: pd.DataFrame) -> pd.DataFrame:
    """
    볼린저 밴드 계산.
    - close < bb_lower: 과매도 구간 (하단 반등 기대)
    - close > bb_upper: 과매수 구간
    - bb_width: 밴드 폭 (변동성 지표)
    """
    sma = df["close"].rolling(BB_PERIOD).mean()
    std = df["close"].rolling(BB_PERIOD).std()

    df["bb_upper"]  = sma + BB_STD * std
    df["bb_middle"] = sma
    df["bb_lower"]  = sma - BB_STD * std

    band_width = (df["bb_upper"] - df["bb_lower"]).replace(0, float("nan"))
    df["bb_width"]  = band_width / df["bb_middle"].replace(0, float("nan"))

    # 현재 가격의 밴드 내 위치 (0=하단, 1=상단) — 분모 0이면 중립값 0.5
    df["bb_pct"] = (
        (df["close"] - df["bb_lower"]) / band_width
    ).fillna(0.5).clip(0, 1)
    return df


def add_atr(df: pd.DataFrame) -> pd.DataFrame:
    """
    ATR (Average True Range) - 평균 변동폭.
    손절가 계산의 기준으로 사용.
    """
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = true_range.ewm(span=ATR_PERIOD, adjust=False).mean()
    return df


def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    거래량 비율 = 현재 거래량 / 20일 평균 거래량.
    - volume_ratio > 2.0: 거래량 급등 (단타 신호)
    """
    df["volume_ma"] = df["volume"].rolling(period).mean()
    df["volume_ratio"] = (
        df["volume"] / df["volume_ma"].replace(0, float("nan"))
    ).fillna(1.0)
    return df


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """이동평균선 (5일, 20일, 60일)."""
    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    return df


def get_latest_signals(df: pd.DataFrame) -> dict:
    """
    최신 봉의 지표값 및 시그널 요약 반환.

    Returns:
        dict: 지표값 + 시그널 설명 리스트
    """
    if df.empty or len(df) < 30:
        return {}

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    signals = []

    # RSI 신호
    rsi = latest.get("rsi", 50)
    if rsi < 30:
        signals.append(f"RSI 강한 과매도 ({rsi:.1f})")
    elif rsi < 40:
        signals.append(f"RSI 과매도 구간 ({rsi:.1f})")

    # MACD 골든크로스
    if (prev.get("macd", 0) < prev.get("macd_signal", 0) and
            latest.get("macd", 0) > latest.get("macd_signal", 0)):
        signals.append("MACD 골든크로스 (매수 전환)")

    # MACD 히스토그램 증가
    if (latest.get("macd_hist", 0) > 0 and
            latest.get("macd_hist", 0) > prev.get("macd_hist", 0)):
        signals.append("MACD 상승 모멘텀")

    # 볼린저 하단
    bb_pct = latest.get("bb_pct", 0.5)
    if bb_pct < 0.1:
        signals.append(f"볼린저 하단 근접 ({bb_pct:.2f})")

    # 거래량 급등
    vol_ratio = latest.get("volume_ratio", 1.0)
    if vol_ratio >= 3.0:
        signals.append(f"거래량 급등 ({vol_ratio:.1f}배)")
    elif vol_ratio >= 2.0:
        signals.append(f"거래량 증가 ({vol_ratio:.1f}배)")

    # 이동평균 지지
    close = latest.get("close", 0)
    ma20  = latest.get("ma20", 0)
    if ma20 and abs(close - ma20) / ma20 < 0.01:
        signals.append("20일 이평선 지지")

    return {
        "rsi":          round(float(rsi), 2),
        "macd":         round(float(latest.get("macd", 0)), 2),
        "macd_signal":  round(float(latest.get("macd_signal", 0)), 2),
        "macd_hist":    round(float(latest.get("macd_hist", 0)), 2),
        "bb_pct":       round(float(bb_pct), 3),
        "bb_upper":     round(float(latest.get("bb_upper", 0))),
        "bb_lower":     round(float(latest.get("bb_lower", 0))),
        "volume_ratio": round(float(vol_ratio), 2),
        "atr":          round(float(latest.get("atr", 0)), 2),
        "signals":      signals,
        "signal_count": len(signals),
    }
