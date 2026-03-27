# ============================================================
# ui/dashboard.py - 단타 어드바이저 대시보드
# 실행: python -m streamlit run ui/dashboard.py --server.port 8502
# ============================================================

from __future__ import annotations
import sys, os, logging
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config import (
    TOP_N_STOCKS, DATA_SOURCE,
    MIN_VOLUME_SURGE, MIN_PRICE, MAX_PRICE, MAX_SCAN_STOCKS,
    MAX_RSI, MIN_MACD_HIST, MIN_RISK_REWARD,
    STOP_LOSS_ATR_MULT, TARGET1_RATIO, TARGET2_RATIO,
    RSI_PERIOD, BB_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
)
from analysis.screener import run_screening
from data.fetcher import get_fetcher
from analysis.indicators import add_all_indicators

logging.basicConfig(level=logging.INFO)

# ── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="단타 어드바이저",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html("""
<style>
[data-testid="stDecoration"]       { display: none !important; }
[data-testid="stToolbar"]          { display: none !important; }
header[data-testid="stHeader"]     { display: none !important; }
footer                             { display: none !important; }
[data-testid="collapsedControl"]        { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
button[kind="header"]                   { display: none !important; }
.block-container { padding-top: 1rem !important; }

/* ── 슬라이더 오른쪽(미선택) 회색 트랙 ── */
[data-baseweb="slider"] > div > div {
    background: #cbd5e1 !important;
}
/* ── 슬라이더 왼쪽(선택) 파란색 채움 ── */
[data-baseweb="slider"] div[role="progressbar"],
[data-baseweb="slider"] div[data-testid="stSliderTrackFill"] {
    background: #2563eb !important;
}
/* ── 슬라이더 썸(동그라미) 파란색 ── */
[data-baseweb="slider"] [role="slider"] {
    background: #2563eb !important;
    border-color: #2563eb !important;
    box-shadow: 0 0 0 4px rgba(37,99,235,0.15) !important;
}
/* ── 슬라이더 값/라벨 텍스트 검정색 ── */
[data-testid="stSlider"] p,
[data-testid="stSlider"] label,
[data-testid="stSlider"] span {
    color: #0f172a !important;
}
/* 전체 색상 변수 오버라이드 */
:root { --primary-color: #2563eb !important; }

/* ── 슬라이더 min/max 항상 표시 ── */
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {
    opacity: 1 !important;
    visibility: visible !important;
}

/* ── 분석 시작 버튼 파란색 ── */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button,
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background-color: #2563eb !important;
    border-color: #2563eb !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background-color: #1d4ed8 !important;
}
</style>
""")

# ── 색상 ─────────────────────────────────────────────────────
C_UP      = "#ef4444"
C_DOWN    = "#3b82f6"
C_SUCCESS = "#16a34a"
C_WARN    = "#d97706"
C_NEUTRAL = "#64748b"
C_PRIMARY = "#2563eb"
C_BORDER  = "#e2e8f0"
C_BG      = "#f8fafc"


# ── 유틸 ─────────────────────────────────────────────────────

def _fmt(n) -> str:
    try:    return f"{int(n):,}"
    except: return str(n)

def _rsi_status(rsi: float):
    if rsi < 30:  return "강한 과매도", C_UP
    if rsi < 40:  return "과매도",      C_WARN
    if rsi < 60:  return "중립",        C_NEUTRAL
    if rsi < 70:  return "과매수",      C_WARN
    return "강한 과매수", C_UP

def _rr_color(rr: float):
    if rr >= 2.0: return C_SUCCESS
    if rr >= 1.5: return C_WARN
    return C_PRIMARY

def _grade(score: float):
    if score >= 70: return "S", "#7c3aed"
    if score >= 55: return "A", C_SUCCESS
    if score >= 40: return "B", C_WARN
    return "C", C_NEUTRAL


# ── 종목 카드 ─────────────────────────────────────────────────

def _render_card(rank: int, row: pd.Series, investment: int):
    rr         = float(row.get("risk_reward", 0))
    rr_c       = _rr_color(rr)
    up         = float(row["change_rate"]) >= 0
    arrow      = "▲" if up else "▼"
    chg_c      = C_UP if up else C_DOWN
    rsi_lbl, rsi_c = _rsi_status(float(row["rsi"]))
    score      = float(row["score"])
    g_lbl, g_c = _grade(score)

    signals_html = ""
    if str(row.get("signals", "")).strip():
        tags = "".join(
            f'<span style="background:#eff6ff;color:{C_PRIMARY};font-size:0.72rem;'
            f'padding:3px 10px;border-radius:12px;border:1px solid #bfdbfe;'
            f'margin:2px 4px 2px 0;display:inline-block;">{s.strip()}</span>'
            for s in str(row["signals"]).split(",") if s.strip()
        )
        signals_html = f'<div style="margin-top:12px;padding-top:10px;border-top:1px solid {C_BORDER};">{tags}</div>'

    st.html(f"""
<div style="background:#fff;border-radius:12px;margin-bottom:14px;overflow:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid {C_BORDER};">
  <div style="background:linear-gradient(135deg,{rr_c}cc,{rr_c});
      padding:13px 20px;display:flex;justify-content:space-between;align-items:center;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="background:rgba(255,255,255,0.25);border-radius:7px;width:28px;height:28px;
          display:flex;align-items:center;justify-content:center;
          font-size:0.78rem;font-weight:800;color:#fff;">#{rank}</div>
      <div>
        <div style="font-size:1rem;font-weight:700;color:#fff;">{row['name']}</div>
        <div style="display:flex;gap:5px;margin-top:3px;">
          <span style="font-size:0.66rem;color:rgba(255,255,255,0.8);background:rgba(0,0,0,0.2);
              padding:1px 7px;border-radius:4px;">{row['ticker']}</span>
          <span style="font-size:0.66rem;color:rgba(255,255,255,0.8);background:rgba(0,0,0,0.2);
              padding:1px 7px;border-radius:4px;">{row['market']}</span>
        </div>
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:1.5rem;font-weight:800;color:#fff;">{_fmt(row['price'])}원</div>
      <div style="font-size:0.78rem;color:rgba(255,255,255,0.85);margin-top:1px;">
        {arrow} {float(row['change_rate']):+.2f}%
      </div>
    </div>
  </div>

  <div style="padding:14px 20px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
      <div style="background:{g_c};color:#fff;font-size:0.9rem;font-weight:800;
          border-radius:6px;width:28px;height:28px;flex-shrink:0;
          display:flex;align-items:center;justify-content:center;">{g_lbl}</div>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
          <span style="font-size:0.72rem;color:{C_NEUTRAL};">추천 점수</span>
          <span style="font-size:0.88rem;font-weight:700;color:{g_c};">{score:.0f}점</span>
        </div>
        <div style="background:#e2e8f0;border-radius:4px;height:5px;overflow:hidden;">
          <div style="background:{g_c};width:{min(int(score),100)}%;height:100%;border-radius:4px;"></div>
        </div>
      </div>
      <div style="display:flex;gap:6px;flex-shrink:0;">
        <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:7px;
            padding:5px 10px;text-align:center;min-width:58px;">
          <div style="font-size:0.6rem;color:{C_NEUTRAL};">RSI</div>
          <div style="font-size:1rem;font-weight:700;color:{rsi_c};">{row['rsi']:.1f}</div>
          <div style="font-size:0.6rem;color:{rsi_c};">{rsi_lbl}</div>
        </div>
        <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:7px;
            padding:5px 10px;text-align:center;min-width:58px;">
          <div style="font-size:0.6rem;color:{C_NEUTRAL};">거래량</div>
          <div style="font-size:1rem;font-weight:700;color:{C_PRIMARY};">{row['volume_ratio']:.1f}x</div>
          <div style="font-size:0.6rem;color:{C_NEUTRAL};">평균 대비</div>
        </div>
        <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:7px;
            padding:5px 10px;text-align:center;min-width:58px;">
          <div style="font-size:0.6rem;color:{C_NEUTRAL};">R/R</div>
          <div style="font-size:1rem;font-weight:700;color:{rr_c};">1:{rr:.1f}</div>
          <div style="font-size:0.6rem;color:{rr_c};">{"우수" if rr>=2 else "양호" if rr>=1.5 else "보통"}</div>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:8px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:700;color:{C_NEUTRAL};
            margin-bottom:10px;display:flex;align-items:center;gap:5px;">
          🛒 매수 / 매도 가이드
        </div>
        <div style="display:flex;flex-direction:column;gap:7px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">🪙 매수 구간</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_PRIMARY};">
              {_fmt(row['entry_low'])} ~ {_fmt(row['entry_high'])}원
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">🎯 1차 목표</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_SUCCESS};">
              {_fmt(row['target1'])}원
              <span style="font-size:0.72rem;font-weight:400;">(+{row['target1_pct']}%)</span>
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">🚀 2차 목표</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_SUCCESS};">
              {_fmt(row['target2'])}원
              <span style="font-size:0.72rem;font-weight:400;">(+{row['target2_pct']}%)</span>
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;
              border-top:1px solid {C_BORDER};padding-top:7px;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">⛔ 손절가</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_UP};">
              {_fmt(row['stop_loss'])}원
              <span style="font-size:0.72rem;font-weight:400;">(-{row['loss_pct']}%)</span>
            </span>
          </div>
        </div>
      </div>

      <div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:8px;padding:12px 14px;">
        <div style="font-size:0.68rem;font-weight:700;color:{C_NEUTRAL};
            margin-bottom:4px;display:flex;align-items:center;gap:5px;">
          🧮 수량 / 수익 예상
        </div>
        <div style="font-size:0.66rem;color:{C_NEUTRAL};margin-bottom:8px;">
          투자금 {_fmt(investment)}원 기준
        </div>
        <div style="display:flex;flex-direction:column;gap:7px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">1차 매수 (70%)</span>
            <span style="font-size:0.85rem;font-weight:700;color:#0f172a;">{_fmt(row['qty_first'])}주</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">2차 매수 (30%)</span>
            <span style="font-size:0.85rem;font-weight:700;color:#0f172a;">{_fmt(row['qty_second'])}주</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;
              border-top:1px solid {C_BORDER};padding-top:7px;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">예상 수익</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_SUCCESS};">+{_fmt(row['expected_profit1'])}원</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.75rem;color:{C_NEUTRAL};">예상 손실</span>
            <span style="font-size:0.85rem;font-weight:700;color:{C_UP};">-{_fmt(row['expected_loss'])}원</span>
          </div>
        </div>
      </div>

    </div>
    {signals_html}
  </div>
