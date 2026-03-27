# ============================================================
# ui/dashboard.py — Stock Advisor Pro
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import CACHE_TTL_OHLCV, DEFAULT_INVESTMENT, TOP_N_TICKERS
from data.pykrx_source import get_datasource
from analysis.screener import run_screening, get_strategy
from charts.tradingview import render_chart

# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────

_MODE_META = {
    "단기": {"icon": "⚡", "period": "1주일 내외", "color": "#f87171",
             "desc": "RSI 과매도 · 거래량 급증 · 볼린저 하단 · MACD 상향",
             "sub": ["rsi","volume","bb","macd"]},
    "스윙": {"icon": "🔄", "period": "1개월 내외", "color": "#fb923c",
             "desc": "EMA 골든크로스 · MACD · ADX 추세강도 · 지지선",
             "sub": ["ema_cross","macd","adx","support"]},
    "장기": {"icon": "🏔",  "period": "1년 이상",   "color": "#34d399",
             "desc": "MA200 위 · MA50 위 · 52주 고가 · 거래량 증가",
             "sub": ["ma200","ma50","week52","vol_trend","bb_width"]},
}

_COL_KO = {
    "순위":"순위","ticker":"코드","name":"종목명","market":"시장",
    "score":"점수","last_close":"현재가","last_volume":"거래량",
    "rsi":"RSI","volume":"거래량점수","bb":"BB","macd":"MACD",
    "ema_cross":"EMA크로스","adx":"ADX","support":"지지선",
    "ma200":"MA200","ma50":"MA50","week52":"52주고가",
    "vol_trend":"거래량추세","bb_width":"BB폭",
}

# ─────────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Stock Advisor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 브라우저 다크모드 무력화 + 전체 스타일 (st.html 사용 — st.markdown은 style 태그를 텍스트로 렌더링)
st.html("""
<style>
:root { color-scheme: only light !important; }
html, body, [class*="css"] { color-scheme: only light !important; }
html, body { background: #0a0e17 !important; }
.stApp, .stApp > * { background: #0a0e17 !important; }
.block-container { padding: 0 2rem 2rem 2rem !important; max-width: 1400px !important; }
section[data-testid="stSidebar"], button[data-testid="collapsedControl"] { display: none !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0e17; }
::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
#MainMenu, header[data-testid="stHeader"], footer { display: none !important; }
p, span, div, label, h1, h2, h3, h4, h5, h6, li, td, th { color: #e2e8f0 !important; }
div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input { background: #111827 !important; border: 1.5px solid #1f2937 !important; color: #e2e8f0 !important; border-radius: 10px !important; }
div[data-testid="stNumberInput"] input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important; }
div[data-testid="stButton"] > button { background: #1d4ed8 !important; color: #fff !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; font-size: 0.9rem !important; height: 46px !important; }
div[data-testid="stButton"] > button:hover { background: #2563eb !important; box-shadow: 0 6px 20px rgba(37,99,235,0.4) !important; }
div[data-testid="stDownloadButton"] > button { background: #111827 !important; color: #94a3b8 !important; border: 1.5px solid #1f2937 !important; border-radius: 8px !important; font-size: 0.82rem !important; height: 36px !important; }
div[data-testid="stDownloadButton"] > button:hover { border-color: #374151 !important; color: #e2e8f0 !important; }
div[data-testid="stMetric"] { background: #111827 !important; border: 1.5px solid #1f2937 !important; border-radius: 12px !important; padding: 16px 20px !important; }
div[data-testid="stMetricLabel"] p { color: #64748b !important; font-size: 0.73rem !important; text-transform: uppercase; letter-spacing: 0.06em; }
div[data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 1.5rem !important; font-weight: 700 !important; }
div[data-testid="stMetricDelta"] p { color: #64748b !important; font-size: 0.78rem !important; }
div[data-testid="stDataFrame"] { border: 1.5px solid #1f2937 !important; border-radius: 12px !important; overflow: hidden !important; background: #111827 !important; }
div[data-testid="stSelectbox"] > div > div { background: #111827 !important; border: 1.5px solid #1f2937 !important; color: #e2e8f0 !important; border-radius: 10px !important; }
div[data-testid="stProgress"] > div > div > div { background: #3b82f6 !important; border-radius: 4px !important; }
div[data-testid="stProgress"] > div > div { background: #1f2937 !important; border-radius: 4px !important; }
div[data-testid="stStatusContainer"] { background: #111827 !important; border: 1.5px solid #1f2937 !important; border-radius: 12px !important; }
div[data-testid="stAlert"] { background: #111827 !important; border: 1.5px solid #1f2937 !important; border-radius: 12px !important; }
div[data-testid="stRadio"] { display: none !important; }
hr { border-color: #1f2937 !important; margin: 20px 0 !important; }
</style>
""")


