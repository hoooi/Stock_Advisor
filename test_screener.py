# ============================================================
# test_screener.py - 단타 추천 종목 빠른 테스트
# 전체 종목 대신 인기 종목 50개만 스캔 (약 30초 소요)
# 실행: python test_screener.py
# ============================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stock_advisor"))

from data.fetcher import PykrxFetcher
from analysis.indicators import add_all_indicators, get_latest_signals
from analysis.price_guide import calculate_price_guide, format_price_guide
from analysis.screener import _analyze_single, _calculate_score

# 테스트용 인기 종목 50개 (유동성 높은 종목 위주)
WATCHLIST = [
    ("005930", "삼성전자",    "KOSPI"),
    ("000660", "SK하이닉스",  "KOSPI"),
    ("005380", "현대차",      "KOSPI"),
    ("035420", "NAVER",       "KOSPI"),
    ("051910", "LG화학",      "KOSPI"),
    ("006400", "삼성SDI",     "KOSPI"),
    ("035720", "카카오",      "KOSPI"),
    ("068270", "셀트리온",    "KOSPI"),
    ("105560", "KB금융",      "KOSPI"),
    ("055550", "신한지주",    "KOSPI"),
    ("003550", "LG",          "KOSPI"),
    ("012330", "현대모비스",  "KOSPI"),
    ("028260", "삼성물산",    "KOSPI"),
    ("066570", "LG전자",      "KOSPI"),
    ("032830", "삼성생명",    "KOSPI"),
    ("017670", "SK텔레콤",    "KOSPI"),
    ("030200", "KT",          "KOSPI"),
    ("086790", "하나금융지주","KOSPI"),
    ("316140", "우리금융지주","KOSPI"),
    ("034730", "SK",          "KOSPI"),
    ("018260", "삼성에스디에스","KOSPI"),
    ("009150", "삼성전기",    "KOSPI"),
    ("000270", "기아",        "KOSPI"),
    ("011200", "HMM",         "KOSPI"),
    ("047050", "포스코인터내셔널","KOSPI"),
    ("096770", "SK이노베이션","KOSPI"),
    ("011170", "롯데케미칼",  "KOSPI"),
    ("010130", "고려아연",    "KOSPI"),
    ("042660", "한화오션",    "KOSPI"),
    ("009830", "한화솔루션",  "KOSPI"),
    # KOSDAQ
    ("247540", "에코프로비엠","KOSDAQ"),
    ("086520", "에코프로",    "KOSDAQ"),
    ("373220", "LG에너지솔루션","KOSPI"),
    ("196170", "알테오젠",    "KOSDAQ"),
    ("091990", "셀트리온헬스케어","KOSDAQ"),
    ("067160", "에이티젠",    "KOSDAQ"),
    ("112040", "위메이드",    "KOSDAQ"),
    ("293490", "카카오게임즈","KOSDAQ"),
    ("263750", "펄어비스",    "KOSDAQ"),
    ("035900", "JYP Ent.",    "KOSDAQ"),
    ("041510", "에스엠",      "KOSDAQ"),
    ("122870", "YG PLUS",     "KOSDAQ"),
    ("214150", "클래시스",    "KOSDAQ"),
    ("145020", "휴젤",        "KOSDAQ"),
    ("216080", "제테마",      "KOSDAQ"),
    ("240810", "원익IPS",     "KOSDAQ"),
    ("357780", "솔브레인",    "KOSDAQ"),
    ("046890", "서울반도체",  "KOSDAQ"),
    ("095340", "ISC",         "KOSDAQ"),
    ("058470", "리노공업",    "KOSDAQ"),
]

print("=" * 60)
print("📈 단타 추천 종목 스캐너 (인기 종목 50개)")
print("=" * 60)
print(f"총 {len(WATCHLIST)}개 종목 분석 중...\n")

results = []

for i, (ticker, name, market) in enumerate(WATCHLIST, 1):
    pct = int(i / len(WATCHLIST) * 30)
    bar = "█" * pct + "░" * (30 - pct)
    print(f"\r[{bar}] {i}/{len(WATCHLIST)} {name}          ", end="", flush=True)

    try:
        result = _analyze_single(ticker, name, market, investment_amount=1_000_000)
        if result:
            results.append(result)
    except Exception as e:
        pass

print(f"\n\n분석 완료: {len(WATCHLIST)}개 스캔 → {len(results)}개 후보 발견\n")

if not results:
    print("⚠️  조건에 맞는 단타 추천 종목이 없습니다.")
    print("   (현재 시장 상황에서 조건을 만족하는 종목 없음)")
    print("\n💡 조건 완화 방법: stock_advisor/config.py 에서")
    print("   MIN_VOLUME_SURGE = 1.5  (거래량 조건 낮추기)")
    print("   RSI_OVERSOLD = 50       (RSI 조건 완화)")
else:
    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"✅ 오늘의 단타 추천 종목 TOP {len(results)}")
    print("=" * 60)

    for rank, r in enumerate(results, 1):
        guide = {
            "entry_low":        r["entry_low"],
            "entry_high":       r["entry_high"],
            "stop_loss":        r["stop_loss"],
            "loss_pct":         r["loss_pct"],
            "target1":          r["target1"],
            "target1_pct":      r["target1_pct"],
            "target2":          r["target2"],
            "target2_pct":      r["target2_pct"],
            "risk_reward1":     r["risk_reward"],
            "rr_ok":            r["risk_reward"] >= 1.5,
            "investment":       1_000_000,
            "qty_first":        r["qty_first"],
            "qty_second":       r["qty_second"],
            "expected_profit1": r["expected_profit1"],
            "expected_loss":    r["expected_loss"],
        }
        print(f"\n[{rank}위] 점수: {r['score']:.0f}점")
        print(format_price_guide(r["ticker"], r["name"], guide))
        print(f"  시그널: {r['signals']}")

print("\n" + "=" * 60)
print("💡 전체 종목 스캔: cd stock_advisor && python main.py")
print("💡 웹 대시보드:    cd stock_advisor && streamlit run ui/dashboard.py")
print("=" * 60)
