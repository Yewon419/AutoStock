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

from broker.base import (
    BaseBroker, OrderResult, FillResult,
    FILL_FILLED, FILL_PARTIAL, FILL_PENDING, FILL_REJECTED, FILL_CANCELLED, FILL_UNKNOWN,
)
from core.config import settings

logger = logging.getLogger(__name__)

# KIS API 엔드포인트
_PAPER_BASE = "https://openapivts.koreainvestment.com:29443"
_REAL_BASE  = "https://openapi.koreainvestment.com:9443"

_TOKEN_REDIS_KEY_FMT = "kis:access_token:{mode}"  # paper/real 토큰 분리 캐시
_ERROR_COUNT_KEY_FMT = "autostock:kis_error_count:{minute_bucket}"  # mechanism_audit E3
_ERROR_COUNT_TTL = 300  # 5분 (5분 주기 감사가 1번은 읽을 수 있도록)


class KisBroker(BaseBroker):
    """KIS REST API를 통해 주문을 처리하는 브로커

    is_paper는 생성자에서 주입. 전역 settings.KIS_IS_PAPER는 더 이상 사용하지 않음.
    같은 사이클 내 bot.mode='paper' 봇과 'real' 봇이 서로 다른 KisBroker를 쓸 수 있도록 보장.
    """

    def __init__(self, is_paper: bool):
        self._is_paper: bool = is_paper
        self._base_url: str = _PAPER_BASE if self._is_paper else _REAL_BASE
        self._token_key: str = _TOKEN_REDIS_KEY_FMT.format(mode="paper" if is_paper else "real")
        self._app_key: str = settings.KIS_APP_KEY
        self._app_secret: str = settings.KIS_APP_SECRET
        self._account_no: str = settings.KIS_ACCOUNT_NO  # "12345678-01"
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    # ------------------------------------------------------------------
    # Token
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Redis 캐시에서 access_token 반환. 만료 임박 시 재발급."""
        cached = self._redis.get(self._token_key)
        if cached:
            return cached

        url = f"{self._base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._app_key,
            "appsecret": self._app_secret,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"KIS 토큰 발급 네트워크 오류: {e}") from e

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"KIS 토큰 발급 실패: {data.get('msg1', data)}")
        expires_in = int(data.get("expires_in", 86400))
        # 만료 10분 전에 갱신하도록 TTL 설정
        ttl = max(expires_in - 600, 60)
        self._redis.setex(self._token_key, ttl, token)
        logger.info("[KisBroker] access_token 발급 완료 mode=%s TTL=%ds", "paper" if self._is_paper else "real", ttl)
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

    def _bump_error_counter(self) -> None:
        """매커니즘 감사(E3)용: 분 단위 에러 카운터 INCR. 본 흐름에 영향 없도록 swallow."""
        try:
            bucket = int(time.time()) // 60
            key = _ERROR_COUNT_KEY_FMT.format(minute_bucket=bucket)
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, _ERROR_COUNT_TTL)
            pipe.execute()
        except Exception as e:
            logger.warning("[KisBroker] error_count INCR 실패: %r", e)

    def _place_order(self, side: str, bot_id: int, ticker: str, quantity: int, price: float) -> OrderResult:
        """매수/매도 공통. 주문 접수만 하고 ODNO 반환. 실체결가는 check_order_fill로 별도 조회."""
        # 모의: VTTC080{1,2}U / 실계좌: TTTC080{1,2}U
        tr_suffix = "0802U" if side == "BUY" else "0801U"
        tr_id = f"{'V' if self._is_paper else 'T'}TTC{tr_suffix}"
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
        try:
            resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            self._bump_error_counter()
            raise

        if data.get("rt_cd") != "0":
            self._bump_error_counter()
            raise RuntimeError(
                f"KIS {side} 거부: ticker={ticker} qty={quantity} "
                f"msg={data.get('msg1')} rt_cd={data.get('rt_cd')} body={body}"
            )

        order_no = data.get("output", {}).get("ODNO", "")
        if not order_no:
            self._bump_error_counter()
            raise RuntimeError(f"KIS {side} 접수됐으나 ODNO 누락: {data}")
        logger.info(
            "[KisBroker] %s 접수 bot=%d %s %d주 order=%s (mode=%s)",
            side, bot_id, ticker, quantity, order_no, "paper" if self._is_paper else "real",
        )
        # filled_price에는 호가(참고값) 넣지만 실체결가 아님 — immediate_fill=None이므로 폴링 필요
        return OrderResult(filled_price=price, order_number=order_no, success=True, immediate_fill=None)

    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return self._place_order("BUY", bot_id, ticker, quantity, price)

    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return self._place_order("SELL", bot_id, ticker, quantity, price)

    def check_order_fill(self, order_number: str, ticker: str) -> FillResult:
        """ODNO로 금일 체결내역 조회. TR: TTTC8001R(실) / VTTC8001R(모의).

        inquire-daily-ccld 엔드포인트는 오늘 주문 전체를 페이지네이션으로 반환.
        조회 비용 절감을 위해 INQR_STRT_ODNO에 대상 ODNO를 넣어 해당 주문부터 시작.
        """
        tr_id = "VTTC8001R" if self._is_paper else "TTTC8001R"
        acct_no, acct_prod = self._account_no.split("-")
        today = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
        params = {
            "CANO": acct_no,
            "ACNT_PRDT_CD": acct_prod,
            "INQR_STRT_DT": today,
            "INQR_END_DT": today,
            "SLL_BUY_DVSN_CD": "00",   # 00: 전체
            "INQR_DVSN": "00",          # 00: 역순
            "PDNO": ticker,
            "CCLD_DVSN": "00",          # 00: 전체 (체결+미체결)
            "ORD_GNO_BRNO": "",
            "ODNO": order_number,
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        try:
            resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("[KisBroker] 체결조회 네트워크 오류 order=%s: %s", order_number, e)
            return FillResult(status=FILL_UNKNOWN, filled_quantity=0, avg_price=0.0)

        if data.get("rt_cd") != "0":
            logger.warning("[KisBroker] 체결조회 실패 order=%s msg=%s", order_number, data.get("msg1"))
            return FillResult(status=FILL_UNKNOWN, filled_quantity=0, avg_price=0.0)

        # output1은 주문 단위 리스트. ODNO 일치 항목 필터.
        rows = [r for r in data.get("output1", []) if r.get("odno") == order_number]
        if not rows:
            # KIS가 아직 주문 기록을 인덱싱하지 않았거나 ODNO 불일치.
            return FillResult(status=FILL_PENDING, filled_quantity=0, avg_price=0.0)

        row = rows[0]
        ord_qty = int(row.get("ord_qty", 0) or 0)
        ccld_qty = int(row.get("tot_ccld_qty", 0) or 0)
        cncl_yn = row.get("cncl_yn", "N")
        rjct_qty = int(row.get("rjct_qty", 0) or 0)
        avg_prvs = row.get("avg_prvs", "0") or "0"  # 평균체결가
        # KIS는 avg_prvs가 문자열. 0이면 미체결
        try:
            avg_price = float(avg_prvs)
        except ValueError:
            avg_price = 0.0

        # 상태 결정
        if cncl_yn == "Y":
            status = FILL_CANCELLED
        elif rjct_qty > 0 and ccld_qty == 0:
            status = FILL_REJECTED
        elif ccld_qty >= ord_qty and ord_qty > 0:
            status = FILL_FILLED
        elif 0 < ccld_qty < ord_qty:
            status = FILL_PARTIAL
        else:
            status = FILL_PENDING

        return FillResult(status=status, filled_quantity=ccld_qty, avg_price=avg_price)

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
