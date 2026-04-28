"""
KIS WebSocket 실시간 시세 스트림
- 장 시작 전(08:55) Celery beat에 의해 start_price_stream 태스크 실행
- 함수 내부 reconnect 루프로 장중 끊김 자동 복구 (max 20회, expo backoff 5→300s)
- 메시지 수신마다 Redis 헬스 키(autostock:price_stream_heartbeat) 갱신
- 5분마다 수신 통계 로깅
- WebSocket 모의: ws://ops.koreainvestment.com:31000
- WebSocket 실계좌: ws://ops.koreainvestment.com:21000
"""
import asyncio
import json
import logging
import time as _time

import redis as redis_sync
import requests
import websockets

from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_PAPER_WS = "ws://ops.koreainvestment.com:31000"
_REAL_WS  = "ws://ops.koreainvestment.com:21000"

_RT_PRICE_TTL = 60                # Redis TTL (초)
_HEARTBEAT_KEY = "autostock:price_stream_heartbeat"
_HEARTBEAT_TTL = 120               # 2분 — 그 이상 갱신 없으면 stale
_STREAM_DURATION = 7 * 3600        # 최대 7시간 유지 (08:55 ~ 15:55)
_STATS_INTERVAL = 300              # 5분마다 통계 로그

# 끊김 시 재연결 정책
_RECONNECT_MAX = 20
_RECONNECT_BACKOFF_INITIAL = 5
_RECONNECT_BACKOFF_MAX = 300


def _get_running_tickers() -> list[str]:
    """RUNNING 상태 봇의 tickers 전체 수집 (중복 제거)"""
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(TradingBot.status == 'RUNNING').all()
        tickers: set[str] = set()
        for bot in bots:
            for t in (bot.tickers or []):
                tickers.add(t)
        return list(tickers)
    finally:
        db.close()


def _get_approval_key() -> str:
    """KIS WebSocket 접속키 발급. 실패 시 status·body 일부를 RuntimeError에 담아 디버깅 가능하게."""
    is_paper = settings.KIS_IS_PAPER
    base = "https://openapivts.koreainvestment.com:29443" if is_paper else "https://openapi.koreainvestment.com:9443"
    url = f"{base}/oauth2/Approval"
    payload = {
        "grant_type": "client_credentials",
        "appkey": settings.KIS_APP_KEY,
        "secretkey": settings.KIS_APP_SECRET,
    }
    resp = requests.post(url, json=payload, timeout=10)
    try:
        resp.raise_for_status()
        data = resp.json()
        return data["approval_key"]
    except Exception as e:
        snippet = (resp.text or "")[:200]
        raise RuntimeError(
            f"approval_key 발급 실패 status={resp.status_code} err={e!r} body[:200]={snippet!r}"
        )


def _parse_price(data: str) -> tuple[str, float] | None:
    """KIS 실시간 시세 메시지 파싱. 응답 형식: '0|H0STCNT0|001|{ticker}^{time}^{price}^...'."""
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


async def _stream_once(tickers: list[str], approval_key: str, redis_client, deadline: float) -> int:
    """단일 WebSocket 연결 세션. deadline 도달 또는 예외 발생 시 종료.

    수신 메시지 수를 반환. 예외(ConnectionClosed 등)는 그대로 전파해 외부 reconnect 루프에서 처리.
    """
    ws_url = _PAPER_WS if settings.KIS_IS_PAPER else _REAL_WS
    msg_count = 0
    last_stats_at = asyncio.get_event_loop().time()

    async with websockets.connect(ws_url, ping_interval=30) as ws:
        for ticker in tickers:
            sub_msg = json.dumps({
                "header": {
                    "approval_key": approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {"tr_id": "H0STCNT0", "tr_key": ticker},
                },
            })
            await ws.send(sub_msg)
        logger.info("[KisPriceStream] %d개 종목 구독 완료, 수신 시작", len(tickers))

        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                continue

            result = _parse_price(raw)
            if not result:
                continue
            ticker, price = result
            try:
                redis_client.setex(f"rt:price:{ticker}", _RT_PRICE_TTL, str(price))
                redis_client.setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, str(int(_time.time())))
                msg_count += 1
            except Exception as e:
                logger.warning("[KisPriceStream] Redis 저장 실패 %s: %r", ticker, e)

            now = asyncio.get_event_loop().time()
            if now - last_stats_at >= _STATS_INTERVAL:
                logger.info(
                    "[KisPriceStream] 5분 통계: 수신 %d건 (구독 %d종목)",
                    msg_count, len(tickers),
                )
                last_stats_at = now
                msg_count_window = msg_count
                msg_count = 0  # 윈도우 카운터 리셋
                _ = msg_count_window  # 향후 통계 확장용

    return msg_count


async def _stream_with_reconnect(tickers: list[str], approval_key: str):
    """deadline까지 WebSocket 끊기면 expo backoff로 재연결.

    backoff: 5s → 10s → 20s ... → 최대 300s. 정상 세션 후엔 리셋.
    approval_key는 만료될 수 있으므로 재연결 직전 재발급 시도(실패 시 기존 키 재사용).
    """
    r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    deadline = asyncio.get_event_loop().time() + _STREAM_DURATION
    backoff = _RECONNECT_BACKOFF_INITIAL
    attempts = 0
    while asyncio.get_event_loop().time() < deadline and attempts < _RECONNECT_MAX:
        attempts += 1
        try:
            count = await _stream_once(tickers, approval_key, r, deadline)
            logger.info("[KisPriceStream] 세션 정상 종료 msgs=%d attempt=%d", count, attempts)
            backoff = _RECONNECT_BACKOFF_INITIAL
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(
                "[KisPriceStream] 연결 끊김 attempt=%d/%d err=%r — %ds 후 재연결",
                attempts, _RECONNECT_MAX, e, backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX)
            try:
                approval_key = _get_approval_key()
                logger.info("[KisPriceStream] approval_key 재발급 완료")
            except Exception as ke:
                logger.warning("[KisPriceStream] approval_key 재발급 실패 — 기존 키 재사용: %r", ke)

    if attempts >= _RECONNECT_MAX:
        logger.error("[KisPriceStream] 재연결 최대 시도(%d) 초과 — 스트림 종료", _RECONNECT_MAX)


@celery_app.task(name="tasks.kis_price_stream.start_price_stream", bind=True, max_retries=10)
def start_price_stream(self):
    """장 시작 전 호출되는 Celery 태스크.

    내부 reconnect 루프가 끊김을 직접 처리하므로 Celery retry는 task 시작 자체가 실패하는
    경우(approval_key 발급 실패, 예외 미잡힘 등)에만 발동. retry 10회로 늘림.
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
        logger.error("[KisPriceStream] approval_key 발급 실패: %r", e)
        raise self.retry(exc=e, countdown=60)

    logger.info("[KisPriceStream] 스트림 시작 (tickers=%d)", len(tickers))
    try:
        asyncio.run(_stream_with_reconnect(tickers, approval_key))
    except Exception as e:
        logger.error("[KisPriceStream] 스트림 비정상 종료 err=%r — Celery retry", e, exc_info=True)
        raise self.retry(exc=e, countdown=60)
    logger.info("[KisPriceStream] 스트림 정상 종료")