# ─────────────────────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────────────────────

if "mode" not in st.session_state:
    st.session_state["mode"] = "단기"
if "df_result" not in st.session_state:
    st.session_state["df_result"] = None
if "investment" not in st.session_state:
    st.session_state["investment"] = DEFAULT_INVESTMENT


# ─────────────────────────────────────────────────────────────
# 캐시
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL_OHLCV, show_spinner=False)
def _cached_ohlcv(ticker: str, years: int):
    return get_datasource().get_ohlcv(ticker, years=years)


# ─────────────────────────────────────────────────────────────
# 헤더 바
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div style="
    display: flex; align-items: center; gap: 12px;
    padding: 24px 0 20px 0;
    border-bottom: 1px solid #1f2937;
    margin-bottom: 28px;
">
    <div style="
        width: 38px; height: 38px; background: linear-gradient(135deg,#1d4ed8,#3b82f6);
        border-radius: 10px; display: flex; align-items: center; justify-content: center;
        font-size: 1.2rem;
    ">📈</div>
    <div>
        <div style="font-size: 1.1rem; font-weight: 800; color: #e2e8f0 !important; letter-spacing: -0.3px;">
            Stock Advisor Pro
        </div>
        <div style="font-size: 0.72rem; color: #475569 !important; margin-top: 1px;">
            한국 주식 멀티 전략 스크리너 · 시가총액 상위 100종목
        </div>
    </div>
    <div style="margin-left: auto; font-size: 0.72rem; color: #475569 !important; text-align: right;">
        ⚠ 투자 참고용 · 손실 책임은 본인에게 있습니다
    </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 컨트롤 바 (모드 선택 + 투자금 + 실행)
# ─────────────────────────────────────────────────────────────

cur_mode = st.session_state["mode"]

col_modes, col_spacer, col_input, col_btn = st.columns([5, 0.3, 2, 1.2])

with col_modes:
    st.markdown('<div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">투자 전략</div>', unsafe_allow_html=True)
    m_cols = st.columns(3)
    for i, (m, meta) in enumerate(_MODE_META.items()):
        with m_cols[i]:
            active = (m == cur_mode)
            border_style = f"border-color:{meta['color']} !important; box-shadow: 0 0 0 1px {meta['color']}40, 0 4px 20px {meta['color']}20;" if active else ""
            dot_color = meta['color'] if active else "#374151"
            if st.button(
                f"{meta['icon']}  **{m}**  ·  {meta['period']}",
                key=f"mode_btn_{m}",
                use_container_width=True,
            ):
                st.session_state["mode"] = m
                st.session_state["df_result"] = None
                st.rerun()
            if active:
                st.markdown(f"""
                <style>
                div[data-testid="stButton"]:has(button[kind="secondary"][key="mode_btn_{m}"]) > button,
                div[data-testid="stButton"]:nth-child({i+1}) > button {{
                    border: 1.5px solid {meta['color']} !important;
                    background: #1a2234 !important;
                    color: {meta['color']} !important;
                }}
                </style>
                """, unsafe_allow_html=True)

with col_input:
    st.markdown('<div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">투자 금액</div>', unsafe_allow_html=True)
    investment = st.number_input(
        "투자금",
        min_value=100_000,
        max_value=100_000_000,
        value=st.session_state["investment"],
        step=100_000,
        format="%d",
        label_visibility="collapsed",
    )
    st.session_state["investment"] = investment

with col_btn:
    st.markdown('<div style="font-size:0.72rem;color:#0a0e17;margin-bottom:8px;">.</div>', unsafe_allow_html=True)
    run_btn = st.button("🔍  스크리닝", use_container_width=True)

# 현재 모드 설명
meta = _MODE_META[cur_mode]
st.markdown(f"""
<div style="
    background: {meta['color']}08;
    border: 1px solid {meta['color']}25;
    border-radius: 8px; padding: 8px 14px; margin: 12px 0 24px 0;
    display: flex; align-items: center; gap: 10px;
">
    <span style="color:{meta['color']};font-size:0.85rem;font-weight:600;">{meta['icon']} {cur_mode} 전략</span>
    <span style="color:#475569;font-size:0.78rem;">{meta['desc']}</span>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 스크리닝 실행
# ─────────────────────────────────────────────────────────────

if run_btn:
    ds = get_datasource()
    prog = st.progress(0, text="")

    with st.status("분석 중...", expanded=True) as status:
        def _cb(done, total, ticker):
            prog.progress(done / max(total, 1), text=f"{done}/{total}  {ticker}")
            st.write(f"`{ticker}`")

        df_r = run_screening(cur_mode, ds, progress_callback=_cb)
        status.update(label=f"✅ 완료  —  {len(df_r)}종목 발견", state="complete", expanded=False)

    prog.empty()

    if df_r.empty:
        st.warning("조건에 맞는 종목이 없습니다.")
        st.stop()

    st.session_state["df_result"] = df_r
    st.rerun()


# ─────────────────────────────────────────────────────────────
# 결과 없는 초기 상태
# ─────────────────────────────────────────────────────────────

df_result = st.session_state.get("df_result")

if df_result is None:
    st.markdown("""
    <div style="
        text-align: center; padding: 80px 0; color: #374151;
    ">
        <div style="font-size: 3rem; margin-bottom: 16px; opacity: 0.4;">📊</div>
        <div style="font-size: 1rem; color: #374151 !important; font-weight: 500;">전략을 선택하고 스크리닝을 시작하세요</div>
        <div style="font-size: 0.8rem; color: #1f2937 !important; margin-top: 8px;">시가총액 상위 100종목을 분석합니다</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ─────────────────────────────────────────────────────────────
# KPI 바
# ─────────────────────────────────────────────────────────────

top_score  = df_result["score"].max()
avg_score  = df_result["score"].mean()
best_row   = df_result.iloc[0]
kospi_cnt  = (df_result["market"] == "KOSPI").sum()
kosdaq_cnt = (df_result["market"] == "KOSDAQ").sum()
_, top_n   = get_strategy(cur_mode)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("결과", f"{len(df_result)}종목", delta=f"상위 {TOP_N_TICKERS}종목 분석")
with k2:
    st.metric("최고 점수", f"{top_score:.1f}")
with k3:
    st.metric("평균 점수", f"{avg_score:.1f}")
with k4:
    st.metric("1위", best_row["name"], delta=best_row["ticker"])
with k5:
    st.metric("시장", f"KOSPI {kospi_cnt}", delta=f"KOSDAQ {kosdaq_cnt}")

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 결과 테이블 + 차트 (좌우 분할)
# ─────────────────────────────────────────────────────────────

col_table, col_chart = st.columns([1, 1.6], gap="large")

with col_table:
    st.markdown(f'<div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;">📋 종목 리스트 — 상위 {top_n}개</div>', unsafe_allow_html=True)

    sub_cols  = meta["sub"]
    show_cols = ["순위","ticker","name","market","score","last_close"] + sub_cols
    show_cols = [c for c in show_cols if c in df_result.columns]
    disp      = df_result[show_cols].copy()
    disp.columns = [_COL_KO.get(c, c) for c in show_cols]

    col_cfg = {
        "점수":  st.column_config.ProgressColumn("점수", min_value=0, max_value=100, format="%.1f"),
        "현재가": st.column_config.NumberColumn("현재가", format="%d원"),
    }
    for c in sub_cols:
        ko = _COL_KO.get(c, c)
        col_cfg[ko] = st.column_config.ProgressColumn(ko, min_value=0, max_value=100, format="%.0f")

    st.dataframe(disp, width="stretch", hide_index=True, column_config=col_cfg,
                 height=min(60 + len(disp) * 36, 500))

    csv = disp.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ CSV", data=csv, file_name=f"screening_{cur_mode}.csv", mime="text/csv")


with col_chart:
    st.markdown('<div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;">📈 차트 분석</div>', unsafe_allow_html=True)

    # 종목 선택
    opts = [f"{r.name}  ({r.ticker})" for r in df_result.itertuples()]
    selected = st.selectbox("종목 선택", options=opts, label_visibility="collapsed")

    if selected:
        sel_name   = selected.rsplit("  (", 1)[0].strip()
        sel_ticker = selected.rsplit("(", 1)[1].rstrip(")")
        sel_row    = df_result[df_result["ticker"] == sel_ticker].iloc[0]
        ohlcv_df   = sel_row["ohlcv"]
        price      = int(sel_row["last_close"])
        score      = sel_row["score"]
        shares     = int(investment / price) if price > 0 else 0

        # 종목 정보 바
        def _sc_color(s):
            return "#34d399" if s >= 70 else "#fb923c" if s >= 50 else "#f87171"

        sc = _sc_color(score)
        sub_html = ""
        for c in sub_cols:
            val = sel_row.get(c)
            if val is not None and isinstance(val, (int, float)) and not np.isnan(val):
                sc2 = _sc_color(val)
                sub_html += f"""
                <div style="flex:1;text-align:center;">
                    <div style="font-size:0.65rem;color:#475569;margin-bottom:3px;">{_COL_KO.get(c,c)}</div>
                    <div style="font-size:0.95rem;font-weight:700;color:{sc2};">{val:.0f}</div>
                    <div style="height:3px;background:#1f2937;border-radius:2px;margin-top:3px;">
                        <div style="width:{min(100,val):.0f}%;height:3px;background:{sc2};border-radius:2px;"></div>
                    </div>
                </div>"""

        st.markdown(f"""
        <div style="background:#111827;border:1.5px solid #1f2937;border-radius:12px;padding:14px 18px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <div>
                    <span style="font-size:1.05rem;font-weight:700;color:#e2e8f0;">{sel_name}</span>
                    <span style="font-size:0.75rem;color:#475569;margin-left:8px;">{sel_ticker} · {sel_row['market']}</span>
                </div>
                <div style="margin-left:auto;text-align:right;">
                    <div style="font-size:0.65rem;color:#475569;">종합 점수</div>
                    <div style="font-size:1.8rem;font-weight:800;color:{sc};line-height:1;">{score:.1f}</div>
                </div>
            </div>
            <div style="display:flex;gap:8px;padding-top:10px;border-top:1px solid #1f2937;">
                {sub_html}
            </div>
        </div>
        <div style="display:flex;gap:10px;margin-bottom:10px;">
            <div style="flex:1;background:#111827;border:1.5px solid #1f2937;border-radius:10px;padding:10px 14px;">
                <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;">현재가</div>
                <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-top:2px;">{price:,}원</div>
            </div>
            <div style="flex:1;background:#111827;border:1.5px solid #1f2937;border-radius:10px;padding:10px 14px;">
                <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;">매수 가능</div>
                <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-top:2px;">{shares:,}주</div>
            </div>
            <div style="flex:1;background:#111827;border:1.5px solid #1f2937;border-radius:10px;padding:10px 14px;">
                <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;">사용 금액</div>
                <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-top:2px;">{shares*price:,}원</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig = render_chart(ohlcv_df, mode=cur_mode, ticker=sel_ticker, name=sel_name)
        st.plotly_chart(fig, width="stretch")
