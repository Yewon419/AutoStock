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

# universe 동기화 — scanner가 봇 tickers 갱신 후 SET. stream이 polling으로 감지해
# 정상 종료 → watchdog이 다음 분 stale 보고 새 universe로 재기동. 키 DEL은 watchdog 책임.
_STREAM_UNIVERSE_DIRTY_KEY = "autostock:price_stream:universe_dirty"

# 끊김 시 재연결 정책
_RECONNECT_MAX = 20
_RECONNECT_BACKOFF_INITIAL = 5
_RECONNECT_BACKOFF_MAX = 300

# Watchdog 정책
_WATCHDOG_STALE_SECONDS = 180          # heartbeat 누락 180s 이상이면 재기동 트리거
_WATCHDOG_RESTART_COUNT_KEY = "autostock:watchdog:restart_count"  # sliding 30m count
_WATCHDOG_LAST_ACTION_KEY = "autostock:watchdog:last_action_ts"
_WATCHDOG_ESCALATE_KEY = "autostock:watchdog:escalated"           # 30m TTL 키
_WATCHDOG_WINDOW_SECONDS = 1800        # 30분 슬라이딩 윈도우
_WATCHDOG_ESCALATE_THRESHOLD = 3       # 30분 내 3회 초과 → 에스컬레이션
_ALERTS_KEY = "autostock:alerts"
# KRX 정규장: 평일 09:00~15:30 KST. Watchdog는 정규장 시간에만 재기동을 시도한다.
_MARKET_OPEN_HOUR = 9                  # KST
_MARKET_OPEN_MINUTE = 0
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MINUTE = 30


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

        # 연결 직후 1회 heartbeat 갱신 — WS alive 신호 (메시지 수신 전이라도)
        try:
            redis_client.setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, str(int(_time.time())))
        except Exception as e:
            logger.warning("[KisPriceStream] 초기 heartbeat 갱신 실패: %r", e)

        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                # 30s 동안 메시지 없음 — WS는 살아있음(ping_interval=30이 keepalive 처리).
                # 거래 무발생 구간(장 종료 후, 점심시간 무거래)에도 heartbeat을 유지해
                # watchdog의 false-positive 재기동을 방지한다.
                try:
                    redis_client.setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, str(int(_time.time())))
                except Exception as e:
                    logger.warning("[KisPriceStream] keepalive heartbeat 갱신 실패: %r", e)
                # universe 갱신 신호 감지 — 정상 종료해 watchdog이 새 universe로 재기동하도록.
                try:
                    if redis_client.get(_STREAM_UNIVERSE_DIRTY_KEY) is not None:
                        logger.info("[KisPriceStream] universe_dirty 감지 → 세션 종료 (재기동 유도)")
                        return msg_count
                except Exception as e:
                    logger.warning("[KisPriceStream] dirty 키 조회 실패: %r", e)
                continue

            result = _parse_price(raw)
            if not result:
                # 비-가격 메시지(ping/pong, 시스템 메시지 등)도 WS alive 시그널 → heartbeat 갱신
                try:
                    redis_client.setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, str(int(_time.time())))
                except Exception:
                    pass
                continue
            ticker, price = result
            try:
                redis_client.setex(f"rt:price:{ticker}", _RT_PRICE_TTL, str(price))
                redis_client.setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, str(int(_time.time())))
                msg_count += 1
                # universe 갱신 신호 — 장 활성으로 메시지가 계속 들어오면 timeout 분기를 안 타므로
                # 여기서도 주기적으로 폴링. 매 100건(시장 활성 시 ~10초) 간격이면 충분히 빠르고
                # redis 부담 작음.
                if msg_count % 100 == 0:
                    if redis_client.get(_STREAM_UNIVERSE_DIRTY_KEY) is not None:
                        logger.info(
                            "[KisPriceStream] universe_dirty 감지 (msg=%d) → 세션 종료 (재기동 유도)",
                            msg_count,
                        )
                        return msg_count
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
    # 이 task는 이미 fresh universe(_get_running_tickers 결과)로 진입했으므로 stale dirty 신호는 정리.
    # 안 하면 첫 iteration에서 자기 자신이 다시 종료 → 무한 재기동 루프.
    try:
        r.delete(_STREAM_UNIVERSE_DIRTY_KEY)
    except Exception as e:
        logger.warning("[KisPriceStream] 진입 시 dirty 정리 실패: %r", e)
    deadline = asyncio.get_event_loop().time() + _STREAM_DURATION
    backoff = _RECONNECT_BACKOFF_INITIAL
    attempts = 0
    while asyncio.get_event_loop().time() < deadline and attempts < _RECONNECT_MAX:
        # universe 갱신 신호 감지 — task 자체를 종료해 watchdog이 새 universe로 재기동하게 함.
        # heartbeat 키를 명시적 DEL해 watchdog의 stale 감지 시차를 단축(최대 ~120s → ~60s).
        try:
            if r.get(_STREAM_UNIVERSE_DIRTY_KEY) is not None:
                logger.info("[KisPriceStream] universe_dirty — task 종료 (watchdog이 새 universe로 재기동)")
                try:
                    r.delete(_HEARTBEAT_KEY)
                except Exception:
                    pass
                return
        except Exception as e:
            logger.warning("[KisPriceStream] dirty 키 조회 실패(reconnect 루프): %r", e)

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


