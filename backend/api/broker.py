"""
브로커 상태 API
- 현재 BROKER_MODE 반환
- real 모드일 때 브릿지 연결 상태 확인
- 브릿지 연결 트리거 (CONNECT 명령 발행)
- 비상정지 (모든 RUNNING 봇 즉시 STOPPED)
- 알림 목록 조회
"""
import json
import redis

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from models.trading import TradingBot

router = APIRouter(prefix="/broker", tags=["broker"])

BRIDGE_STATUS_KEY = "autostock:bridge_status"
CMD_CHANNEL = "autostock:commands"
ALERTS_KEY = "autostock:alerts"


def _redis():
    return redis.from_url(settings.REDIS_URL)


@router.get("/status")
def get_broker_status(_: dict = Depends(get_current_user)):
    mode = settings.BROKER_MODE
    connected = None

    if mode == "real":
        r = _redis()
        val = r.get(BRIDGE_STATUS_KEY)
        connected = val is not None and val.decode() == "connected"

    return {"mode": mode, "connected": connected}


@router.post("/connect")
def connect_broker(_: dict = Depends(get_current_user)):
    """키움 브릿지에 로그인 명령 발행"""
    if settings.BROKER_MODE != "real":
        return {"message": "mock 모드에서는 연결이 필요 없습니다", "mode": "mock"}

    r = _redis()
    r.publish(CMD_CHANNEL, json.dumps({"type": "CONNECT"}))
    return {"message": "CONNECT 명령을 전송했습니다. 브릿지 응답을 대기 중입니다."}


@router.post("/emergency-stop")
def emergency_stop(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """현재 사용자의 모든 RUNNING 봇을 즉시 STOPPED 처리"""
    user_id = int(current_user['sub'])
    running = db.query(TradingBot).filter(
        TradingBot.user_id == user_id,
        TradingBot.status == 'RUNNING',
    ).all()

    stopped = []
    for bot in running:
        bot.status = 'STOPPED'
        stopped.append({'id': bot.id, 'name': bot.name})

    db.commit()
    return {"stopped": stopped, "count": len(stopped)}


@router.get("/alerts")
def get_alerts(
    limit: int = 20,
    _: dict = Depends(get_current_user),
):
    """Redis에서 최근 알림 목록 반환"""
    r = _redis()
    items = r.lrange(ALERTS_KEY, 0, limit - 1)
    alerts = []
    for item in items:
        try:
            alerts.append(json.loads(item))
        except Exception:
            pass
    return alerts


@router.delete("/alerts")
def clear_alerts(_: dict = Depends(get_current_user)):
    """알림 목록 초기화"""
    r = _redis()
    r.delete(ALERTS_KEY)
    return {"message": "알림이 모두 삭제되었습니다"}