</div>
    """)


# ── 차트 ─────────────────────────────────────────────────────

def _render_chart(ticker: str, row: pd.Series):
    fetcher = get_fetcher()
    with st.spinner(f"{ticker} 차트 로딩 중..."):
        df = fetcher.get_ohlcv(ticker, days=60)
        if df is None or df.empty:
            st.error("차트 데이터를 불러올 수 없습니다.")
            return
        df = add_all_indicators(df)

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.52, 0.16, 0.16, 0.16],
        subplot_titles=("가격 · 볼린저밴드 · 이동평균", "RSI", "MACD", "거래량"),
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="OHLC",
        increasing=dict(line=dict(color=C_UP),   fillcolor=C_UP),
        decreasing=dict(line=dict(color=C_DOWN), fillcolor=C_DOWN),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=list(df.index) + list(df.index[::-1]),
        y=list(df["bb_upper"]) + list(df["bb_lower"][::-1]),
        fill="toself", fillcolor="rgba(37,99,235,0.05)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip",
    ), row=1, col=1)

    for col_name, color, name, dash in [
        ("bb_upper",  C_PRIMARY, "BB 상단", "dot"),
        ("bb_middle", C_WARN,    "BB 중단", "solid"),
        ("bb_lower",  C_PRIMARY, "BB 하단", "dot"),
        ("ma5",   "#7c3aed", "MA5",  "solid"),
        ("ma20",  C_WARN,    "MA20", "solid"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col_name],
            line=dict(color=color, width=1.5, dash=dash), name=name, opacity=0.8,
        ), row=1, col=1)

    for y_val, color, label in [
        (row["entry_low"], C_PRIMARY, f"매수 {_fmt(row['entry_low'])}"),
        (row["stop_loss"], C_UP,      f"손절 {_fmt(row['stop_loss'])}"),
        (row["target1"],   C_SUCCESS, f"목표1 {_fmt(row['target1'])}"),
        (row["target2"],   "#059669", f"목표2 {_fmt(row['target2'])}"),
    ]:
        fig.add_hline(
            y=y_val, line_color=color, line_dash="dash", line_width=1.2,
            annotation_text=label, annotation_font=dict(color=color, size=11),
            annotation_position="right", row=1, col=1,
        )

    fig.add_trace(go.Scatter(
        x=df.index, y=df["rsi"],
        line=dict(color="#7c3aed", width=2), fill="tozeroy",
        fillcolor="rgba(124,58,237,0.07)", name="RSI",
    ), row=2, col=1)
    fig.add_hline(y=30, line_color=C_SUCCESS, line_dash="dash", line_width=1, row=2, col=1)
    fig.add_hline(y=70, line_color=C_UP,      line_dash="dash", line_width=1, row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["macd"],
        line=dict(color=C_PRIMARY, width=1.5), name="MACD",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["macd_signal"],
        line=dict(color=C_UP, width=1.5), name="Signal",
    ), row=3, col=1)
    fig.add_trace(go.Bar(
        x=df.index, y=df["macd_hist"],
        marker_color=["rgba(220,38,38,0.65)" if v >= 0 else "rgba(37,99,235,0.65)"
                      for v in df["macd_hist"]], name="Hist",
    ), row=3, col=1)

    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        marker_color=["rgba(220,38,38,0.6)" if c >= o else "rgba(37,99,235,0.6)"
                      for c, o in zip(df["close"], df["open"])], name="거래량",
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["volume_ma"],
        line=dict(color=C_WARN, width=1.5), name="거래량MA",
    ), row=4, col=1)

    fig.update_layout(
        height=820, hovermode="x unified", showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    xanchor="right", x=1, font=dict(size=11)),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(color="#1e293b", family="sans-serif"),
        margin=dict(l=10, r=110, t=45, b=10),
    )
    for i in range(1, 5):
        fig.update_xaxes(showgrid=True, gridcolor="#f1f5f9", linecolor=C_BORDER, row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", linecolor=C_BORDER, row=i, col=1)

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 사이드바
# ============================================================

with st.sidebar:
    st.markdown("## 📈 단타 어드바이저")
    st.caption("기술적 지표 기반 종목 스크리너")

    if DATA_SOURCE == "pykrx":
        st.markdown(
            '<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;'
            'padding:5px 10px;font-size:0.75rem;color:#92400e;margin-bottom:8px;">'
            '⚡ pykrx — 장중 약 15분 지연</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    investment_raw = st.slider("💵 투자금 (만원)", 10, 10_000, 1_000, 10)
    investment = investment_raw * 10_000
    st.caption(f"설정 금액: {investment:,}원")

    if "top_n" not in st.session_state:
        st.session_state["top_n"] = TOP_N_STOCKS
    top_n = st.slider("추천 종목 수", 1, 20, st.session_state["top_n"], 1, key="top_n_slider")
    st.session_state["top_n"] = top_n

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")

    last_run = st.session_state.get("last_run", "미실행")
    st.caption(f"마지막 분석: {last_run}")

    st.markdown(
        '<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;'
        'padding:6px 10px;font-size:0.72rem;color:#78350f;margin-top:6px;">'
        '⚠ 본 자료는 참고용입니다.<br>투자 손실 책임은 본인에게 있습니다.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("⚙️ **현재 분석 기준**")

    conds = [
        ("📋", "스캔 종목",  f"시총 상위 {MAX_SCAN_STOCKS}개"),
        ("📊", "주가 범위",  f"{MIN_PRICE:,} ~ {MAX_PRICE:,}원"),
        ("📈", "거래량",     f"평균의 {MIN_VOLUME_SURGE}배 이상"),
        ("📉", "RSI 상한",   f"{MAX_RSI} 이하"),
        ("📊", "MACD",       f"{int(MIN_MACD_HIST):,} 이상"),
        ("⚖️", "R/R 비율",   f"1:{MIN_RISK_REWARD} 이상"),
    ]
    for icon, k, v in conds:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:4px 0;border-bottom:1px solid #f1f5f9;">'
            f'<span style="font-size:0.75rem;color:#64748b;">{icon} {k}</span>'
            f'<span style="font-size:0.75rem;font-weight:600;color:#0f172a;">{v}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.expander("💡 가이드라인 계산 방식"):
        st.markdown(f"""
