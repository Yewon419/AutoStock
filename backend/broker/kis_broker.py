"""
KIS (한국투자증권) REST API 브로커
- OAuth access_token 발급/갱신 (Redis 캐시)
- 주식 매수/매도 주문 (REST)
- 모의투자/실계좌 URL 자동 전환
"""
import json
import logging
import time
from datetime import datetime, timezone

import redis
import requests

from broker.base import BaseBroker, OrderResult
from core.config import settings

logger = logging.getLogger(__name__)

# KIS API 엔드포인트
_PAPER_BASE = "https://openapivts.koreainvestment.com:29443"
_REAL_BASE  = "https://openapi.koreainvestment.com:9443"

_TOKEN_REDIS_KEY = "kis:access_token"


class KisBroker(BaseBroker):
    """KIS REST API를 통해 주문을 처리하는 브로커"""

    def __init__(self):
        self._is_paper: bool = settings.KIS_IS_PAPER
        self._base_url: str = _PAPER_BASE if self._is_paper else _REAL_BASE
        self._app_key: str = settings.KIS_APP_KEY
        self._app_secret: str = settings.KIS_APP_SECRET
        self._account_no: str = settings.KIS_ACCOUNT_NO  # "12345678-01"
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    # ------------------------------------------------------------------
    # Token
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Redis 캐시에서 access_token 반환. 만료 임박 시 재발급."""
        cached = self._redis.get(_TOKEN_REDIS_KEY)
        if cached:
            return cached

        url = f"{self._base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        # 만료 10분 전에 갱신하도록 TTL 설정
        ttl = max(expires_in - 600, 60)
        self._redis.setex(_TOKEN_REDIS_KEY, ttl, token)
        logger.info("[KisBroker] access_token 발급 완료 (TTL=%ds)", ttl)
        return token

    def _headers(self, tr_id: str) -> dict:
        acct_parts = self._account_no.split("-")
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def get_available_cash(self) -> float:
        """KIS 실계좌 주문가능현금 조회"""
        tr_id = "VTTC8908R" if self._is_paper else "TTTC8908R"
        acct_no, acct_prod = self._account_no.split("-")
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
        params = {
            "CANO": acct_no, "ACNT_PRDT_CD": acct_prod,
            "PDNO": "005930", "ORD_UNPR": "0", "ORD_DVSN": "01",
            "CMA_EVLU_AMT_ICLD_YN": "N", "OVRS_ICLD_YN": "N",
        }
        resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(f"잔고 조회 실패: {data.get('msg1')}")
        return float(data.get("output", {}).get("ord_psbl_cash", 0))

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """시장가 매수 주문 (ord_dvsn=01)"""
        # 모의: VTTC0802U / 실계좌: TTTC0802U
        tr_id = "VTTC0802U" if self._is_paper else "TTTC0802U"
        acct_no, acct_prod = self._account_no.split("-")

        body = {
            "CANO": acct_no,
            "ACNT_PRDT_CD": acct_prod,
            "PDNO": ticker,
            "ORD_DVSN": "01",         # 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": "0",
        }
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/order-cash"
        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS BUY 오류: {data.get('msg1')}")

        order_no = data.get("output", {}).get("ODNO", "")
        filled = price if price else float(data.get("output", {}).get("EXEC_PRC", price))
        logger.info("[KisBroker] BUY bot=%d %s %d주 @%.0f order=%s", bot_id, ticker, quantity, filled, order_no)
        return OrderResult(filled_price=filled, order_number=order_no)

    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """시장가 매도 주문 (ord_dvsn=01)"""
        # 모의: VTTC0801U / 실계좌: TTTC0801U
        tr_id = "VTTC0801U" if self._is_paper else "TTTC0801U"
        acct_no, acct_prod = self._account_no.split("-")

        body = {
            "CANO": acct_no,
            "ACNT_PRDT_CD": acct_prod,
            "PDNO": ticker,
            "ORD_DVSN": "01",         # 시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": "0",
        }
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/order-cash"
        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS SELL 오류: {data.get('msg1')}")

        order_no = data.get("output", {}).get("ODNO", "")
        filled = price if price else float(data.get("output", {}).get("EXEC_PRC", price))
        logger.info("[KisBroker] SELL bot=%d %s %d주 @%.0f order=%s", bot_id, ticker, quantity, filled, order_no)
        return OrderResult(filled_price=filled, order_number=order_no)

    # ------------------------------------------------------------------
    # Intraday (minute candles)
    # ------------------------------------------------------------------

    def get_minute_candles(self, ticker: str, interval: int = 1) -> list[dict]:
        """KIS 분봉 시세 조회 (TR: FHKST03010200)
        반환: [{"t": "HH:MM", "o": float, "h": float, "l": float, "c": float, "v": int}, ...]
        최신순 정렬 (index 0이 가장 최근)
        """
        now_str = datetime.now(timezone.utc).strftime("%H%M%S")
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_HOUR_1": now_str,
            "FID_PW_DATA_INCU_YN": "Y",
        }
        url = f"{self._base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = self._headers("FHKST03010200")
        headers["tr_id"] = "FHKST03010200"

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            logger.warning("[KisBroker] 분봉 조회 오류: %s", data.get("msg1"))
            return []

        candles = []
        for item in data.get("output2", []):
            try:
                t_raw = item.get("stck_bsop_hour", "")  # "HHMMSS"
                t_str = f"{t_raw[:2]}:{t_raw[2:4]}" if len(t_raw) >= 4 else t_raw
                candles.append({
                    "t": t_str,
                    "o": float(item.get("stck_oprc", 0)),
                    "h": float(item.get("stck_hgpr", 0)),
                    "l": float(item.get("stck_lwpr", 0)),
                    "c": float(item.get("stck_prpr", 0)),
                    "v": int(item.get("cntg_vol", 0)),
                })
            except (ValueError, KeyError):
                continue

        logger.debug("[KisBroker] 분봉 수집 %s interval=%d count=%d", ticker, interval, len(candles))
        return candles
