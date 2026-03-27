# ============================================================
# main.py - CLI 진입점
# 사용법:
#   python main.py               → 대화형 종목 분석
#   python main.py --top 5       → 상위 5개 종목 출력
#   python main.py --invest 500000 → 50만원 기준 가이드라인
#   streamlit run ui/dashboard.py → 웹 대시보드
# ============================================================

from __future__ import annotations
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import TOP_N_STOCKS
from analysis.screener import run_screening
from analysis.price_guide import format_price_guide

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="단타 어드바이저")
    parser.add_argument("--top",     type=int, default=TOP_N_STOCKS, help="추천 종목 수")
    parser.add_argument("--invest",  type=int, default=1_000_000,    help="투자금 (원)")
    parser.add_argument("--verbose", action="store_true",            help="상세 로그 출력")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print(" 단타 주식 어드바이저")
    print("=" * 60)
    print(f"투자금: {args.invest:,}원 | 상위 {args.top}개 종목")
    print("전체 종목 분석 중... (수분 소요)\n")

    def progress(current, total, name):
        pct = int(current / total * 20)
        bar = "█" * pct + "░" * (20 - pct)
        print(f"\r[{bar}] {current}/{total} {name}          ", end="", flush=True)

    result_df = run_screening(
        investment_amount=args.invest,
        top_n=args.top,
        progress_callback=progress,
    )
    print()

    if result_df.empty:
        print("\n⚠️  조건에 맞는 종목이 없습니다.")
        print("    → MIN_VOLUME_SURGE, RSI_OVERSOLD 등 config.py 조건을 완화해보세요.")
        return

    print(f"\n✅ 오늘의 단타 추천 종목 TOP {len(result_df)}")
    print("=" * 60)

    for rank, (_, row) in enumerate(result_df.iterrows(), 1):
        print(f"\n[{rank}위] 점수: {row['score']:.0f}점")
        # format_price_guide가 기대하는 키 이름으로 매핑
        guide = {
            "entry_low":        row["entry_low"],
            "entry_high":       row["entry_high"],
            "stop_loss":        row["stop_loss"],
            "loss_pct":         row["loss_pct"],
            "target1":          row["target1"],
            "target1_pct":      row["target1_pct"],
            "target2":          row["target2"],
            "target2_pct":      row["target2_pct"],
            "risk_reward1":     row["risk_reward"],   # screener는 'risk_reward'로 저장
            "rr_ok":            row["risk_reward"] >= 1.5,
            "investment":       args.invest,
            "qty_first":        row["qty_first"],
            "qty_second":       row["qty_second"],
            "expected_profit1": row["expected_profit1"],
            "expected_loss":    row["expected_loss"],
        }
        print(format_price_guide(ticker=row["ticker"], name=row["name"], guide=guide))
        print(f"  시그널: {row.get('signals', '')}")

    print("\n" + "=" * 60)
    print("⚠️  본 프로그램은 기술적 지표 기반 참고 자료입니다.")
    print("   투자 손실에 대한 책임은 본인에게 있습니다.")
    print("=" * 60)

    print("\n💡 웹 대시보드 실행: streamlit run ui/dashboard.py")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