<div style="font-size:0.82rem;line-height:1.6;">
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">매수 구간</div>
    <div style="color:#64748b;">볼린저밴드 하단 ~ 현재가 ±0.5% 범위</div>
  </div>
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">손절가</div>
    <div style="color:#64748b;">매수가 − ATR × {STOP_LOSS_ATR_MULT}</div>
    <div style="color:#64748b;">평균 변동폭의 {STOP_LOSS_ATR_MULT}배 이하로 내리면 자동 손절 기준</div>
  </div>
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">1차 목표</div>
    <div style="color:#64748b;">매수가 대비 +{TARGET1_RATIO*100:.0f}% 수익 실현</div>
  </div>
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">2차 목표</div>
    <div style="color:#64748b;">매수가 대비 +{TARGET2_RATIO*100:.0f}% 추가 수익</div>
  </div>
  <div>
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">R/R 비율</div>
    <div style="color:#64748b;">기대수익 ÷ 위험손실</div>
    <div style="color:#64748b;">1:{MIN_RISK_REWARD} 이상 종목만 추천</div>
  </div>
</div>
        """, unsafe_allow_html=True)

    with st.expander("📊 지표 설정값"):
        st.markdown(f"""
<div style="font-size:0.82rem;line-height:1.6;">
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">RSI ({RSI_PERIOD}일)</div>
    <div style="color:#64748b;">30↓ 과매도(매수), 70↑ 과매수(매도 주의)</div>
  </div>
  <div style="margin-bottom:12px;">
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">MACD ({MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL})</div>
    <div style="color:#64748b;">히스토그램 0선 상향돌파 → 상승 신호</div>
  </div>
  <div>
    <div style="font-weight:700;color:#0f172a;margin-bottom:3px;">볼린저밴드 ({BB_PERIOD}일)</div>
    <div style="color:#64748b;">하단 근접 = 반등 가능성 높음</div>
  </div>
