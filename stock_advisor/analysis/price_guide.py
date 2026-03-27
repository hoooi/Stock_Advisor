# ============================================================
# analysis/price_guide.py - 매수/매도 가이드라인 계산
# ============================================================

from __future__ import annotations
import sys
import pandas as pd

sys.path.append("../..")
from config import (
    STOP_LOSS_ATR_MULT,
    TARGET1_RATIO,
    TARGET2_RATIO,
    MIN_RISK_REWARD,
)


def calculate_price_guide(
    df: pd.DataFrame,
    indicators: dict,
    investment_amount: int = 1_000_000,
) -> dict:
    """
    단타 매수/매도 가이드라인 계산.

    Args:
        df: OHLCV + 지표 DataFrame
        indicators: get_latest_signals() 반환값
        investment_amount: 투자금 (원)

    Returns:
        dict: 매수구간, 손절가, 목표가, 리스크/리워드, 수량 등
    """
    if df.empty or not indicators:
        return {}

    latest = df.iloc[-1]
    close  = float(latest["close"])
    atr    = float(indicators.get("atr", close * 0.015))  # ATR 없으면 1.5% 대체
    bb_lower = float(indicators.get("bb_lower", close))

    # ----------------------------------------------------------
    # 매수 구간 계산
    # 1) 볼린저 하단 ~ 현재가 사이
    # 2) 현재가 기준 ±0.5% 범위
    # ----------------------------------------------------------
    entry_low  = max(bb_lower, close * 0.995)
    entry_high = close * 1.005
    entry_mid  = (entry_low + entry_high) / 2

    # ----------------------------------------------------------
    # 손절가 (Stop Loss)
    # ATR × multiplier 아래로 하락 시 손절
    # ----------------------------------------------------------
    stop_loss = entry_mid - (atr * STOP_LOSS_ATR_MULT)
    stop_loss = _round_price(stop_loss)

    # 손실률
    loss_pct = (entry_mid - stop_loss) / entry_mid

    # ----------------------------------------------------------
    # 목표가
    # ----------------------------------------------------------
    target1 = _round_price(entry_mid * (1 + TARGET1_RATIO))
    target2 = _round_price(entry_mid * (1 + TARGET2_RATIO))

    gain1_pct = (target1 - entry_mid) / entry_mid
    gain2_pct = (target2 - entry_mid) / entry_mid

    # ----------------------------------------------------------
    # 리스크/리워드 비율
    # ----------------------------------------------------------
    risk_reward1 = gain1_pct / loss_pct if loss_pct > 0 else 0
    risk_reward2 = gain2_pct / loss_pct if loss_pct > 0 else 0

    # 최소 R/R 조건 충족 여부
    rr_ok = risk_reward1 >= MIN_RISK_REWARD

    # ----------------------------------------------------------
    # 투자금 기준 매수 수량 계산
    # ----------------------------------------------------------
    qty = int(investment_amount / entry_mid) if entry_mid > 0 else 0
    actual_cost = qty * entry_mid

    # 분할매수 가이드 (1차 70%, 2차 30%)
    qty_first  = int(qty * 0.7)
    qty_second = qty - qty_first

    # ----------------------------------------------------------
    # 예상 손익 계산
    # ----------------------------------------------------------
    expected_profit1 = qty * (target1 - entry_mid)
    expected_profit2 = qty * (target2 - entry_mid)
    expected_loss    = qty * (entry_mid - stop_loss)

    return {
        # 매수
        "entry_low":    _round_price(entry_low),
        "entry_high":   _round_price(entry_high),
        "entry_mid":    _round_price(entry_mid),

        # 손절
        "stop_loss":    stop_loss,
        "loss_pct":     round(loss_pct * 100, 2),

        # 목표가
        "target1":      target1,
        "target1_pct":  round(gain1_pct * 100, 2),
        "target2":      target2,
        "target2_pct":  round(gain2_pct * 100, 2),

        # 리스크/리워드
        "risk_reward1": round(risk_reward1, 2),
        "risk_reward2": round(risk_reward2, 2),
        "rr_ok":        rr_ok,

        # 수량 / 금액
        "investment":   investment_amount,
        "qty_total":    qty,
        "qty_first":    qty_first,    # 1차 매수 (70%)
        "qty_second":   qty_second,   # 2차 매수 (30%)
        "actual_cost":  int(actual_cost),

        # 예상 손익
        "expected_profit1": int(expected_profit1),
        "expected_profit2": int(expected_profit2),
        "expected_loss":    int(expected_loss),
    }


def _round_price(price: float) -> int:
    """한국 주식 호가 단위에 맞게 반올림."""
    if price < 1_000:
        unit = 1
    elif price < 5_000:
        unit = 5
    elif price < 10_000:
        unit = 10
    elif price < 50_000:
        unit = 50
    elif price < 100_000:
        unit = 100
    elif price < 500_000:
        unit = 500
    else:
        unit = 1_000
    return int(round(price / unit) * unit)


def format_price_guide(ticker: str, name: str, guide: dict) -> str:
    """가이드라인을 콘솔 출력용 텍스트로 포맷."""
    rr_badge = "✅" if guide.get("rr_ok") else "⚠️"
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 {name} ({ticker})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 매수 구간   {guide['entry_low']:,} ~ {guide['entry_high']:,}원
🎯 목표가 1차  {guide['target1']:,}원  (+{guide['target1_pct']}%)
🎯 목표가 2차  {guide['target2']:,}원  (+{guide['target2_pct']}%)
🛑 손절가      {guide['stop_loss']:,}원  (-{guide['loss_pct']}%)
{rr_badge} 리스크/리워드  1 : {guide['risk_reward1']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 {guide['investment']:,}원 기준
   1차 매수  {guide['qty_first']}주  (70%)
   2차 매수  {guide['qty_second']}주  (30%)
   예상 수익 1차  +{guide['expected_profit1']:,}원
   예상 손실      -{guide['expected_loss']:,}원
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
