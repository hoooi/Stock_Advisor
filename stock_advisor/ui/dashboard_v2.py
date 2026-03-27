# ============================================================
# ui/dashboardv2.py - 단타 어드바이저 (Financial Architect Design)
# 실행: python -m streamlit run ui/dashboardv2.py --server.port 8501
# ============================================================

from __future__ import annotations
import sys, os, logging, time, random
from datetime import datetime

import base64
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import FinanceDataReader as fdr

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

# ── 주식 용어 팁 ──────────────────────────────────────────────
_STOCK_TIPS = [
    ("RSI (상대강도지수)", "0~100 사이 값으로, 70 이상이면 과매수, 30 이하면 과매도 신호입니다."),
    ("MACD", "단기·장기 이동평균의 차이로 추세 전환을 포착합니다. 시그널선을 상향 돌파하면 매수 신호."),
    ("볼린저 밴드", "가격이 상단 밴드에 닿으면 과매수, 하단 밴드에 닿으면 과매도 구간으로 봅니다."),
    ("ATR (평균 실제 범위)", "일정 기간의 평균 변동폭으로, 손절 폭을 설정할 때 기준으로 활용합니다."),
    ("거래량 급증", "평소보다 거래량이 갑자기 늘면 세력 진입 또는 큰 이슈 발생 신호일 수 있습니다."),
    ("이동평균선 (MA)", "일정 기간 종가의 평균선입니다. 주가가 MA 위에 있으면 상승 추세로 봅니다."),
    ("골든 크로스", "단기 이동평균이 장기 이동평균을 상향 돌파하는 강세 신호입니다."),
    ("데드 크로스", "단기 이동평균이 장기 이동평균을 하향 돌파하는 약세 신호입니다."),
    ("지지선 / 저항선", "주가가 반복적으로 반등하는 가격대가 지지선, 막히는 가격대가 저항선입니다."),
    ("손익비 (Risk/Reward)", "손절 폭 대비 목표 수익 폭의 비율입니다. 최소 1:2 이상이 유리합니다."),
    ("캔들스틱", "하루의 시·고·저·종가를 시각화한 차트입니다. 패턴으로 다음 방향을 예측합니다."),
    ("시가총액", "주가 × 발행 주식 수로, 기업의 시장 가치를 나타냅니다."),
    ("PER (주가수익비율)", "주가를 주당순이익으로 나눈 값으로, 낮을수록 저평가 가능성이 있습니다."),
    ("공매도", "주식을 빌려서 팔고 나중에 싸게 사서 갚는 하락 베팅 전략입니다."),
    ("단타 (스캘핑)", "수분~수시간 내 짧게 수익을 내는 초단기 매매 전략입니다."),
    ("PBR (주가순자산비율)", "주가를 주당 순자산으로 나눈 값입니다. 1 미만이면 청산가치보다 싸게 거래되는 셈."),
    ("EPS (주당순이익)", "기업의 순이익을 발행 주식 수로 나눈 값으로, 수익성을 판단하는 핵심 지표입니다."),
    ("배당수익률", "주가 대비 배당금의 비율입니다. 안정적인 현금흐름을 원하는 투자자가 중시합니다."),
    ("섹터 순환", "시장 상황에 따라 강세를 보이는 업종이 돌아가며 바뀌는 현상입니다."),
    ("오버행 (Overhang)", "대량의 잠재 매도 물량이 쌓여 주가 상승을 억누르는 압력을 말합니다."),
    ("유동성", "주식을 원하는 가격에 쉽게 사고팔 수 있는 정도입니다. 거래량이 많을수록 유동성이 높습니다."),
    ("스톡캐스틱", "현재 주가가 일정 기간 고·저가 범위 안에서 어느 위치에 있는지 보여주는 지표입니다."),
    ("OBV (On-Balance Volume)", "거래량을 누적해 매수·매도 세력의 힘을 측정하는 보조 지표입니다."),
    ("피벗 포인트", "전일 고·저·종가로 계산한 당일 지지·저항 기준선으로, 단타 매매에 많이 씁니다."),
    ("윌리엄스 %R", "RSI와 유사한 과매수·과매도 지표로, -20 이상이면 과매수, -80 이하면 과매도입니다."),
    ("추세선", "차트의 저점 혹은 고점을 연결한 선으로, 이탈 시 추세 전환 신호로 봅니다."),
    ("갭 (Gap)", "전일 종가와 당일 시가 사이에 거래 없이 벌어진 빈 구간입니다. 갭은 종종 강한 지지·저항이 됩니다."),
    ("삼각수렴", "고점은 낮아지고 저점은 높아지며 가격이 한 점으로 모이는 패턴으로, 곧 큰 방향성이 나옵니다."),
    ("헤드앤숄더", "머리와 양쪽 어깨 모양의 하락 반전 패턴으로, 넥라인 이탈 시 하락이 본격화됩니다."),
    ("더블 바텀", "같은 가격대에서 두 번 반등하는 W자 패턴으로, 강한 지지와 상승 반전 신호입니다."),
    ("매물대", "과거 거래가 집중된 가격 구간으로, 매수·매도 세력이 충돌하는 핵심 가격대입니다."),
    ("ROE (자기자본이익률)", "순이익 ÷ 자기자본으로, 기업이 투자금 대비 얼마나 효율적으로 수익을 내는지 보여줍니다."),
    ("신고가 / 신저가", "일정 기간 내 가장 높거나 낮은 가격입니다. 신고가 돌파는 강한 매수 신호로 봅니다."),
    ("시초가 (시가)", "당일 처음 거래된 가격입니다. 전일 종가 대비 갭이 크면 당일 방향성을 암시합니다."),
    ("상한가 / 하한가", "하루 주가 변동 허용 상한(+30%)과 하한(-30%)입니다. 상한가 이후 연속 상승하는 경우도 있습니다."),
    ("세력", "대규모 자금으로 특정 종목을 의도적으로 움직이는 큰손 투자자를 속칭합니다."),
    ("VI (변동성 완화 장치)", "단기 급등락 시 2분간 단일가 매매로 전환해 가격 충격을 완화하는 제도입니다."),
    ("공시", "기업이 투자자에게 경영 상황을 의무적으로 알리는 정보 공개 제도입니다. 호재·악재의 원천입니다."),
    ("테마주", "정치·경제·사회 이슈와 연관되어 함께 움직이는 종목 군입니다. 모멘텀이 빠르게 사라질 수 있습니다."),
    ("낙폭과대주", "단기간에 크게 하락해 기술적 반등을 기대할 수 있는 종목입니다. 단, 추가 하락 위험도 존재합니다."),
    ("순환매", "시장 주도 섹터가 교체되며 자금이 다음 섹터로 이동하는 현상입니다."),
    ("외국인 수급", "외국인 투자자의 순매수·순매도 동향으로, 대형주 방향성에 큰 영향을 미칩니다."),
    ("기관 수급", "연기금·보험·펀드 등 기관 투자자의 매매 동향으로, 중장기 추세를 좌우하는 경우가 많습니다."),
    ("프로그램 매매", "컴퓨터 알고리즘이 자동으로 실행하는 대량 매매로, 단기 급등락의 원인이 되기도 합니다."),
    ("베이시스", "선물 가격과 현물 가격의 차이입니다. 베이시스가 높으면 프로그램 매수가 유입되기 쉽습니다."),
]