</div>
        """, unsafe_allow_html=True)

    with st.expander("🏆 추천 점수 등급 기준"):
        st.markdown("""
<div style="font-size:0.82rem;line-height:1.6;">
  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
    <div style="background:#7c3aed;color:#fff;font-weight:800;border-radius:6px;
        width:26px;height:26px;display:flex;align-items:center;justify-content:center;
        flex-shrink:0;font-size:0.78rem;">S</div>
    <div>
      <div style="font-weight:700;color:#0f172a;">70점 이상 — 강력 추천</div>
      <div style="color:#64748b;font-size:0.78rem;">거래량·RSI·MACD 모두 우수, 즉시 진입 고려</div>
    </div>
  </div>
  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
    <div style="background:#16a34a;color:#fff;font-weight:800;border-radius:6px;
        width:26px;height:26px;display:flex;align-items:center;justify-content:center;
        flex-shrink:0;font-size:0.78rem;">A</div>
    <div>
      <div style="font-weight:700;color:#0f172a;">55~69점 — 추천</div>
      <div style="color:#64748b;font-size:0.78rem;">대부분 조건 충족, 매수 구간 진입 시 유리</div>
    </div>
  </div>
  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
    <div style="background:#d97706;color:#fff;font-weight:800;border-radius:6px;
        width:26px;height:26px;display:flex;align-items:center;justify-content:center;
        flex-shrink:0;font-size:0.78rem;">B</div>
    <div>
      <div style="font-weight:700;color:#0f172a;">40~54점 — 관심 종목</div>
      <div style="color:#64748b;font-size:0.78rem;">일부 조건 충족, 추가 확인 후 진입 권장</div>
    </div>
  </div>
  <div style="display:flex;align-items:flex-start;gap:10px;">
    <div style="background:#94a3b8;color:#fff;font-weight:800;border-radius:6px;
        width:26px;height:26px;display:flex;align-items:center;justify-content:center;
        flex-shrink:0;font-size:0.78rem;">C</div>
    <div>
      <div style="font-weight:700;color:#0f172a;">40점 미만 — 낮은 우선순위</div>
      <div style="color:#64748b;font-size:0.78rem;">최소 조건만 통과, 신중한 접근 필요</div>
    </div>
  </div>