def _is_market_hours() -> bool:
    """KST 평일 09:00~15:30(KRX 정규장)인지 판단. 장외에는 watchdog이 재기동을 시도하지 않는다."""
    from datetime import datetime, timezone, timedelta
    kst = datetime.now(timezone(timedelta(hours=9)))
    if kst.weekday() >= 5:  # 토(5), 일(6)
        return False
    cur_minutes = kst.hour * 60 + kst.minute
    open_minutes = _MARKET_OPEN_HOUR * 60 + _MARKET_OPEN_MINUTE
    close_minutes = _MARKET_CLOSE_HOUR * 60 + _MARKET_CLOSE_MINUTE
    return open_minutes <= cur_minutes < close_minutes


def _push_alert(redis_client, alert_type: str, message: str, extra: dict | None = None) -> None:
    from datetime import datetime, timezone
    payload = {
        "type": alert_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    try:
        redis_client.lpush(_ALERTS_KEY, json.dumps(payload, ensure_ascii=False))
        redis_client.ltrim(_ALERTS_KEY, 0, 199)  # 최근 200건 유지
    except Exception as e:
        logger.warning("[Watchdog] alert push 실패: %s", e)


def _is_start_task_active(celery_inspect) -> bool:
    """celery inspect.active() 결과에 start_price_stream task가 떠 있는지 확인."""
    try:
        active = celery_inspect.active() or {}
    except Exception as e:
        logger.warning("[Watchdog] inspect.active 실패 (보수적으로 active=True 처리): %s", e)
        return True  # 알 수 없을 땐 재기동을 보류 (안전 우선)
    for _worker, tasks in active.items():
        for t in tasks or []:
            if (t.get("name") or "").endswith("start_price_stream"):
                return True
    return False


@celery_app.task(name="tasks.kis_price_stream.watchdog_price_stream")
def watchdog_price_stream():
    """KIS 실시간 시세 스트림 Heartbeat Watchdog.

    매 1분 실행 (Celery beat). 장중에만 동작.
    - heartbeat 키가 stale이고 active task가 없으면 start_price_stream을 재기동
    - 30분 내 3회 초과 재기동 시 에스컬레이션 알림 (코드 결함/외부 장애 의심)
    """
    if not _is_market_hours():
        return {"status": "skipped", "reason": "outside_market_hours"}

    if not settings.KIS_APP_KEY or not settings.KIS_APP_SECRET:
        return {"status": "skipped", "reason": "kis_keys_missing"}

    r = redis_sync.from_url(settings.REDIS_URL)

    # 1) heartbeat 상태 확인
    raw_ts = r.get(_HEARTBEAT_KEY)
    now = int(_time.time())
    if raw_ts is not None:
        try:
            last_ts = int(raw_ts)
        except (TypeError, ValueError):
            last_ts = 0
        age = now - last_ts
        if age < _WATCHDOG_STALE_SECONDS:
            return {"status": "ok", "heartbeat_age_s": age}
    else:
        age = None  # 키 자체가 없음 (TTL 만료 또는 미기록)

    # 2) RUNNING 봇이 없으면 스트림이 없는 게 정상 — skip
    try:
        running_tickers = _get_running_tickers()
    except Exception as e:
        logger.warning("[Watchdog] RUNNING 봇 조회 실패: %s", e)
        running_tickers = []
    if not running_tickers:
        return {"status": "skipped", "reason": "no_running_bots"}

    # 3) celery에 start_price_stream이 이미 떠 있으면 reconnect 진행 중일 가능성
    inspect = celery_app.control.inspect(timeout=2.0)
    if _is_start_task_active(inspect):
        logger.info("[Watchdog] heartbeat stale (age=%s) but start_task active — 재기동 보류", age)
        return {"status": "deferred", "reason": "start_task_active", "heartbeat_age_s": age}

    # 4) 30분 윈도우 내 재기동 횟수 체크
    try:
        cur_count = int(r.get(_WATCHDOG_RESTART_COUNT_KEY) or 0)
    except (TypeError, ValueError):
        cur_count = 0

    if cur_count >= _WATCHDOG_ESCALATE_THRESHOLD:
        # 에스컬레이션 — 30분 윈도우 내 1번만 알림 (escalated 키 TTL로 디덥)
        if not r.exists(_WATCHDOG_ESCALATE_KEY):
            r.setex(_WATCHDOG_ESCALATE_KEY, _WATCHDOG_WINDOW_SECONDS, "1")
            msg = (
                f"[Watchdog] 30분 내 재기동 {cur_count}회 누적 — 코드 결함/외부 장애 의심. "
                f"heartbeat_age_s={age} running_tickers={len(running_tickers)}"
            )
            logger.error(msg)
            _push_alert(r, "STREAM_WATCHDOG_ESCALATE", msg, {"restart_count": cur_count, "heartbeat_age_s": age})
        return {"status": "escalated", "restart_count": cur_count, "heartbeat_age_s": age}

    # 5) 재기동 — start_price_stream을 stream 큐에 enqueue
    try:
        async_result = start_price_stream.apply_async(queue="stream")
        new_count = r.incr(_WATCHDOG_RESTART_COUNT_KEY)
        # 첫 진입 시에만 TTL 설정 → 30분 슬라이딩 윈도우
        if new_count == 1:
            r.expire(_WATCHDOG_RESTART_COUNT_KEY, _WATCHDOG_WINDOW_SECONDS)
        from datetime import datetime, timezone
        r.set(_WATCHDOG_LAST_ACTION_KEY, datetime.now(timezone.utc).isoformat())
        # universe_dirty 신호로 인한 재기동이었다면 키 정리 (없어도 무해).
        try:
            r.delete(_STREAM_UNIVERSE_DIRTY_KEY)
        except Exception:
            pass

        msg = (
            f"[Watchdog] heartbeat stale (age={age}s) — start_price_stream 재기동 "
            f"(window count={new_count}/{_WATCHDOG_ESCALATE_THRESHOLD}, task_id={async_result.id})"
        )
        logger.warning(msg)
        _push_alert(r, "STREAM_WATCHDOG_RESTART", msg, {
            "restart_count": new_count,
            "heartbeat_age_s": age,
            "task_id": async_result.id,
        })
        return {
            "status": "restarted",
            "restart_count": new_count,
            "heartbeat_age_s": age,
            "task_id": async_result.id,
        }
    except Exception as e:
        logger.error("[Watchdog] 재기동 enqueue 실패: %s", e, exc_info=True)
        _push_alert(r, "STREAM_WATCHDOG_ERROR", f"재기동 enqueue 실패: {e}")
        return {"status": "error", "error": str(e)}


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
