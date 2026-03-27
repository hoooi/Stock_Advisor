# ============================================================
# charts/tradingview.py — TradingView 스타일 캔들차트
# render_chart(df, mode) — 단일 진입점
# ============================================================

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from analysis.indicators import _ema, _sma, calc_bollinger


# ── 색상 팔레트 (TradingView 다크 테마) ──────────────────────

_UP_COLOR   = "#26a69a"   # 상승 캔들 (teal)
_DOWN_COLOR = "#ef5350"   # 하락 캔들 (red)
_BG_COLOR   = "#131722"
_GRID_COLOR = "#1e2433"
_TEXT_COLOR = "#d1d4dc"
_VOLUME_UP  = "rgba(38,166,154,0.4)"
_VOLUME_DN  = "rgba(239,83,80,0.4)"


# ── 오버레이 지표 (모드별) ────────────────────────────────────

def _add_short_term_overlays(fig: go.Figure, df: pd.DataFrame):
    """단기: EMA20, Bollinger Bands"""
    close = df["close"]

    ema20 = _ema(close, 20)
    fig.add_trace(go.Scatter(
        x=df.index, y=ema20,
        name="EMA20", line=dict(color="#f48fb1", width=1),
        hovertemplate="EMA20: %{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    upper, middle, lower, _ = calc_bollinger(close)
    bb_upper = close.rolling(20).mean() + 2 * close.rolling(20).std()
    bb_lower = close.rolling(20).mean() - 2 * close.rolling(20).std()
    bb_mid   = close.rolling(20).mean()

    fig.add_trace(go.Scatter(
        x=df.index, y=bb_upper,
        name="BB상단", line=dict(color="rgba(100,160,255,0.6)", width=1, dash="dot"),
        hovertemplate="BB상단: %{y:,.0f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=bb_lower,
        name="BB하단", line=dict(color="rgba(100,160,255,0.6)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(100,160,255,0.05)",
        hovertemplate="BB하단: %{y:,.0f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=bb_mid,
        name="BB중심", line=dict(color="rgba(100,160,255,0.3)", width=1),
        hovertemplate="BB중심: %{y:,.0f}<extra></extra>",
    ), row=1, col=1)


def _add_swing_overlays(fig: go.Figure, df: pd.DataFrame):
    """스윙: EMA20, EMA50"""
    close = df["close"]
    for period, color, name in [(20, "#f48fb1", "EMA20"), (50, "#ffb74d", "EMA50")]:
        fig.add_trace(go.Scatter(
            x=df.index, y=_ema(close, period),
            name=name, line=dict(color=color, width=1.5),
            hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>",
        ), row=1, col=1)


def _add_long_term_overlays(fig: go.Figure, df: pd.DataFrame):
    """장기: MA50, MA200"""
    close = df["close"]
    for period, color, name in [(50, "#ffb74d", "MA50"), (200, "#ce93d8", "MA200")]:
        fig.add_trace(go.Scatter(
            x=df.index, y=_sma(close, period),
            name=name, line=dict(color=color, width=1.5),
            hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>",
        ), row=1, col=1)


# ── 하단 지표 패널 (RSI / MACD) ───────────────────────────────

def _add_rsi_panel(fig: go.Figure, df: pd.DataFrame, row: int):
    close = df["close"]
    delta     = close.diff()
    gain      = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss      = (-delta).clip(lower=0).ewm(com=13, adjust=False).mean()
    rs        = gain / loss.replace(0, float("nan"))
    rsi       = 100 - 100 / (1 + rs)

    fig.add_trace(go.Scatter(
        x=df.index, y=rsi, name="RSI(14)",
        line=dict(color="#7e57c2", width=1.5),
        hovertemplate="RSI: %{y:.1f}<extra></extra>",
    ), row=row, col=1)

    # 기준선
    for level, color in [(30, "rgba(239,83,80,0.4)"), (70, "rgba(38,166,154,0.4)")]:
        fig.add_hline(y=level, line_width=1, line_dash="dot", line_color=color, row=row, col=1)


def _add_macd_panel(fig: go.Figure, df: pd.DataFrame, row: int):
    close      = df["close"]
    ema_fast   = close.ewm(span=12, adjust=False).mean()
    ema_slow   = close.ewm(span=26, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal     = macd_line.ewm(span=9, adjust=False).mean()
    histogram  = macd_line - signal

    colors = [_UP_COLOR if v >= 0 else _DOWN_COLOR for v in histogram]

    fig.add_trace(go.Bar(
        x=df.index, y=histogram, name="MACD Hist",
        marker_color=colors,
        hovertemplate="MACD Hist: %{y:.2f}<extra></extra>",
    ), row=row, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=macd_line, name="MACD",
        line=dict(color="#29b6f6", width=1.2),
        hovertemplate="MACD: %{y:.2f}<extra></extra>",
    ), row=row, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=signal, name="Signal",
        line=dict(color="#ff7043", width=1.2),
        hovertemplate="Signal: %{y:.2f}<extra></extra>",
    ), row=row, col=1)


# ── 메인 진입점 ───────────────────────────────────────────────

def render_chart(df: pd.DataFrame, mode: str, ticker: str = "", name: str = "") -> go.Figure:
    """
    TradingView 스타일 캔들차트 + 거래량 + 모드별 지표.

    Parameters
    ----------
    df     : OHLCV DataFrame (index=DatetimeIndex)
    mode   : "단기" | "스윙" | "장기"
    ticker : 종목코드 (제목용)
    name   : 종목명 (제목용)

    Returns
    -------
    plotly.graph_objects.Figure
    """
    # 패널 구성: 캔들(6) + 거래량(2) + 하단지표(2)
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        vertical_spacing=0.02,
        subplot_titles=("", "거래량", "RSI(14)" if mode == "단기" else "MACD"),
    )

    # ── 캔들스틱 ─────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="가격",
        increasing=dict(line=dict(color=_UP_COLOR), fillcolor=_UP_COLOR),
        decreasing=dict(line=dict(color=_DOWN_COLOR), fillcolor=_DOWN_COLOR),
        hovertext=[
            f"시가: {o:,.0f}<br>고가: {h:,.0f}<br>저가: {l:,.0f}<br>종가: {c:,.0f}"
            for o, h, l, c in zip(df["open"], df["high"], df["low"], df["close"])
        ],
        hoverinfo="text+x",
    ), row=1, col=1)

    # ── 모드별 오버레이 ───────────────────────────────────────
    if mode == "단기":
        _add_short_term_overlays(fig, df)
    elif mode == "스윙":
        _add_swing_overlays(fig, df)
    else:  # 장기
        _add_long_term_overlays(fig, df)

    # ── 거래량 ────────────────────────────────────────────────
    vol_colors = [
        _VOLUME_UP if df["close"].iloc[i] >= df["open"].iloc[i] else _VOLUME_DN
        for i in range(len(df))
    ]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        name="거래량",
        marker_color=vol_colors,
        hovertemplate="거래량: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ── 하단 지표 ─────────────────────────────────────────────
    if mode == "단기":
        _add_rsi_panel(fig, df, row=3)
    else:
        _add_macd_panel(fig, df, row=3)

    # ── 레이아웃 ──────────────────────────────────────────────
    title_text = f"{name} ({ticker})" if name else ticker

    fig.update_layout(
        title=dict(text=title_text, font=dict(color=_TEXT_COLOR, size=16)),
        paper_bgcolor=_BG_COLOR,
        plot_bgcolor=_BG_COLOR,
        font=dict(color=_TEXT_COLOR),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        margin=dict(l=10, r=10, t=60, b=10),
        height=700,
    )

    # 그리드 스타일 통일
    for axis in ["xaxis", "xaxis2", "xaxis3", "yaxis", "yaxis2", "yaxis3"]:
        fig.update_layout(**{axis: dict(
            gridcolor=_GRID_COLOR,
            zerolinecolor=_GRID_COLOR,
            showgrid=True,
        )})

    # 주말 갭 제거 (한국 주식 거래일만 표시)
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),  # 주말 제거
        ]
    )

    return fig