</div>
        """, unsafe_allow_html=True)


# ============================================================
# 메인 영역
# ============================================================

# ── 헤더 배너 ────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);
    border-radius:12px;padding:24px 32px;margin-bottom:20px;">
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:1.8rem;">📈</span>
    <div>
      <div style="font-size:1.4rem;font-weight:800;color:#fff;">단타 어드바이저</div>
      <div style="font-size:0.82rem;color:#bfdbfe;margin-top:2px;">
        RSI · MACD · 볼린저밴드 기반 단타 후보 자동 스크리닝 &amp; 매수/매도 가이드라인
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 스크리닝 실행 ────────────────────────────────────────────
if run_btn:
    prog_text = st.empty()
    prog_bar  = st.progress(0)

    def on_progress(current, total, name):
        prog_text.markdown(f"분석 중: **{name}** &nbsp; `{current} / {total}`")
        prog_bar.progress(current / total)

    df_r = run_screening(
        investment_amount=investment,
        top_n=top_n,
        progress_callback=on_progress,
    )
    prog_text.empty()
    prog_bar.empty()

    st.session_state["result_df"]    = df_r
    st.session_state["investment"]   = investment
    st.session_state["last_run"]     = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state["analysis_ran"] = True
    st.rerun()

result_df    = st.session_state.get("result_df", pd.DataFrame())
saved_inv    = st.session_state.get("investment", investment)
analysis_ran = st.session_state.get("analysis_ran", False)

# ── 탭 ──────────────────────────────────────────────────────
tab_list, tab_chart = st.tabs(["📋  추천 종목 리스트", "📊  종목 상세 차트"])

# ── 추천 종목 리스트 탭 ──────────────────────────────────────
with tab_list:
    if not isinstance(result_df, pd.DataFrame) or result_df.empty:
        if analysis_ran:
            st.warning("조건에 맞는 종목이 없습니다. 사이드바에서 분석 조건을 확인하세요.")
        else:
            st.info("좌측 사이드바에서 **분석 시작** 버튼을 눌러주세요.")
    else:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);
            border:1px solid #86efac;border-radius:10px;
            padding:12px 18px;margin-bottom:16px;
            display:flex;align-items:center;gap:10px;">
          <span style="font-size:1.2rem;">✅</span>
          <span style="font-size:0.95rem;font-weight:600;color:#14532d;">
            오늘의 단타 추천 종목 <strong>{len(result_df)}개</strong>를 찾았습니다
          </span>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("추천 종목",       f"{len(result_df)}개")
        m2.metric("평균 점수",        f"{result_df['score'].mean():.1f}점")
        m3.metric("평균 RSI",         f"{result_df['rsi'].mean():.1f}")
        m4.metric("평균 거래량 배율", f"{result_df['volume_ratio'].mean():.1f}배")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        for rank, (_, row) in enumerate(result_df.iterrows(), 1):
            _render_card(rank, row, saved_inv)

        with st.expander("전체 데이터 테이블"):
            cols = ["ticker","name","market","price","change_rate","score","rsi",
                    "volume_ratio","entry_low","entry_high","stop_loss","target1","target2","risk_reward"]
            st.dataframe(
                result_df[cols].style.format({
                    "price":        "{:,.0f}",
                    "change_rate":  "{:+.2f}%",
                    "score":        "{:.1f}",
                    "rsi":          "{:.1f}",
                    "volume_ratio": "{:.1f}x",
                    "entry_low":    "{:,.0f}",
                    "entry_high":   "{:,.0f}",
                    "stop_loss":    "{:,.0f}",
                    "target1":      "{:,.0f}",
                    "target2":      "{:,.0f}",
                    "risk_reward":  "{:.2f}",
                }),
                use_container_width=True, height=360,
            )

# ── 종목 상세 차트 탭 ────────────────────────────────────────
with tab_chart:
    if not isinstance(result_df, pd.DataFrame) or result_df.empty:
        st.info("먼저 분석을 실행해주세요.")
    else:
        options = {
            f"#{i}  {r['name']} ({r['ticker']})": r["ticker"]
            for i, (_, r) in enumerate(result_df.iterrows(), 1)
        }
        label  = st.selectbox("종목 선택", list(options.keys()))
        ticker = options[label]
        row    = result_df[result_df["ticker"] == ticker].iloc[0]

        rr = float(row["risk_reward"])
        ca, cb, cc, cd, ce = st.columns(5)
        ca.metric("현재가",    f"{_fmt(row['price'])}원",             f"{float(row['change_rate']):+.2f}%")
        cb.metric("매수 구간", f"{_fmt(row['entry_low'])}~{_fmt(row['entry_high'])}")
        cc.metric("손절가",    f"{_fmt(row['stop_loss'])}원",         f"-{row['loss_pct']}%")
        cd.metric("1차 목표",  f"{_fmt(row['target1'])}원",           f"+{row['target1_pct']}%")
        ce.metric("R/R 비율",  f"1 : {rr:.2f}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _render_chart(ticker, row)
