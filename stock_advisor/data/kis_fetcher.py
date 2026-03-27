# ============================================================
# data/kis_fetcher.py - KIS API Fetcher (현재 비활성)
# ============================================================
#
# [활성화 방법]
# 1. config.py에서 DATA_SOURCE = "kis" 설정
# 2. KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 입력
# 3. pip install requests
#
# KIS Developers: https://apiportal.koreainvestment.com
# ============================================================

from __future__ import annotations
import sys
import requests
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

sys.path.append("..")
from config import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, KIS_IS_MOCK
)

# 실계좌 / 모의투자 도메인 분기
KIS_BASE_URL = (
    "https://openapivts.koreainvestment.com:29443"  # 모의투자
    if KIS_IS_MOCK else
    "https://openapi.koreainvestment.com:9443"       # 실계좌
)


class KISFetcher:
    """
    한국투자증권 KIS OpenAPI 기반 주식 데이터 수집기.
    실시간 시세, WebSocket 스트리밍 지원.

    [현재 상태] 비활성 - config.py에서 DATA_SOURCE = "kis" 설정 후 사용
    """

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    # ----------------------------------------------------------
    # 인증
    # ----------------------------------------------------------

    def _get_access_token(self) -> str:
        """Access Token 발급 (유효기간 24시간, 자동 갱신)."""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token

        url = f"{KIS_BASE_URL}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
        }
        res = requests.post(url, json=body, timeout=10)
        res.raise_for_status()
        data = res.json()

        self._access_token = data["access_token"]
        self._token_expires = datetime.now() + timedelta(hours=23)
        return self._access_token

    def _headers(self, tr_id: str) -> dict:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": tr_id,
            "custtype": "P",
        }

    # ----------------------------------------------------------
    # 데이터 수집 (PykrxFetcher와 동일한 인터페이스)
    # ----------------------------------------------------------

    def get_stock_list(self, market: str = "ALL") -> pd.DataFrame:
        """전체 종목 리스트 반환."""
        # KIS API: 업종별 종목 조회 (FHKUP03500100)
        # TODO: 실제 구현 시 KIS 종목 목록 API 연동
        raise NotImplementedError("KIS 종목 목록 API 구현 필요")

    def get_ohlcv(
        self,
        ticker: str,
        days: int = 60,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        KIS API 일봉 OHLCV 데이터.
        TR_ID: FHKST01010100
        """
        if end_date is None:
            end_date = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")

        url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }
        res = requests.get(url, headers=self._headers("FHKST01010100"), params=params, timeout=10)
        res.raise_for_status()

        items = res.json().get("output2", [])
        rows = []
        for item in items:
            rows.append({
                "date": pd.Timestamp(item["stck_bsop_date"]),
                "open":   int(item["stck_oprc"]),
                "high":   int(item["stck_hgpr"]),
                "low":    int(item["stck_lwpr"]),
                "close":  int(item["stck_clpr"]),
                "volume": int(item["acml_vol"]),
            })

        df = pd.DataFrame(rows).set_index("date").sort_index()
        return df

    def get_current_price(self, ticker: str) -> dict:
        """
        KIS 실시간 현재가 조회.
        TR_ID: FHKST01010100
        """
        url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        res = requests.get(url, headers=self._headers("FHKST01010100"), params=params, timeout=10)
        res.raise_for_status()

        output = res.json().get("output", {})
        return {
            "ticker":      ticker,
            "price":       int(output.get("stck_prpr", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0)),
            "volume":      int(output.get("acml_vol", 0)),
        }

    def get_market_cap(self, ticker: str) -> int:
        """시가총액 반환 (억원)."""
        info = self.get_current_price(ticker)
        # 현재가 × 상장주식수로 간이 계산 (KIS API 별도 필드 있음)
        return 0  # TODO: KIS 상장주식수 API 연동
