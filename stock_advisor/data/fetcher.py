# ============================================================
# data/fetcher.py - 주식 데이터 수집 (현재: pykrx)
# ============================================================
#
# [KIS API 전환 방법]
# 1. config.py에서 DATA_SOURCE = "kis" 로 변경
# 2. KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 입력
# 3. 이 파일의 fetch_* 함수들이 자동으로 kis_fetcher.py로 라우팅됨
#
# ============================================================

from __future__ import annotations
import sys
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

sys.path.append("..")
from config import DATA_SOURCE, MARKET


def get_fetcher():
    """
    DATA_SOURCE 설정에 따라 적절한 fetcher 반환.

    [KIS 전환 시] 이 함수가 자동으로 KIS fetcher를 반환합니다.
    별도 코드 수정 없이 config.py의 DATA_SOURCE 값만 바꾸면 됩니다.
    """
    if DATA_SOURCE == "kis":
        # [KIS 전환 시 활성화] kis_fetcher.py 사용
        from data.kis_fetcher import KISFetcher
        return KISFetcher()
    else:
        return PykrxFetcher()


# ============================================================
# pykrx 기반 Fetcher (현재 사용)
# ============================================================

class PykrxFetcher:
    """
    pykrx를 사용한 주식 데이터 수집기.
    데이터는 15분~1일 지연이 있으므로 장 시작 전 분석용으로 사용.

    [KIS 전환 시] 이 클래스 대신 KISFetcher가 사용됩니다.
    """

    def get_stock_list(self, market: str = MARKET) -> pd.DataFrame:
        """
        전체 종목 리스트 반환.
        pykrx의 종목목록 API가 불안정하므로 FinanceDataReader 사용.

        Returns:
            DataFrame: columns=[ticker, name, market]

        [KIS 전환 시] KIS API: GET /uapi/domestic-stock/v1/quotations/search-stock-info
        """
        import FinanceDataReader as fdr

        frames = []
        if market in ("KOSPI", "ALL"):
            df = fdr.StockListing("KOSPI")[["Code", "Name"]].copy()
            df.columns = ["ticker", "name"]
            df["market"] = "KOSPI"
            frames.append(df)

        if market in ("KOSDAQ", "ALL"):
            df = fdr.StockListing("KOSDAQ")[["Code", "Name"]].copy()
            df.columns = ["ticker", "name"]
            df["market"] = "KOSDAQ"
            frames.append(df)

        result = pd.concat(frames, ignore_index=True)
        result["ticker"] = result["ticker"].astype(str).str.zfill(6)
        return result

    def get_ohlcv(
        self,
        ticker: str,
        days: int = 60,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        OHLCV 일봉 데이터 반환.

        Args:
            ticker: 종목코드 (예: "005930")
            days: 조회 기간 (일수)
            end_date: 종료일 (YYYYMMDD, None이면 오늘)

        Returns:
            DataFrame: columns=[open, high, low, close, volume]

        [KIS 전환 시] KIS API: GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
                     실시간 데이터 + WebSocket 구독 가능
        """
        from pykrx import stock

        if end_date is None:
            end_date = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")

        df = stock.get_market_ohlcv(start_date, end_date, ticker)
        if df.empty:
            return df

        # pykrx 버전에 따라 컬럼 수가 6개 또는 7개로 다를 수 있음 → 위치 기반으로 안전하게 처리
        col_map = {
            df.columns[0]: "open",
            df.columns[1]: "high",
            df.columns[2]: "low",
            df.columns[3]: "close",
            df.columns[4]: "volume",
        }
        df = df.rename(columns=col_map)
        df.index.name = "date"
        return df[["open", "high", "low", "close", "volume"]]

    def get_current_price(self, ticker: str) -> dict:
        """
        현재가 정보 반환 (pykrx는 당일 종가 기준).

        Returns:
            dict: {ticker, price, change_rate, volume}

        [KIS 전환 시] KIS API: GET /uapi/domestic-stock/v1/quotations/inquire-price
                     초 단위 실시간 현재가 제공
        """
        from pykrx import stock

        today = datetime.today().strftime("%Y%m%d")
        df = stock.get_market_ohlcv(today, today, ticker)

        if df.empty:
            yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv(yesterday, yesterday, ticker)

        if df.empty:
            return {"ticker": ticker, "price": 0, "change_rate": 0.0, "volume": 0}

        row = df.iloc[-1]
        try:
            change_rate = float(row.iloc[6]) if len(row) > 6 else 0.0
            if change_rate != change_rate:   # NaN 체크
                change_rate = 0.0
        except (ValueError, TypeError):
            change_rate = 0.0

        return {
            "ticker": ticker,
            "price": int(row.iloc[3]),       # close
            "change_rate": change_rate,
            "volume": int(row.iloc[4]),       # volume
        }

    def get_market_cap(self, ticker: str) -> int:
        """
        시가총액 반환 (억원).

        [KIS 전환 시] KIS API: GET /uapi/domestic-stock/v1/quotations/inquire-price
                     시총 필드 포함
        """
        from pykrx import stock

        today = datetime.today().strftime("%Y%m%d")
        df = stock.get_market_cap(today, today, ticker)

        if df.empty:
            return 0
        return int(df.iloc[-1]["시가총액"] / 1e8)  # 원 → 억원


def _get_last_business_day() -> str:
    """
    가장 최근 영업일 반환 (YYYYMMDD).
    pykrx의 자동 날짜 감지가 KRX 서버 응답 오류로 실패할 때 대체용.
    토요일 → 금요일, 일요일 → 금요일, 평일 → 당일 반환.
    """
    today = datetime.today()
    weekday = today.weekday()  # 월=0 ... 금=4, 토=5, 일=6
    if weekday == 5:           # 토요일
        today -= timedelta(days=1)
    elif weekday == 6:         # 일요일
        today -= timedelta(days=2)
    return today.strftime("%Y%m%d")
