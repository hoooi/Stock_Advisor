# ============================================================
# test_single.py - 단일 종목 빠른 동작 테스트
# 실행: python test_single.py
# ============================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stock_advisor"))

print("=" * 50)
print("패키지 import 테스트")
print("=" * 50)

# 1. import 테스트
try:
    import pandas as pd
    print(f"✅ pandas {pd.__version__}")
except ImportError:
    print("❌ pandas 없음 → pip install pandas")

try:
    import numpy as np
    print(f"✅ numpy {np.__version__}")
except ImportError:
    print("❌ numpy 없음 → pip install numpy")

try:
    import pykrx
    print(f"✅ pykrx OK")
except ImportError:
    print("❌ pykrx 없음 → pip install pykrx")

try:
    import streamlit
    print(f"✅ streamlit {streamlit.__version__}")
except ImportError:
    print("❌ streamlit 없음 → pip install streamlit")

try:
    import plotly
    print(f"✅ plotly {plotly.__version__}")
except ImportError:
    print("❌ plotly 없음 → pip install plotly")

print()
print("=" * 50)
print("삼성전자(005930) 단일 종목 테스트")
print("=" * 50)

try:
    from data.fetcher import PykrxFetcher
    from analysis.indicators import add_all_indicators, get_latest_signals
    from analysis.price_guide import calculate_price_guide, format_price_guide

    fetcher = PykrxFetcher()

    print("📡 OHLCV 데이터 수집 중...")
    df = fetcher.get_ohlcv("005930", days=60)
    print(f"✅ 데이터 수집 완료: {len(df)}행")
    print(f"   기간: {df.index[0].date()} ~ {df.index[-1].date()}")
    print(f"   최근 종가: {df['close'].iloc[-1]:,}원")

    print("\n📊 지표 계산 중...")
    df = add_all_indicators(df)
    ind = get_latest_signals(df)
    print(f"✅ 지표 계산 완료")
    print(f"   RSI: {ind['rsi']}")
    print(f"   MACD 히스토그램: {ind['macd_hist']}")
    print(f"   거래량 배율: {ind['volume_ratio']}배")
    print(f"   시그널: {ind['signals'] if ind['signals'] else '없음'}")

    print("\n💰 가이드라인 계산 중...")
    guide = calculate_price_guide(df, ind, investment_amount=1_000_000)
    print(f"✅ 가이드라인 계산 완료")
    print(format_price_guide("005930", "삼성전자", guide))

    print("\n✅ 모든 테스트 통과!")

except Exception as e:
    print(f"\n❌ 오류 발생: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
