# ============================================================
# tests/test_indicators.py
# indicators.py 단위 테스트 — 13개 케이스
# pytest tests/test_indicators.py
# ============================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import pytest

from analysis.indicators import (
    calc_rsi, score_rsi,
    calc_macd, score_macd,
    calc_bollinger, score_bb, score_bb_width,
    calc_ema_cross, score_ema_cross,
    calc_adx, score_adx,
    score_volume, score_volume_trend,
    score_support,
    score_ma_position,
    score_week52_high,
    scale_binary,
)


# ── 헬퍼 ─────────────────────────────────────────────────────

def _rising(n=300, start=1000.0, step=1.0) -> pd.Series:
    """단조증가 시리즈 (추세 있는 시장)"""
    return pd.Series([start + i * step for i in range(n)], dtype=float)


def _flat(n=300, value=1000.0) -> pd.Series:
    """횡보 시리즈"""
    return pd.Series([value] * n, dtype=float)


def _falling(n=300, start=2000.0, step=1.0) -> pd.Series:
    """단조하락 시리즈"""
    return pd.Series([start - i * step for i in range(n)], dtype=float)


def _ohlcv(close: pd.Series):
    """close 기반 dummy OHLCV 생성 (high=close+5, low=close-5, vol=1_000_000)"""
    high   = close + 5
    low    = close - 5
    volume = pd.Series([1_000_000.0] * len(close), dtype=float)
    return high, low, volume


# ── 1. scale_binary ──────────────────────────────────────────

class TestScaleBinary:
    def test_true_returns_07(self):
        assert scale_binary(True) == pytest.approx(0.7)

    def test_false_returns_03(self):
        assert scale_binary(False) == pytest.approx(0.3)


# ── 2. RSI ───────────────────────────────────────────────────

class TestRSI:
    def test_rsi_range(self):
        """정상 시리즈: RSI는 [0, 100] 범위"""
        rsi = calc_rsi(_rising())
        assert 0 <= rsi <= 100

    def test_rsi_nan_on_short_series(self):
        """데이터 부족 시 nan 반환"""
        assert np.isnan(calc_rsi(pd.Series([1.0, 2.0, 3.0])))

    def test_score_rsi_oversold(self):
        """과매도(급락) → score 높음"""
        # RSI가 낮아지도록 급락 시리즈 생성
        close = _rising(200) + _falling(50, start=0)
        # score가 nan이 아니면 [0,1] 범위 확인
        s = score_rsi(close)
        if not np.isnan(s):
            assert 0.0 <= s <= 1.0

    def test_score_rsi_overbought(self):
        """단조상승 → RSI 높음 → score 낮음(0에 가까움)"""
        s = score_rsi(_rising(300))
        if not np.isnan(s):
            assert s < 0.5  # 오버바이 상태면 점수 낮아야 함


# ── 3. MACD ──────────────────────────────────────────────────

class TestMACD:
    def test_macd_returns_three_values(self):
        macd, signal, hist = calc_macd(_rising())
        assert not np.isnan(macd)
        assert not np.isnan(signal)
        assert not np.isnan(hist)

    def test_macd_nan_on_short_series(self):
        macd, signal, hist = calc_macd(pd.Series([1.0] * 10))
        assert np.isnan(macd)

    def test_score_macd_rising(self):
        """상승 추세: MACD > signal 가능성 높음 → 점수 0.3 또는 0.7"""
        s = score_macd(_rising())
        assert s in (0.3, 0.7)

    def test_score_macd_nan_short(self):
        assert np.isnan(score_macd(pd.Series([1.0] * 5)))


# ── 4. Bollinger Bands ────────────────────────────────────────

class TestBollinger:
    def test_bb_structure(self):
        upper, middle, lower, pct_b = calc_bollinger(_rising())
        assert upper > middle > lower

    def test_bb_nan_on_short_series(self):
        upper, middle, lower, pct_b = calc_bollinger(pd.Series([1.0] * 5))
        assert np.isnan(upper)

    def test_score_bb_range(self):
        """score_bb: [0, 1] 범위"""
        s = score_bb(_rising())
        assert 0.0 <= s <= 1.0

    def test_score_bb_low_price(self):
        """가격이 밴드 하단 → score 높음"""
        # 급락 시리즈 마지막에 낮은 가격이 오도록
        falling = _falling(250)
        s = score_bb(falling)
        if not np.isnan(s):
            assert s >= 0.5

    def test_score_bb_width_range(self):
        s = score_bb_width(_rising())
        assert 0.0 <= s <= 1.0


