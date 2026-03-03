"""
KIS WebSocket 실시간 시세 스트림
- 장 시작 전(08:55) Celery beat에 의해 start_price_stream 태스크 실행
- RUNNING 봇의 tickers를 수집 → KIS WebSocket 구독
- 수신된 현재가를 Redis rt:price:{ticker} (TTL 60초) 에 저장
- WebSocket 모의: ws://ops.koreainvestment.com:31000
- WebSocket 실계좌: ws://ops.koreainvestment.com:21000
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import redis as redis_sync
import websockets

from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_PAPER_WS = "ws://ops.koreainvestment.com:31000"
_REAL_WS  = "ws://ops.koreainvestment.com:21000"

_RT_PRICE_TTL = 60          # Redis TTL (초)
_STREAM_DURATION = 7 * 3600  # 최대 7시간 유지 (08:55 ~ 15:55)


def _get_running_tickers() -> list[str]:
    """RUNNING 상태 봇의 tickers 전체 수집 (중복 제거)"""
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(TradingBot.status == 'RUNNING').all()
        tickers = set()
        for bot in bots:
            for t in (bot.tickers or []):
                tickers.add(t)
        return list(tickers)
    finally:
        db.close()


def _get_approval_key() -> str:
    """KIS WebSocket 접속키 발급"""
    import requests
    is_paper = settings.KIS_IS_PAPER
    base = "https://openapivts.koreainvestment.com:29443" if is_paper else "https://openapi.koreainvestment.com:9443"
    url = f"{base}/oauth2/Approval"
    payload = {
        "grant_type": "client_credentials",
        "appkey": settings.KIS_APP_KEY,
        "secretkey": settings.KIS_APP_SECRET,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["approval_key"]


def _parse_price(data: str) -> tuple[str, float] | None:
    """
    KIS 실시간 시세 메시지 파싱.
    응답 형식: "0|H0STCNT0|001|{ticker}^{time}^{price}^..."
    """
    try:
        parts = data.split("|")
        if len(parts) < 4:
            return None
        if parts[1] != "H0STCNT0":
            return None
        fields = parts[3].split("^")
        ticker = fields[0]
        curr_price = float(fields[2])
        return ticker, curr_price
    except Exception:
        return None


async def _stream(tickers: list[str], approval_key: str):
    """WebSocket 연결 후 tickers 구독 → Redis 저장"""
    ws_url = _PAPER_WS if settings.KIS_IS_PAPER else _REAL_WS
    r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    deadline = asyncio.get_event_loop().time() + _STREAM_DURATION

    async with websockets.connect(ws_url, ping_interval=30) as ws:
        # 각 ticker 구독
        for ticker in tickers:
            sub_msg = json.dumps({
                "header": {
                    "approval_key": approval_key,
                    "custtype": "P",
                    "tr_type": "1",   # 등록
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",
                        "tr_key": ticker,
                    }
                },
            })
            await ws.send(sub_msg)
            logger.info("[KisPriceStream] 구독 등록: %s", ticker)

        logger.info("[KisPriceStream] %d개 종목 구독 완료, 시세 수신 시작", len(tickers))

        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                continue

            result = _parse_price(raw)
            if result:
                ticker, price = result
                key = f"rt:price:{ticker}"
                r.setex(key, _RT_PRICE_TTL, str(price))


@celery_app.task(name="tasks.kis_price_stream.start_price_stream", bind=True, max_retries=2)
def start_price_stream(self):
    """
    장 시작 전 호출되는 Celery 태스크.
    RUNNING 봇의 tickers를 KIS WebSocket으로 구독하여
    Redis rt:price:{ticker} 에 실시간 가격을 저장한다.
    """
    if not settings.KIS_APP_KEY or not settings.KIS_APP_SECRET:
        logger.warning("[KisPriceStream] KIS 키 미설정 → 스트림 생략")
        return

    tickers = _get_running_tickers()
    if not tickers:
        logger.info("[KisPriceStream] RUNNING 봇 없음 → 스트림 생략")
        return

    try:
        approval_key = _get_approval_key()
    except Exception as e:
        logger.error("[KisPriceStream] approval_key 발급 실패: %s", e)
        raise self.retry(exc=e, countdown=60)

    logger.info("[KisPriceStream] 스트림 시작 (tickers=%d)", len(tickers))
    try:
        asyncio.run(_stream(tickers, approval_key))
    except Exception as e:
        logger.error("[KisPriceStream] 스트림 오류: %s", e, exc_info=True)
        raise self.retry(exc=e, countdown=60)
    logger.info("[KisPriceStream] 스트림 종료")
