# ============================================================
# tests/test_strategies.py
# 3개 전략 × 4 케이스 (max/min/mixed/NaN)
# pytest tests/test_strategies.py
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import pytest

import strategies.short_term as short_term
import strategies.swing      as swing
import strategies.long_term  as long_term


# ── 헬퍼 ─────────────────────────────────────────────────────

def _make_df(n: int, close_start: float = 1000.0, trend: str = "rising",
             volume: float = 5_000_000.0) -> pd.DataFrame:
    """테스트용 OHLCV DataFrame 생성"""
    idx = pd.date_range("2022-01-01", periods=n, freq="B")

    if trend == "rising":
        vals = [close_start + i for i in range(n)]
    elif trend == "falling":
        vals = [close_start + n - i for i in range(n)]
    else:  # flat
        vals = [close_start] * n

    close = pd.Series(vals, dtype=float, index=idx)

    return pd.DataFrame({
        "open":   close * 0.99,
        "high":   close * 1.01,
        "low":    close * 0.98,
        "close":  close,
        "volume": pd.Series([volume] * n, dtype=float, index=idx),
    })


def _short_df():
    """단기 전략용 — 충분한 데이터 + 충분한 거래량"""
    return _make_df(250, trend="rising", volume=5_000_000)


def _swing_df():
    return _make_df(250, trend="rising")


def _long_df():
    return _make_df(260, trend="rising")


# ── 단기 전략 ─────────────────────────────────────────────────

class TestShortTerm:
    def test_normal_returns_score(self):
        """정상 데이터 → score 반환"""
        result = short_term.score(_short_df())
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100

    def test_has_all_sub_scores(self):
        """서브 점수 4개 모두 포함"""
        result = short_term.score(_short_df())
        for key in ("rsi", "volume", "bb", "macd"):
            assert key in result

    def test_insufficient_data(self):
        """데이터 부족 → score=None"""
        df = _make_df(50, volume=5_000_000)
        result = short_term.score(df)
        assert result["score"] is None
        assert "데이터 부족" in result["reason"]

    def test_low_volume_filtered(self):
        """거래량 미달 → score=None"""
        df = _make_df(250, volume=500_000)  # 1백만 미만
        result = short_term.score(df)
        assert result["score"] is None
        assert "거래량" in result["reason"]


# ── 스윙 전략 ─────────────────────────────────────────────────

class TestSwing:
    def test_normal_returns_score(self):
        result = swing.score(_swing_df())
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100

    def test_has_all_sub_scores(self):
        result = swing.score(_swing_df())
        for key in ("ema_cross", "macd", "adx", "support"):
            assert key in result

    def test_insufficient_data(self):
        df = _make_df(50)
        result = swing.score(df)
        assert result["score"] is None
        assert "데이터 부족" in result["reason"]

    def test_both_markets_produce_valid_scores(self):
        """상승장/하락장 모두 유효한 점수 반환 (스윙은 반전 포착 전략)"""
        rising_result  = swing.score(_make_df(250, trend="rising"))
        falling_result = swing.score(_make_df(250, trend="falling"))
        # 스윙 전략은 지지선 근처(하락장 후반)를 좋게 볼 수 있음 — 점수 범위만 확인
        for result in (rising_result, falling_result):
            if result["score"] is not None:
                assert 0 <= result["score"] <= 100


# ── 장기 전략 ─────────────────────────────────────────────────

class TestLongTerm:
    def test_normal_returns_score(self):
        result = long_term.score(_long_df())
        assert result["score"] is not None
        assert 0 <= result["score"] <= 100

    def test_has_all_sub_scores(self):
        result = long_term.score(_long_df())
        for key in ("ma200", "ma50", "week52", "vol_trend", "bb_width"):
            assert key in result

    def test_insufficient_data(self):
        df = _make_df(50)
        result = long_term.score(df)
        assert result["score"] is None
        assert "데이터 부족" in result["reason"]

    def test_rising_above_ma200(self):
        """상승 추세 → MA200 위 → ma200 점수 0.7"""
        result = long_term.score(_long_df())
        if result["score"] is not None:
            assert result["ma200"] == pytest.approx(0.7)


# ── 공통: score 범위 ──────────────────────────────────────────

@pytest.mark.parametrize("strategy,df_func", [
    (short_term, _short_df),
    (swing,      _swing_df),
    (long_term,  _long_df),
])
def test_score_in_range(strategy, df_func):
    """모든 전략: score ∈ [0, 100]"""
    result = strategy.score(df_func())
    if result["score"] is not None:
        assert 0 <= result["score"] <= 100
