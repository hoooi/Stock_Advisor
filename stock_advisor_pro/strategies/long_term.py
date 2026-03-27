# ============================================================
# strategies/long_term.py — 장기 전략 (1년 이상 보유)
# Score = MA200×0.25 + MA50×0.20 + 52주고가×0.20 + 거래량트렌드×0.15 + BB폭×0.20
# ============================================================

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import LONG_TERM_WEIGHTS, MIN_OHLCV_DAYS, MA200_PERIOD, MA50_PERIOD
from analysis.indicators import (
    score_ma_position,
    score_week52_high,
    score_volume_trend,
    score_bb_width,
)


def score(df: pd.DataFrame) -> dict:
    """
    장기 전략 점수 계산.

    Parameters
    ----------
    df : pd.DataFrame
        Columns: open, high, low, close, volume / Index: DatetimeIndex

    Returns
    -------
    dict with keys:
        score      : float [0, 100] or None
        ma200      : float
        ma50       : float
        week52     : float
        vol_trend  : float
        bb_width   : float
        reason     : str
    """
    if len(df) < MIN_OHLCV_DAYS:
        return {"score": None, "reason": f"데이터 부족 ({len(df)}일)"}

    close  = df["close"]
    volume = df["volume"]

    s_ma200   = score_ma_position(close, MA200_PERIOD)
    s_ma50    = score_ma_position(close, MA50_PERIOD)
    s_week52  = score_week52_high(close)
    s_vol_tr  = score_volume_trend(volume)
    s_bb_w    = score_bb_width(close)

    sub_scores = {
        "ma200":     s_ma200,
        "ma50":      s_ma50,
        "week52":    s_week52,
        "vol_trend": s_vol_tr,
        "bb_width":  s_bb_w,
    }

    w = LONG_TERM_WEIGHTS.copy()
    valid = {k: v for k, v in sub_scores.items() if not np.isnan(v)}
    if not valid:
        return {"score": None, "reason": "지표 계산 불가"}

    total_w = sum(w[k] for k in valid)
    weighted = sum(valid[k] * w[k] for k in valid) / total_w

    return {
        "score":     round(weighted * 100, 2),
        "ma200":     s_ma200,
        "ma50":      s_ma50,
        "week52":    s_week52,
        "vol_trend": s_vol_tr,
        "bb_width":  s_bb_w,
        "reason":    "",
    }
