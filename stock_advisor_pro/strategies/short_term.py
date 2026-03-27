# ============================================================
# strategies/short_term.py — 단기 전략 (1주일 내 매매)
# Score = RSI×0.25 + Volume×0.30 + BB×0.25 + MACD×0.20
# ============================================================

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SHORT_TERM_WEIGHTS, SHORT_TERM_MIN_VOLUME, MIN_OHLCV_DAYS
from analysis.indicators import score_rsi, score_volume, score_bb, score_macd


def score(df: pd.DataFrame) -> dict:
    """
    단기 전략 점수 계산.

    Parameters
    ----------
    df : pd.DataFrame
        Columns: open, high, low, close, volume / Index: DatetimeIndex

    Returns
    -------
    dict with keys:
        score      : float [0, 100] or None (데이터 부족 / 거래량 미달)
        rsi        : float
        volume     : float
        bb         : float
        macd       : float
        reason     : str (score=None일 때 사유)
    """
    if len(df) < MIN_OHLCV_DAYS:
        return {"score": None, "reason": f"데이터 부족 ({len(df)}일)"}

    close  = df["close"]
    volume = df["volume"]

    # 거래량 필터
    if volume.iloc[-1] < SHORT_TERM_MIN_VOLUME:
        return {"score": None, "reason": f"거래량 미달 ({int(volume.iloc[-1]):,}주)"}

    s_rsi = score_rsi(close)
    s_vol = score_volume(volume)
    s_bb  = score_bb(close)
    s_mac = score_macd(close)

    sub_scores = {"rsi": s_rsi, "volume": s_vol, "bb": s_bb, "macd": s_mac}

    # NaN이 있으면 제외 후 가중치 재정규화
    w = SHORT_TERM_WEIGHTS.copy()
    valid = {k: v for k, v in sub_scores.items() if not np.isnan(v)}
    if not valid:
        return {"score": None, "reason": "지표 계산 불가"}

    total_w = sum(w[k] for k in valid)
    weighted = sum(valid[k] * w[k] for k in valid) / total_w

    return {
        "score":  round(weighted * 100, 2),
        "rsi":    s_rsi,
        "volume": s_vol,
        "bb":     s_bb,
        "macd":   s_mac,
        "reason": "",
    }
