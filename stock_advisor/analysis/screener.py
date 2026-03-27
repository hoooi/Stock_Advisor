# ============================================================
# analysis/screener.py - 단타 종목 스크리닝
# ============================================================

from __future__ import annotations
import sys
import time
import logging
from typing import Optional
import pandas as pd

sys.path.append("../..")
from config import (
    MIN_VOLUME_SURGE, MIN_PRICE, MAX_PRICE,
    MIN_MARKET_CAP, RSI_OVERSOLD, TOP_N_STOCKS, MAX_SCAN_STOCKS,
    MAX_RSI, MIN_MACD_HIST, MIN_RISK_REWARD
)
from data.fetcher import get_fetcher
from analysis.indicators import add_all_indicators, get_latest_signals
from analysis.price_guide import calculate_price_guide

logger = logging.getLogger(__name__)


def run_screening(
    investment_amount: int = 1_000_000,
    top_n: int = TOP_N_STOCKS,
    progress_callback=None,
) -> pd.DataFrame:
    """
    전체 종목 단타 스크리닝 실행.

    Args:
        investment_amount: 투자금 (원)
        top_n: 상위 N개 종목 반환
        progress_callback: 진행률 콜백 fn(current, total, ticker_name)

    Returns:
        DataFrame: 추천 종목 + 가이드라인
    """
    fetcher = get_fetcher()

    # 종목 목록 조회 (시총 상위 MAX_SCAN_STOCKS개만 스캔)
    logger.info("종목 목록 조회 중...")
    stock_list = fetcher.get_stock_list()
    stock_list = stock_list.head(MAX_SCAN_STOCKS)
    total = len(stock_list)
    logger.info(f"총 {total}개 종목 분석 시작")

    results = []

    for i, row in stock_list.iterrows():
        ticker = row["ticker"]
        name   = row["name"]
        market = row["market"]

        if progress_callback:
            progress_callback(i + 1, total, name)

        try:
            result = _analyze_single(ticker, name, market, investment_amount)
            if result:
                results.append(result)
        except Exception as e:
            logger.debug(f"{ticker} {name} 분석 오류: {e}")

        # API 호출 딜레이 (pykrx 과부하 방지)
        # [KIS 전환 시] KIS API는 초당 20건 제한 → 딜레이 조정 불필요할 수 있음
        time.sleep(0.1)

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("score", ascending=False).head(top_n)
    df_result = df_result.reset_index(drop=True)
    df_result.index += 1  # 순위 1부터 시작

    return df_result


def _analyze_single(
    ticker: str,
    name: str,
    market: str,
    investment_amount: int,
) -> Optional[dict]:
    """
    단일 종목 분석 및 단타 조건 필터링.

    Returns:
        조건 통과 시 dict, 미통과 시 None
    """
    fetcher = get_fetcher()

    # OHLCV 데이터 수집
    df = fetcher.get_ohlcv(ticker, days=60)
    if df is None or len(df) < 30:
        return None

    # 현재가 필터
    current = fetcher.get_current_price(ticker)
    price = current.get("price", 0)
    if not (MIN_PRICE <= price <= MAX_PRICE):
        return None

    # 지표 계산
    df = add_all_indicators(df)
    ind = get_latest_signals(df)

    if not ind:
        return None

    # ----------------------------------------------------------
    # 단타 스크리닝 조건
    # ----------------------------------------------------------

    # 1. 거래량 조건 (필수)
    if ind.get("volume_ratio", 0) < MIN_VOLUME_SURGE:
        return None

    # 2. RSI 조건 (config MAX_RSI 초과만 제외)
    rsi = ind.get("rsi", 50)
    if rsi > MAX_RSI:
        return None

    # 3. MACD 조건 (config MIN_MACD_HIST 미만만 제외)
    if ind.get("macd_hist", 0) < MIN_MACD_HIST:
        return None

    # 4. 시그널 조건 없음 (점수로만 순위 결정)

    # ----------------------------------------------------------
    # 점수 계산 (높을수록 추천 우선순위 높음)
    # ----------------------------------------------------------
    score = _calculate_score(ind)

    # ----------------------------------------------------------
    # 가이드라인 계산
    # ----------------------------------------------------------
    guide = calculate_price_guide(df, ind, investment_amount)

    # 리스크/리워드 미달 종목 제외
    if not guide.get("rr_ok", False):
        return None

    return {
        "ticker":       ticker,
        "name":         name,
        "market":       market,
        "price":        price,
        "change_rate":  current.get("change_rate", 0),
        "score":        score,

        # 지표
        "rsi":          ind.get("rsi"),
        "macd_hist":    ind.get("macd_hist"),
        "volume_ratio": ind.get("volume_ratio"),
        "bb_pct":       ind.get("bb_pct"),
        "signals":      ", ".join(ind.get("signals", [])),

        # 가이드라인
        "entry_low":    guide.get("entry_low"),
        "entry_high":   guide.get("entry_high"),
        "stop_loss":    guide.get("stop_loss"),
        "loss_pct":     guide.get("loss_pct"),
        "target1":      guide.get("target1"),
        "target1_pct":  guide.get("target1_pct"),
        "target2":      guide.get("target2"),
        "target2_pct":  guide.get("target2_pct"),
        "risk_reward":  guide.get("risk_reward1"),
        "qty_first":    guide.get("qty_first"),
        "qty_second":   guide.get("qty_second"),
        "expected_profit1": guide.get("expected_profit1"),
        "expected_loss":    guide.get("expected_loss"),
    }


def _calculate_score(ind: dict) -> float:
    """
    단타 적합도 점수 계산 (0~100).
    시그널 강도에 따라 가중치 부여.
    """
    score = 0.0

    # RSI (낮을수록 유리, 최대 30점)
    rsi = ind.get("rsi", 50)
    if rsi < 30:
        score += 30
    elif rsi < 40:
        score += 20
    elif rsi < 50:
        score += 10

    # 거래량 급등 (최대 30점)
    vol_ratio = ind.get("volume_ratio", 1.0)
    score += min(vol_ratio * 6, 30)

    # 볼린저 위치 (하단 근접할수록 유리, 최대 20점)
    bb_pct = ind.get("bb_pct", 0.5)
    score += max(0, (0.5 - bb_pct) * 40)

    # MACD 히스토그램 (양수 + 증가 시 가산, 최대 10점)
    macd_hist = ind.get("macd_hist", 0)
    if macd_hist > 0:
        score += min(macd_hist / 100, 10)

    # 시그널 개수 보너스 (최대 10점)
    score += min(ind.get("signal_count", 0) * 3, 10)

    return round(score, 2)
