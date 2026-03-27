# ============================================================
# data/kis_source.py — KIS API stub
# TODO: KIS OpenAPI 연동 시 이 파일 구현
# 참고: https://apiportal.koreainvestment.com/
# ============================================================


class KisSource:
    """KIS(한국투자증권) API 데이터 소스 — 미구현 stub"""

    def get_market_tickers(self, top_n: int):
        # TODO: KIS /uapi/domestic-stock/v1/quotations/inquire-daily-price
        raise NotImplementedError("KIS API 미구현 — data/kis_source.py 참조")

    def get_ohlcv(self, ticker: str, years: int):
        # TODO: KIS /uapi/domestic-stock/v1/quotations/inquire-daily-price
        raise NotImplementedError("KIS API 미구현 — data/kis_source.py 참조")
