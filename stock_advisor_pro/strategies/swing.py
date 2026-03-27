# ============================================================
# strategies/swing.py — 스윙 전략 (1개월 내외 보유)
# Score = EMA크로스×0.30 + MACD×0.25 + ADX×0.25 + 지지선×0.20
# ============================================================

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SWING_WEIGHTS, MIN_OHLCV_DAYS
from analysis.indicators import score_ema_cross, score_macd, score_adx, score_support


def score(df: pd.DataFrame) -> dict:
    """
    스윙 전략 점수 계산.

    Parameters
    ----------
    df : pd.DataFrame
        Columns: open, high, low, close, volume / Index: DatetimeIndex

    Returns
    -------
    dict with keys:
        score      : float [0, 100] or None
        ema_cross  : float
        macd       : float
        adx        : float
        support    : float
        reason     : str
    """
    if len(df) < MIN_OHLCV_DAYS:
        return {"score": None, "reason": f"데이터 부족 ({len(df)}일)"}

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    s_ema  = score_ema_cross(close)
    s_mac  = score_macd(close)
    s_adx  = score_adx(high, low, close)
    s_sup  = score_support(close)

    sub_scores = {"ema_cross": s_ema, "macd": s_mac, "adx": s_adx, "support": s_sup}

    w = SWING_WEIGHTS.copy()
    valid = {k: v for k, v in sub_scores.items() if not np.isnan(v)}
    if not valid:
        return {"score": None, "reason": "지표 계산 불가"}

    total_w = sum(w[k] for k in valid)
    weighted = sum(valid[k] * w[k] for k in valid) / total_w

    return {
        "score":     round(weighted * 100, 2),
        "ema_cross": s_ema,
        "macd":      s_mac,
        "adx":       s_adx,
        "support":   s_sup,
        "reason":    "",
    }
