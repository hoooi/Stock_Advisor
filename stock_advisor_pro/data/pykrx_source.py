# ============================================================
# data/pykrx_source.py
# pykrx + FinanceDataReader 기반 데이터 소스
# get_datasource() factory function으로 접근
# ============================================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pykrx import stock as krx
import FinanceDataReader as fdr

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import OHLCV_YEARS, TOP_N_TICKERS


def get_datasource():
    """factory: 설정된 데이터 소스 반환"""
    return PykrxSource()


class PykrxSource:
    """pykrx + FinanceDataReader 기반 데이터 소스"""

    def get_market_tickers(self, top_n: int = TOP_N_TICKERS) -> list[dict]:
        """
        시가총액 상위 N종목 리스트 반환.
        Returns: [{"ticker": "005930", "name": "삼성전자", "market": "KOSPI"}, ...]
        """
        try:
            kospi  = fdr.StockListing('KOSPI')[['Code', 'Name', 'Marcap']].dropna()
            kosdaq = fdr.StockListing('KOSDAQ')[['Code', 'Name', 'Marcap']].dropna()
            kospi['market']  = 'KOSPI'
            kosdaq['market'] = 'KOSDAQ'
            all_stocks = pd.concat([kospi, kosdaq], ignore_index=True)
            all_stocks = all_stocks.sort_values('Marcap', ascending=False).head(top_n)
            return [
                {"ticker": row.Code, "name": row.Name, "market": row.market}
                for row in all_stocks.itertuples()
            ]
        except Exception as e:
            raise RuntimeError(f"종목 리스트 수집 실패: {e}")

    def get_ohlcv(self, ticker: str, years: int = OHLCV_YEARS) -> pd.DataFrame:
        """
        종목 OHLCV 반환 (지표 계산에 충분한 기간).
        Columns: open, high, low, close, volume
        Index: DatetimeIndex
        """
        end   = datetime.today()
        start = end - timedelta(days=int(years * 365))
        fromdate = start.strftime('%Y%m%d')
        todate   = end.strftime('%Y%m%d')

        try:
            df = krx.get_market_ohlcv(fromdate, todate, ticker)
        except Exception as e:
            raise RuntimeError(f"{ticker} OHLCV 수집 실패: {e}")

        if df is None or len(df) == 0:
            raise ValueError(f"{ticker}: 데이터 없음")

        # pykrx 컬럼명 한글 → 영문 통일
        col_map = {
            '시가': 'open', '고가': 'high', '저가': 'low',
            '종가': 'close', '거래량': 'volume',
        }
        df = df.rename(columns=col_map)

        # 필요 컬럼만
        needed = ['open', 'high', 'low', 'close', 'volume']
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"{ticker}: 컬럼 누락 {missing}, 실제: {list(df.columns)}")

        df = df[needed].copy()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # 숫자형 보장
        for col in needed:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(subset=['close', 'volume'])
        return df
