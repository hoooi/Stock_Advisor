# ============================================================
# analysis/screener.py — 스크리닝 엔진
# get_strategy(mode) factory + run_screening()
# ============================================================

import pandas as pd
import numpy as np
from typing import Callable

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import (
    SHORT_TERM_TOP_N, SWING_TOP_N, LONG_TERM_TOP_N,
    OHLCV_YEARS,
)
import strategies.short_term as _short
import strategies.swing      as _swing
import strategies.long_term  as _long


# ── Strategy factory ──────────────────────────────────────────

def get_strategy(mode: str) -> tuple[Callable, int]:
    """
    투자 유형 → (score 함수, 상위 N)

    Parameters
    ----------
    mode : "단기" | "스윙" | "장기"

    Returns
    -------
    (score_fn, top_n)
    """
    mapping = {
        "단기": (_short.score, SHORT_TERM_TOP_N),
        "스윙": (_swing.score, SWING_TOP_N),
        "장기": (_long.score, LONG_TERM_TOP_N),
    }
    if mode not in mapping:
        raise ValueError(f"알 수 없는 모드: {mode!r}. 선택 가능: {list(mapping)}")
    return mapping[mode]


# ── Screener ──────────────────────────────────────────────────

def run_screening(
    mode: str,
    datasource,
    progress_callback=None,
) -> pd.DataFrame:
    """
    전체 종목 스크리닝 실행.

    Parameters
    ----------
    mode            : "단기" | "스윙" | "장기"
    datasource      : PykrxSource (get_market_tickers / get_ohlcv 구현체)
    progress_callback : callable(done, total, ticker) | None
        UI 진행률 업데이트용 콜백

    Returns
    -------
    pd.DataFrame  — 상위 N종목, 컬럼:
        ticker, name, market, score, [전략별 서브스코어], last_close,
        last_volume, ohlcv (pd.DataFrame, 차트용)
    """
    score_fn, top_n = get_strategy(mode)

    # 종목 리스트
    tickers = datasource.get_market_tickers()

    results = []
    total = len(tickers)

    for i, info in enumerate(tickers):
        ticker = info["ticker"]

        if progress_callback:
            progress_callback(i, total, ticker)

        try:
            df = datasource.get_ohlcv(ticker, years=OHLCV_YEARS)
        except Exception:
            continue

        result = score_fn(df)
        if result["score"] is None:
            continue

        row = {
            "ticker":      ticker,
            "name":        info["name"],
            "market":      info["market"],
            "score":       result["score"],
            "last_close":  int(df["close"].iloc[-1]),
            "last_volume": int(df["volume"].iloc[-1]),
            "ohlcv":       df,          # 차트용 원본 보관
        }
        # 서브스코어 병합
        for k, v in result.items():
            if k not in ("score", "reason"):
                row[k] = round(v * 100, 1) if isinstance(v, float) and not np.isnan(v) else None

        results.append(row)

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)
    df_result.insert(0, "순위", range(1, len(df_result) + 1))

    return df_result