_HERO_IMG_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "hero.png")

@st.cache_data(ttl=300)
def _get_market_indices():
    from datetime import timedelta
    prev = (datetime.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    today = datetime.today().strftime("%Y-%m-%d")
    try:
        kospi  = fdr.DataReader("KS11",    prev, today)["Close"].iloc[-1]
        kosdaq = fdr.DataReader("KQ11",    prev, today)["Close"].iloc[-1]
        usdkrw = fdr.DataReader("USD/KRW", prev, today)["Close"].iloc[-1]
        return round(kospi, 2), round(kosdaq, 2), round(usdkrw, 1)
    except Exception:
        return None, None, None

def _hero_img_src() -> str:
    with open(_HERO_IMG_PATH, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"

st.set_page_config(
    page_title="Danta Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 글로벌 CSS ────────────────────────────────────────────────
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@300;400;500;600&family=Work+Sans:wght@400;500&display=swap');

[data-testid="stDecoration"]            { display: none !important; }
[data-testid="stToolbar"]               { display: none !important; }
header[data-testid="stHeader"]          { display: none !important; }
footer                                  { display: none !important; }
[data-testid="collapsedControl"]        { display: none !important; }
[data-testid="stSidebarCollapseButton"] { display: none !important; }
button[kind="header"]                   { display: none !important; }
.block-container { padding-top: 0 !important; padding-bottom: 2rem !important; }

.stApp { background: #f7f9fb !important; font-family: 'Inter', sans-serif !important; }

/* 사이드바 배경 */
section[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e2e8f0 !important; }
section[data-testid="stSidebar"] > div { background: #ffffff !important; }
section[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif !important; }

/* 슬라이더 라벨 영역 */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: #191c1e !important; font-weight: 600 !important; font-size: 0.8rem !important; }
section[data-testid="stSidebar"] .stCaption p { color: #64748b !important; font-size: 0.68rem !important; }

/* 사이드바 위젯 좌우 패딩 */
section[data-testid="stSidebar"] [data-testid="stSlider"] { padding-left: 12px !important; padding-right: 12px !important; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { padding-left: 12px !important; padding-right: 12px !important; }

/* 사이드바 HTML 블록 사이 gap 제거 */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0 !important; }

/* 슬라이더 hover 툴팁 숨김 */
[data-baseweb="tooltip"] { display: none !important; }
section[data-testid="stSidebar"] div[data-testid="stButton"] { padding-left: 12px !important; padding-right: 12px !important; }

/* 사이드바 details/summary 아코디언 */
details.fin-acc { background: #fff; border-radius: 0.75rem; border: 1px solid #e8edf2; overflow: hidden; box-shadow: 0 2px 12px -3px rgba(0,0,0,0.10); margin-bottom: 8px; }
details.fin-acc > summary { padding: 14px 16px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; list-style: none; font-weight: 700; font-size: 0.75rem; color: #191c1e; font-family: Inter,sans-serif; }
details.fin-acc > summary::-webkit-details-marker { display: none; }
details.fin-acc > summary .acc-icon { font-size: 0.85rem; margin-right: 6px; }
details.fin-acc > summary .acc-arrow { color: #94a3b8; font-size: 0.8rem; transition: transform 0.2s; display: inline-block; }
details.fin-acc[open] > summary .acc-arrow { transform: rotate(180deg); }
details.fin-acc > summary:hover { background: #f8fafc; }
details.fin-acc > .acc-body { padding: 4px 16px 16px; border-top: 1px solid #f1f5f9; }

[data-baseweb="slider"] > div > div { background: #e2e8f0 !important; }
[data-baseweb="slider"] div[role="progressbar"],
[data-baseweb="slider"] div[data-testid="stSliderTrackFill"] { background: #00174a !important; }
[data-baseweb="slider"] [role="slider"] {
    background: #00174a !important; border-color: #00174a !important;
    box-shadow: 0 2px 4px rgba(0,23,74,0.35) !important;
}
[data-testid="stSlider"] p,
[data-testid="stSlider"] label,
[data-testid="stSlider"] span { color: #191c1e !important; }
[data-testid="stTickBarMin"],
[data-testid="stTickBarMax"],
[data-testid="stTickBar"],
[data-testid="stSlider"] > div > div:last-child { display: none !important; }

section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #00174a, #002976) !important;
    border: none !important; color: #ffffff !important;
    border-radius: 0.75rem !important; font-weight: 700 !important;
    font-size: 0.875rem !important; padding: 0.75rem !important;
    box-shadow: 0 4px 15px rgba(0,23,74,0.25) !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #002976, #003ea8) !important;
}

/* ── 종목 선택 셀렉트박스 ── */
[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {
    background: #ffffff !important;
    border: 2px solid #00174a !important;
    border-radius: 0.875rem !important;
    padding: 6px 14px !important;
    box-shadow: 0 4px 20px -4px rgba(0,23,74,0.15) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
    min-height: 52px !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child:hover {
    border-color: #002976 !important;
    box-shadow: 0 4px 24px -4px rgba(0,23,74,0.28) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-container"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-container"] div {
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
}
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p {
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    color: #64748b !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    margin-bottom: 4px !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-radius: 0 !important;
    padding: 0 !important;
    gap: 8px !important;
    border: none !important;
    border-bottom: 2px solid #e2e8f0 !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 0 !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    color: #94a3b8 !important;
    padding: 0.75rem 1.5rem !important;
    background: transparent !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
    letter-spacing: 0.01em !important;
    transition: color 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #00174a !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: transparent !important;
    color: #00174a !important;
    border-bottom: 3px solid #00174a !important;
    box-shadow: none !important;
}
.stTabs [data-baseweb="tab-border"]    { display: none !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

[data-testid="stExpander"] {
    background: #ffffff !important; border: 1px solid #f1f5f9 !important;
    border-radius: 0.75rem !important; overflow: hidden !important;
    box-shadow: 0 2px 12px -3px rgba(0,0,0,0.04) !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    font-weight: 700 !important; font-size: 0.78rem !important; color: #191c1e !important;
}

[data-testid="stMetric"] {
    background: #ffffff !important; border-radius: 0.75rem !important;
    padding: 1rem !important; border: 1px solid #e2e8f0 !important;
    box-shadow: 0 2px 8px -2px rgba(0,0,0,0.04) !important;
}
[data-testid="stMetricLabel"] { color: #454652 !important; font-size: 0.7rem !important; font-weight: 600 !important; }
[data-testid="stMetricValue"] { color: #00174a !important; font-size: 1.4rem !important; font-weight: 800 !important; }

[data-baseweb="select"] > div { border-radius: 0.75rem !important; }
[data-testid="stProgressBar"] > div > div { background: #00174a !important; border-radius: 999px !important; }
</style>
""")

# ── 색상 팔레트 ───────────────────────────────────────────────
C_PRIMARY   = "#00174a"
C_PRIMARY_C = "#002976"
C_SUCCESS   = "#00ad78"
C_DANGER    = "#ba1a1a"
C_WARN      = "#d97706"
C_NEUTRAL   = "#454652"
C_UP        = "#ef4444"
C_DOWN      = "#3b82f6"


# ── 유틸 ─────────────────────────────────────────────────────
def _fmt(n) -> str:
    try:    return f"{int(n):,}"
    except: return str(n)

def _rsi_status(rsi: float):
    if rsi < 30:  return "강한 과매도", C_DANGER
    if rsi < 40:  return "과매도",      C_WARN
    if rsi < 60:  return "중립",        C_NEUTRAL
    if rsi < 70:  return "과매수",      C_WARN
    return "강한 과매수", C_DANGER

def _rr_color(rr: float):
    if rr >= 2.0: return C_SUCCESS
    if rr >= 1.5: return C_WARN
    return C_PRIMARY

def _grade(score: float):
    if score >= 70: return "S", "#8B5CF6"
    if score >= 55: return "A", "#10A37F"
    if score >= 40: return "B", "#EA580C"
    return "C", "#64748B"


# ── 종목 카드 ─────────────────────────────────────────────────
def _render_card(rank: int, row: pd.Series, investment: int):
    rr             = float(row.get("risk_reward", 0))
    rr_c           = _rr_color(rr)
    up             = float(row["change_rate"]) >= 0
    arrow          = "▲" if up else "▼"
    rsi_lbl, rsi_c = _rsi_status(float(row["rsi"]))
    score          = float(row["score"])
    g_lbl, g_c     = _grade(score)

    signals_html = ""
    if str(row.get("signals", "")).strip():
        tags = "".join(
            f'<span style="background:#eff6ff;color:{C_PRIMARY};font-size:0.68rem;'
            f'padding:3px 10px;border-radius:999px;border:1px solid rgba(0,23,74,0.12);'
            f'margin:2px 4px 2px 0;display:inline-block;">{s.strip()}</span>'
            for s in str(row["signals"]).split(",") if s.strip()
        )
        signals_html = f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid #f1f5f9;">{tags}</div>'

    st.html(f"""
<div style="background:#ffffff;border-radius:1.25rem;margin-bottom:16px;overflow:hidden;
    box-shadow:0 2px 12px -3px rgba(0,0,0,0.06);font-family:Inter,sans-serif;">

  <div style="background:linear-gradient(135deg,{C_PRIMARY},{C_PRIMARY_C});
      padding:16px 22px;display:flex;justify-content:space-between;align-items:center;">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="background:rgba(255,255,255,0.15);border-radius:8px;width:30px;height:30px;
          display:flex;align-items:center;justify-content:center;
          font-size:0.72rem;font-weight:800;color:#fff;">#{rank}</div>
      <div>
        <div style="font-size:1rem;font-weight:800;color:#fff;font-family:Manrope,sans-serif;">{row['name']}</div>
        <div style="display:flex;gap:6px;margin-top:4px;">
          <span style="font-size:0.62rem;color:rgba(255,255,255,0.7);background:rgba(255,255,255,0.1);
              padding:2px 8px;border-radius:999px;">{row['ticker']}</span>
          <span style="font-size:0.62rem;color:rgba(255,255,255,0.7);background:rgba(255,255,255,0.1);
              padding:2px 8px;border-radius:999px;">{row['market']}</span>
        </div>
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:1.55rem;font-weight:800;color:#fff;font-family:Manrope,sans-serif;">{_fmt(row['price'])}원</div>
      <div style="font-size:0.76rem;color:rgba(255,255,255,0.8);margin-top:2px;">
        {arrow} {float(row['change_rate']):+.2f}%
      </div>
    </div>
  </div>

  <div style="padding:16px 22px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <div style="background:{g_c};color:#fff;font-size:0.85rem;font-weight:800;
          border-radius:8px;width:30px;height:30px;flex-shrink:0;
          display:flex;align-items:center;justify-content:center;font-family:Manrope,sans-serif;">{g_lbl}</div>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="font-size:0.68rem;color:{C_NEUTRAL};">추천 점수</span>
          <span style="font-size:0.85rem;font-weight:700;color:{g_c};">{score:.0f}점</span>
        </div>
        <div style="background:#f1f5f9;border-radius:999px;height:4px;overflow:hidden;">
          <div style="background:{g_c};width:{min(int(score),100)}%;height:100%;border-radius:999px;"></div>
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-shrink:0;">
        <div style="background:#f7f9fb;border-radius:10px;padding:6px 12px;text-align:center;min-width:60px;">
          <div style="font-size:0.58rem;color:{C_NEUTRAL};">RSI</div>
          <div style="font-size:1rem;font-weight:700;color:{rsi_c};">{row['rsi']:.1f}</div>
          <div style="font-size:0.58rem;color:{rsi_c};">{rsi_lbl}</div>
        </div>
        <div style="background:#f7f9fb;border-radius:10px;padding:6px 12px;text-align:center;min-width:60px;">
          <div style="font-size:0.58rem;color:{C_NEUTRAL};">거래량</div>
          <div style="font-size:1rem;font-weight:700;color:{C_PRIMARY};">{row['volume_ratio']:.1f}x</div>
          <div style="font-size:0.58rem;color:{C_NEUTRAL};">평균 대비</div>
        </div>
        <div style="background:#f7f9fb;border-radius:10px;padding:6px 12px;text-align:center;min-width:60px;">
          <div style="font-size:0.58rem;color:{C_NEUTRAL};">R/R</div>
          <div style="font-size:1rem;font-weight:700;color:{rr_c};">1:{rr:.1f}</div>
          <div style="font-size:0.58rem;color:{rr_c};">{"우수" if rr>=2 else "양호" if rr>=1.5 else "보통"}</div>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div style="background:#f7f9fb;border-radius:10px;padding:14px 16px;">
        <div style="font-size:0.66rem;font-weight:700;color:{C_NEUTRAL};margin-bottom:12px;letter-spacing:0.04em;">
          매수 / 매도 가이드
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">매수 구간</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_PRIMARY};">
              {_fmt(row['entry_low'])} ~ {_fmt(row['entry_high'])}원
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">1차 목표</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_SUCCESS};">
              {_fmt(row['target1'])}원 <span style="font-size:0.68rem;font-weight:400;">(+{row['target1_pct']}%)</span>
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">2차 목표</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_SUCCESS};">
              {_fmt(row['target2'])}원 <span style="font-size:0.68rem;font-weight:400;">(+{row['target2_pct']}%)</span>
            </span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;
              border-top:1px solid #e2e8f0;padding-top:8px;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">손절가</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_DANGER};">
              {_fmt(row['stop_loss'])}원 <span style="font-size:0.68rem;font-weight:400;">(-{row['loss_pct']}%)</span>
            </span>
          </div>
        </div>
      </div>

      <div style="background:#f7f9fb;border-radius:10px;padding:14px 16px;">
        <div style="font-size:0.66rem;font-weight:700;color:{C_NEUTRAL};margin-bottom:4px;letter-spacing:0.04em;">
          수량 / 수익 예상
        </div>
        <div style="font-size:0.62rem;color:{C_NEUTRAL};margin-bottom:10px;">투자금 {_fmt(investment)}원 기준</div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">1차 매수 (70%)</span>
            <span style="font-size:0.82rem;font-weight:700;color:#191c1e;">{_fmt(row['qty_first'])}주</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">2차 매수 (30%)</span>
            <span style="font-size:0.82rem;font-weight:700;color:#191c1e;">{_fmt(row['qty_second'])}주</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;
              border-top:1px solid #e2e8f0;padding-top:8px;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">예상 수익</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_SUCCESS};">+{_fmt(row['expected_profit1'])}원</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.72rem;color:{C_NEUTRAL};">예상 손실</span>
            <span style="font-size:0.82rem;font-weight:700;color:{C_DANGER};">-{_fmt(row['expected_loss'])}원</span>
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
        fill="toself", fillcolor="rgba(0,23,74,0.04)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip",
    ), row=1, col=1)

    for col_name, color, name, dash in [
        ("bb_upper",  C_PRIMARY, "BB 상단", "dot"),
        ("bb_middle", C_WARN,    "BB 중단", "solid"),
        ("bb_lower",  C_PRIMARY, "BB 하단", "dot"),
        ("ma5",       "#8B5CF6", "MA5",     "solid"),
        ("ma20",      C_WARN,    "MA20",    "solid"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col_name],
            line=dict(color=color, width=1.5, dash=dash), name=name, opacity=0.8,
        ), row=1, col=1)

    for y_val, color, label in [
        (row["entry_low"], C_PRIMARY, f"매수 {_fmt(row['entry_low'])}"),
        (row["stop_loss"], C_DANGER,  f"손절 {_fmt(row['stop_loss'])}"),
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
        line=dict(color="#8B5CF6", width=2), fill="tozeroy",
        fillcolor="rgba(139,92,246,0.07)", name="RSI",
    ), row=2, col=1)
    fig.add_hline(y=30, line_color=C_SUCCESS, line_dash="dash", line_width=1, row=2, col=1)
    fig.add_hline(y=70, line_color=C_DANGER,  line_dash="dash", line_width=1, row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["macd"],
        line=dict(color=C_PRIMARY, width=1.5), name="MACD",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["macd_signal"],
        line=dict(color=C_DANGER, width=1.5), name="Signal",
    ), row=3, col=1)
    fig.add_trace(go.Bar(
        x=df.index, y=df["macd_hist"],
        marker_color=["rgba(186,26,26,0.65)" if v >= 0 else "rgba(0,23,74,0.65)"
                      for v in df["macd_hist"]], name="Hist",
    ), row=3, col=1)

    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        marker_color=["rgba(239,68,68,0.6)" if c >= o else "rgba(59,130,246,0.6)"
                      for c, o in zip(df["close"], df["open"])], name="거래량",
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["volume_ma"],
        line=dict(color=C_WARN, width=1.5), name="거래량MA",
    ), row=4, col=1)

    fig.update_layout(
        height=820, hovermode="x unified", showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    xanchor="right", x=1, font=dict(size=11, family="Inter")),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(color="#191c1e", family="Inter, sans-serif"),
        margin=dict(l=10, r=110, t=45, b=10),
    )
    for i in range(1, 5):
        fig.update_xaxes(showgrid=True, gridcolor="#f1f5f9", linecolor="#e2e8f0", row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", linecolor="#e2e8f0", row=i, col=1)

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 사이드바
# ============================================================
with st.sidebar:
    # ── 로고 ──
    st.html("""
<div style="background:#fff;border-radius:0.75rem;padding:16px;margin-bottom:0;
    box-shadow:0 1px 4px rgba(0,0,0,0.06);">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="font-size:1.4rem;color:#ba1a1a;">📈</span>
    <span style="font-size:1.05rem;font-weight:800;color:#191c1e;font-family:Manrope,sans-serif;letter-spacing:-0.02em;">Danta Advisor</span>
  </div>
  <p style="font-size:0.58rem;color:#94a3b8;font-weight:700;letter-spacing:0.12em;margin:0 0 0 30px;text-transform:uppercase;">기술적 지표 기반 종목 스크리너</p>
</div>
    """)

    # ── 스크리너 설정 + 분석 정보 카드 ──
    st.html("""
<div style="background:#fff;border-radius:0.75rem 0.75rem 0 0;padding:14px 16px 10px;
    border-bottom:1px solid #f1f5f9;box-shadow:0 1px 4px rgba(0,0,0,0.04);margin-top:0;">
    """)

    _invest_opts = [f"{v:,}만원" for v in range(10, 10_001, 10)]
    _invest_sel  = st.select_slider("투자금 (만원)", options=_invest_opts, value="1,000만원")
    investment_raw = int(_invest_sel.replace(",", "").replace("만원", ""))
    investment = investment_raw * 10_000

    if "top_n" not in st.session_state:
        st.session_state["top_n"] = TOP_N_STOCKS
    top_n = st.slider("추천 종목 수", 1, 20, st.session_state["top_n"], 1, key="top_n_slider", format="%d개")
    st.session_state["top_n"] = top_n

    run_btn = st.button("🔍 분석 시작", use_container_width=True, type="primary")

    st.html("""

  <div style="border-left:2px solid #fcd34d;padding:4px 8px;font-size:0.65rem;color:#78350f;line-height:1.5;">
    ⚠ 본 자료는 참고용입니다. 투자 손실 책임은 본인에게 있습니다.
  </div>
</div>
    """)

    # ── 현재 분석 기준 카드 ──
    st.html(f"""
<div style="background:#fff;border-radius:0.75rem;overflow:hidden;
    box-shadow:0 2px 12px -3px rgba(0,0,0,0.04);margin-bottom:8px;">
  <div style="padding:12px 16px;border-bottom:1px solid #f8fafc;display:flex;align-items:center;gap:6px;">
    <span style="font-size:0.7rem;font-weight:700;color:#191c1e;">⚙ 현재 분석 기준</span>
  </div>
  <div style="font-family:Inter,sans-serif;">
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f8fafc;">
      <span style="font-size:0.68rem;color:#64748b;">📋 스캔 종목</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">시총 상위 {MAX_SCAN_STOCKS}개</span>
    </div>
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f8fafc;">
      <span style="font-size:0.68rem;color:#64748b;">💰 주가 범위</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">{MIN_PRICE:,} ~ {MAX_PRICE:,}원</span>
    </div>
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f8fafc;">
      <span style="font-size:0.68rem;color:#64748b;">📈 거래량</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">평균의 {MIN_VOLUME_SURGE}배 이상</span>
    </div>
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f8fafc;">
      <span style="font-size:0.68rem;color:#64748b;">📉 RSI 상한</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">{MAX_RSI} 이하</span>
    </div>
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f8fafc;">
      <span style="font-size:0.68rem;color:#64748b;">📊 MACD</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">{int(MIN_MACD_HIST):,} 이상</span>
    </div>
    <div style="padding:7px 16px;display:flex;justify-content:space-between;align-items:center;">
      <span style="font-size:0.68rem;color:#64748b;">⚖ R/R 비율</span>
      <span style="font-size:0.68rem;font-weight:700;color:#191c1e;">1:{MIN_RISK_REWARD} 이상</span>
    </div>
  </div>
</div>
    """)

    # ── 가이드라인 계산 방식 아코디언 ──
    st.html(f"""
<details class="fin-acc">
  <summary>
    <span><span class="acc-icon">💡</span>가이드라인 계산 방식</span>
    <span class="acc-arrow">▾</span>
  </summary>
  <div class="acc-body" style="font-family:Inter,sans-serif;font-size:0.78rem;line-height:1.7;">
    <div style="margin-bottom:10px;margin-top:8px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">매수 구간</div>
      <div style="color:#64748b;">볼린저밴드 하단 ~ 현재가 ±0.5% 범위</div>
    </div>
    <div style="margin-bottom:10px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">손절가</div>
      <div style="font-weight:600;color:#191c1e;">매수가 − ATR × {STOP_LOSS_ATR_MULT}</div>
      <div style="color:#64748b;font-size:0.7rem;">평균 변동폭의 {STOP_LOSS_ATR_MULT}배 이하 기준</div>
    </div>
    <div style="margin-bottom:10px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">1차 목표</div>
      <div style="color:#64748b;">매수가 대비 +{TARGET1_RATIO*100:.0f}% 수익 실현</div>
    </div>
    <div style="margin-bottom:10px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">2차 목표</div>
      <div style="color:#64748b;">매수가 대비 +{TARGET2_RATIO*100:.0f}% 추가 수익</div>
    </div>
    <div>
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">R/R 비율</div>
      <div style="font-weight:600;color:#191c1e;">기대수익 ÷ 위험손실</div>
      <div style="color:#64748b;font-size:0.7rem;">1:{MIN_RISK_REWARD} 이상 종목만 추천</div>
    </div>
  </div>
</details>
    """)

    # ── 지표 설정값 아코디언 ──
    st.html(f"""
<details class="fin-acc">
  <summary>
    <span><span class="acc-icon">📊</span>지표 설정값</span>
    <span class="acc-arrow">▾</span>
  </summary>
  <div class="acc-body" style="font-family:Inter,sans-serif;font-size:0.78rem;line-height:1.7;">
    <div style="margin-bottom:10px;margin-top:8px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">RSI ({RSI_PERIOD}일)</div>
      <div style="color:#64748b;">30↓ 과매도(매수), 70↑ 과매수(매도 주의)</div>
    </div>
    <div style="margin-bottom:10px;">
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">MACD ({MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL})</div>
      <div style="color:#64748b;">히스토그램 0선 상향돌파 → 상승 신호</div>
    </div>
    <div>
      <div style="font-weight:700;color:#191c1e;margin-bottom:2px;">볼린저밴드 ({BB_PERIOD}일)</div>
      <div style="color:#64748b;">하단 근접 = 반등 가능성 높음</div>
    </div>
  </div>
</details>
    """)

    # ── 추천 점수 등급 기준 아코디언 ──
    st.html("""
<details class="fin-acc">
  <summary>
    <span><span class="acc-icon">🏆</span>추천 점수 등급 기준</span>
    <span class="acc-arrow">▾</span>
  </summary>
  <div class="acc-body" style="font-family:Inter,sans-serif;">
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;margin-top:8px;">
      <div style="background:#8B5CF6;color:#fff;font-weight:800;border-radius:6px;
          width:24px;height:24px;display:flex;align-items:center;justify-content:center;
          flex-shrink:0;font-size:0.72rem;">S</div>
      <div>
        <div style="font-weight:700;color:#191c1e;font-size:0.75rem;">70점 이상 — 강력 추천</div>
        <div style="color:#64748b;font-size:0.68rem;">거래량·RSI·MACD 모두 우수, 즉시 진입 고려</div>
      </div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
      <div style="background:#10A37F;color:#fff;font-weight:800;border-radius:6px;
          width:24px;height:24px;display:flex;align-items:center;justify-content:center;
          flex-shrink:0;font-size:0.72rem;">A</div>
      <div>
        <div style="font-weight:700;color:#191c1e;font-size:0.75rem;">55~69점 — 추천</div>
        <div style="color:#64748b;font-size:0.68rem;">대부분 조건 충족, 매수 구간 진입 시 유리</div>
      </div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
      <div style="background:#EA580C;color:#fff;font-weight:800;border-radius:6px;
          width:24px;height:24px;display:flex;align-items:center;justify-content:center;
          flex-shrink:0;font-size:0.72rem;">B</div>
      <div>
        <div style="font-weight:700;color:#191c1e;font-size:0.75rem;">40~54점 — 관심 종목</div>
        <div style="color:#64748b;font-size:0.68rem;">일부 조건 충족, 추가 확인 후 진입 권장</div>
      </div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;">
      <div style="background:#64748B;color:#fff;font-weight:800;border-radius:6px;
          width:24px;height:24px;display:flex;align-items:center;justify-content:center;
          flex-shrink:0;font-size:0.72rem;">C</div>
      <div>
        <div style="font-weight:700;color:#191c1e;font-size:0.75rem;">40점 미만 — 낮은 우선순위</div>
        <div style="color:#64748b;font-size:0.68rem;">최소 조건만 통과, 신중한 접근 필요</div>
      </div>
    </div>
  </div>
</details>
    """)


# ============================================================
# 메인 영역
# ============================================================

# ── 글라스 헤더 ────────────────────────────────────────────────
_kospi, _kosdaq, _usdkrw = _get_market_indices()
_kospi_str  = f"{_kospi:,.2f}"  if _kospi  else "–"
_kosdaq_str = f"{_kosdaq:,.2f}" if _kosdaq else "–"
_usdkrw_str = f"{_usdkrw:,.1f}" if _usdkrw else "–"

_pykrx_badge = (
    '<span style="margin-left:auto;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;'
    'padding:3px 8px;font-size:0.68rem;font-weight:600;color:#92400e;white-space:nowrap;">'
    '⏱ pykrx — 장중 약 15분 지연</span>'
) if DATA_SOURCE == "pykrx" else ""

st.html(f"""
<div style="background:rgba(247,249,251,0.92);border-bottom:1px solid rgba(226,232,240,0.6);
    padding:14px 0;margin-bottom:24px;display:flex;align-items:center;gap:24px;">
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="width:7px;height:7px;border-radius:50%;background:#10b981;display:inline-block;"></span>
    <span style="font-size:0.72rem;font-weight:700;color:#454652;font-family:Inter,sans-serif;">KOSPI {_kospi_str}</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="width:7px;height:7px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
    <span style="font-size:0.72rem;font-weight:700;color:#454652;font-family:Inter,sans-serif;">KOSDAQ {_kosdaq_str}</span>
  </div>
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="width:7px;height:7px;border-radius:50%;background:#3b82f6;display:inline-block;"></span>
    <span style="font-size:0.72rem;font-weight:700;color:#454652;font-family:Inter,sans-serif;">USD/KRW {_usdkrw_str}</span>
  </div>
  {_pykrx_badge}
</div>
""")

# ── 히어로 배너 ────────────────────────────────────────────────
st.html(f"""
<div style="position:relative;height:220px;border-radius:1.5rem;overflow:hidden;
    margin-bottom:28px;box-shadow:0 20px 60px -10px rgba(0,23,74,0.3);">
  <!-- 배경 이미지 -->
  <img src="{_hero_img_src()}"
       style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform 0.7s ease;"
       onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'"/>
  <!-- 좌→우 그라데이션 오버레이 (이미지 위에 얹음) -->
  <div style="position:absolute;inset:0;
      background:linear-gradient(to right, rgba(0,23,74,0.92) 0%, rgba(0,41,118,0.5) 55%, rgba(0,62,168,0.05) 100%);"></div>
  <!-- 텍스트 콘텐츠 -->
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;
      justify-content:center;padding:0 48px;">
    <span style="color:#6ffbbe;font-size:0.6rem;font-weight:700;letter-spacing:0.2em;
        text-transform:uppercase;margin-bottom:12px;
        background:rgba(111,251,190,0.12);width:fit-content;padding:3px 10px;border-radius:999px;">
      A Scalping Screener, Built for You
    </span>
    <h2 style="color:#ffffff;font-size:1.75rem;font-weight:800;line-height:1.35;margin:0;
        font-family:Manrope,sans-serif;letter-spacing:-0.02em;">
      안녕하세요,<br/>정밀한 기술적 분석을 시작할까요?
    </h2>
  </div>
</div>
""")

# ── 스크리닝 실행 ─────────────────────────────────────────────
if run_btn:
    prog_text = st.empty()
    prog_bar  = st.progress(0)
    tip_box   = st.empty()

    _tip_state = {
        "last_time": time.time(),
        "idx": random.randrange(len(_STOCK_TIPS)),
    }

    def _render_tip(box):
        term, desc = _STOCK_TIPS[_tip_state["idx"]]
        box.markdown(
            f"""<div style="display:flex;justify-content:center;margin-top:64px;">
              <div style="background:#ffffff;border:1.5px solid #e2e8f0;border-radius:1rem;
                  padding:18px 24px;max-width:520px;width:100%;
                  box-shadow:0 4px 16px -4px rgba(0,23,74,0.08);text-align:center;">
                <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;
                    color:#94a3b8;text-transform:uppercase;margin-bottom:6px;">
                  📖 잠깐, 이런 용어 알고 계세요?
                </div>
                <div style="font-size:1rem;font-weight:800;color:#00174a;margin-bottom:6px;">
                  {term}
                </div>
                <div style="font-size:0.8rem;color:#475569;line-height:1.7;">{desc}</div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    _render_tip(tip_box)

    def on_progress(current, total, name):
        prog_text.markdown(f"**{name}** &nbsp; `{current} / {total}`")
        prog_bar.progress(current / total)
        if time.time() - _tip_state["last_time"] >= 3:
            _tip_state["idx"] = (_tip_state["idx"] + random.randint(1, len(_STOCK_TIPS) - 1)) % len(_STOCK_TIPS)
            _tip_state["last_time"] = time.time()
            _render_tip(tip_box)

    df_r = run_screening(
        investment_amount=investment,
        top_n=top_n,
        progress_callback=on_progress,
    )
    tip_box.empty()
    prog_text.empty()
    prog_bar.empty()

    st.session_state["result_df"]    = df_r
    st.session_state["investment"]   = investment
    st.session_state["analysis_ran"] = True
    st.rerun()

result_df    = st.session_state.get("result_df", pd.DataFrame())
saved_inv    = st.session_state.get("investment", investment)
analysis_ran = st.session_state.get("analysis_ran", False)

# ── 탭 ───────────────────────────────────────────────────────
tab_list, tab_chart = st.tabs(["📋  추천 종목 리스트", "📊  종목 상세 차트"])

# ── 추천 종목 리스트 탭 ───────────────────────────────────────
with tab_list:
    if not isinstance(result_df, pd.DataFrame) or result_df.empty:
        if analysis_ran:
            st.warning("조건에 맞는 종목이 없습니다. 사이드바에서 분석 조건을 확인하세요.")
        else:
            st.html("""
<div style="background:#ffffff;border-radius:1.25rem;min-height:400px;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:60px 40px;text-align:center;
    box-shadow:0 2px 12px -3px rgba(0,0,0,0.05);border:1px solid #f1f5f9;
    font-family:Inter,sans-serif;">
  <div style="width:80px;height:80px;background:#f7f9fb;border:1px solid #e2e8f0;
      border-radius:50%;display:flex;align-items:center;justify-content:center;
      margin-bottom:20px;font-size:2.2rem;">🔍</div>
  <h4 style="font-size:1.2rem;font-weight:800;color:#00174a;margin:0 0 10px 0;
      font-family:Manrope,sans-serif;">분석된 종목이 없습니다</h4>
  <p style="color:#64748b;font-size:0.875rem;max-width:340px;line-height:1.75;margin:0;">
    좌측 사이드바의 <strong>'분석 시작'</strong> 버튼을 눌러<br>
    현재 시장에서 가장 가능성 높은 단타 종목을 발굴하세요.
  </p>
  <div style="margin-top:40px;display:grid;grid-template-columns:repeat(3,1fr);gap:40px;
      border-top:1px solid #f1f5f9;padding-top:36px;width:100%;max-width:560px;">
    <div style="text-align:center;">
      <div style="font-size:1.6rem;margin-bottom:8px;color:#b4c5ff;">✅</div>
      <p style="font-weight:700;font-size:0.78rem;color:#00174a;margin:0 0 4px 0;">검증된 알고리즘</p>
      <p style="font-size:0.68rem;color:#94a3b8;line-height:1.5;margin:0;">기술적 지표 기반<br>정밀한 진입 신호</p>
    </div>
    <div style="text-align:center;">
      <div style="font-size:1.6rem;margin-bottom:8px;color:#b4c5ff;">⚡</div>
      <p style="font-weight:700;font-size:0.78rem;color:#00174a;margin:0 0 4px 0;">실시간 스캐닝</p>
      <p style="font-size:0.68rem;color:#94a3b8;line-height:1.5;margin:0;">시총 상위 200개<br>전 종목 자동 분석</p>
    </div>
    <div style="text-align:center;">
      <div style="font-size:1.6rem;margin-bottom:8px;color:#b4c5ff;">🛡</div>
      <p style="font-weight:700;font-size:0.78rem;color:#00174a;margin:0 0 4px 0;">리스크 관리</p>
      <p style="font-size:0.68rem;color:#94a3b8;line-height:1.5;margin:0;">손절가·목표가 명확<br>자산 안전하게 보호</p>
    </div>
  </div>
</div>
            """)
    else:
        st.html(f"""
<div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1px solid #86efac;
    border-radius:0.75rem;padding:12px 18px;margin-bottom:16px;
    display:flex;align-items:center;gap:10px;font-family:Inter,sans-serif;">
  <span style="font-size:1.1rem;">✅</span>
  <span style="font-size:0.9rem;font-weight:600;color:#14532d;">
    오늘의 단타 추천 종목 <strong>{len(result_df)}개</strong>를 찾았습니다
  </span>
</div>
        """)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("추천 종목",       f"{len(result_df)}개")
        m2.metric("평균 점수",        f"{result_df['score'].mean():.1f}점")
        m3.metric("평균 RSI",         f"{result_df['rsi'].mean():.1f}")
        m4.metric("평균 거래량 배율", f"{result_df['volume_ratio'].mean():.1f}배")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        for rank, (_, row) in enumerate(result_df.iterrows(), 1):
            _render_card(rank, row, saved_inv)

        with st.expander("전체 데이터 테이블", expanded=True):
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

# ── 종목 상세 차트 탭 ─────────────────────────────────────────
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
