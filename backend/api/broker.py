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
    r = _redis()

    if mode in ("paper", "real"):
        token = r.get("kis:access_token")
        token_ok = token is not None
        ttl = r.ttl("kis:access_token")
        return {
            "mode": mode,
            "connected": token_ok,
            "kis_account": settings.KIS_ACCOUNT_NO,
            "kis_is_paper": settings.KIS_IS_PAPER,
            "token_ttl": ttl if ttl and ttl > 0 else None,
        }

    return {"mode": mode, "connected": None, "kis_account": None, "kis_is_paper": None, "token_ttl": None}


@router.post("/connect")
def connect_broker(_: dict = Depends(get_current_user)):
    """KIS access_token 강제 갱신"""
    if settings.BROKER_MODE not in ("paper", "real"):
        return {"message": "mock 모드에서는 연결이 필요 없습니다", "mode": "mock"}

    r = _redis()
    r.delete("kis:access_token")   # 캐시 삭제 → 다음 주문 시 자동 재발급

    from broker.kis_broker import KisBroker
    try:
        token = KisBroker()._get_token()
        return {"message": "KIS 토큰 발급 성공", "success": True}
    except Exception as e:
        return {"message": f"KIS 토큰 발급 실패: {e}", "success": False}


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