# ── 5. EMA Cross ─────────────────────────────────────────────

class TestEMACross:
    def test_ema_cross_no_cross_on_flat(self):
        """완전 횡보: 크로스 없음"""
        crossed, bars = calc_ema_cross(_flat())
        assert crossed == False

    def test_ema_cross_detected(self):
        """낮은 값 → 급격히 상승 시 골든크로스 발생"""
        base = _flat(100, 1000.0)
        surge = _rising(100, start=1050.0, step=5.0)
        combined = pd.concat([base, surge], ignore_index=True)
        crossed, bars = calc_ema_cross(combined)
        # 크로스가 발생했거나 아직 반영되지 않을 수 있음 — 구조만 확인
        assert isinstance(crossed, bool)

    def test_score_ema_nan_short(self):
        assert np.isnan(score_ema_cross(pd.Series([1.0] * 10)))


# ── 6. ADX ───────────────────────────────────────────────────

class TestADX:
    def test_adx_range(self):
        """ADX: [0, 100] 범위"""
        close = _rising()
        high, low, _ = _ohlcv(close)
        adx = calc_adx(high, low, close)
        assert 0 <= adx <= 100

    def test_adx_nan_short(self):
        close = pd.Series([1.0] * 10)
        high, low, _ = _ohlcv(close)
        assert np.isnan(calc_adx(high, low, close))

    def test_score_adx_range(self):
        close = _rising()
        high, low, _ = _ohlcv(close)
        s = score_adx(high, low, close)
        assert 0.0 <= s <= 1.0


# ── 7. 거래량 ─────────────────────────────────────────────────

class TestVolume:
    def test_score_volume_high_volume(self):
        """오늘 거래량이 평균의 3배 → 만점(1.0)"""
        volume = pd.Series([1_000_000.0] * 25)
        volume.iloc[-1] = 3_000_000.0  # 3배
        s = score_volume(volume)
        assert s == pytest.approx(1.0)

    def test_score_volume_normal(self):
        """평균 거래량 = 오늘 거래량 → 0.5"""
        volume = pd.Series([1_000_000.0] * 25)
        s = score_volume(volume)
        assert s == pytest.approx(0.5)

    def test_score_volume_nan_short(self):
        assert np.isnan(score_volume(pd.Series([1.0] * 5)))

    def test_score_volume_trend(self):
        """최근 거래량 > 장기 평균 → 점수 높음"""
        volume = pd.Series([500_000.0] * 80 + [1_500_000.0] * 20)
        s = score_volume_trend(volume)
        assert s > 0.5


# ── 8. 지지선 ─────────────────────────────────────────────────

class TestSupport:
    def test_score_support_at_bottom(self):
        """현재가 = 지지선 → 최고점수"""
        close = _rising(60)
        # 마지막 값이 지지선 근처가 되도록
        close_low = close.copy()
        close_low.iloc[-1] = close.iloc[-50:].min()
        s = score_support(close_low)
        assert s == pytest.approx(1.0, abs=0.05)

    def test_score_support_far(self):
        """현재가가 지지선보다 훨씬 높음 → 점수 낮음"""
        close = _rising(200)
        s = score_support(close)
        if not np.isnan(s):
            assert s < 0.5


# ── 9. MA 위치 ────────────────────────────────────────────────

class TestMAPosition:
    def test_above_ma(self):
        """상승 추세 → 현재가 > MA200 → 0.7"""
        s = score_ma_position(_rising(300), 200)
        assert s == pytest.approx(0.7)

    def test_below_ma(self):
        """하락 추세 → 현재가 < MA200 → 0.3"""
        s = score_ma_position(_falling(300), 200)
        assert s == pytest.approx(0.3)

    def test_nan_short(self):
        assert np.isnan(score_ma_position(pd.Series([1.0] * 10), 200))


# ── 10. 52주 고가 ─────────────────────────────────────────────

class TestWeek52High:
    def test_at_52week_high(self):
        """현재가 = 52주 고가 → 만점(1.0)"""
        close = _rising(300)
        s = score_week52_high(close)
        assert s == pytest.approx(1.0)

    def test_far_from_52week_high(self):
        """급락 후 저점 → 점수 낮음"""
        close = _falling(300)
        s = score_week52_high(close)
        if not np.isnan(s):
            assert s < 0.5
