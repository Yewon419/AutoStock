"""Portfolio Circuit Breaker — 포트폴리오 전체 평가손실이 한계치 접근 시 자동 방어.

부모님 자금 유치를 위한 무손실 시연 보장 — 한 번도 -10% 가본 적 없게 하는 *사전* 차단.

3단계:
- WARN  -7%  → 신규 매수 차단 (NEW_BUY_BLOCKED 플래그)
- PAUSE -8.5% → 모든 RUNNING 봇을 PAUSED, 알림
- HALT  -10%  → 전 포지션 강제 시장가 청산, 봇 STOPPED, 직접 개입 요구

판정 대상: 각 봇의 mode가 'paper' 또는 'real'인 봇만 (mock 제외).
계산: sum(initial_cash) 대비 sum(현재 평가액) 비율.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import redis as redis_sync
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Position
from services.trading_service import enrich_bot_assets

logger = logging.getLogger(__name__)

# 임계값 (% 손실, 양수로 표기)
THRESHOLD_WARN_PCT = 7.0
THRESHOLD_PAUSE_PCT = 8.5
THRESHOLD_HALT_PCT = 10.0

# Redis 키
NEW_BUY_BLOCK_KEY = "autostock:cb:new_buy_blocked"          # 존재하면 신규 매수 차단
STATE_KEY = "autostock:cb:state"                             # JSON 스냅샷
LAST_ALERT_KEY = "autostock:cb:last_alert:{level}"          # 디덥 (60분 TTL)
LAST_ALERT_TTL = 3600
ALERTS_KEY = "autostock:alerts"

# 판정 대상 모드
TRACKED_MODES = ("paper", "real")


@dataclass
class CircuitState:
    level: str               # OK | WARN | PAUSE | HALT
    portfolio_pnl_pct: float
    total_initial: float
    total_current: float
    bot_count: int
    triggered_actions: list


def _push_alert(r, alert_type: str, message: str, extra: Optional[dict] = None) -> None:
    payload = {
        "type": alert_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    try:
        r.lpush(ALERTS_KEY, json.dumps(payload, ensure_ascii=False))
        r.ltrim(ALERTS_KEY, 0, 199)
    except Exception as e:
        logger.warning("[circuit_breaker] alert push 실패: %s", e)


def _alert_dedup(r, level: str) -> bool:
    """레벨별 60분 디덥 — 같은 레벨 알림 중복 방지. (True = 발령 가능)"""
    key = LAST_ALERT_KEY.format(level=level)
    if r.exists(key):
        return False
    r.setex(key, LAST_ALERT_TTL, "1")
    return True


def compute_portfolio_state(db: Session) -> CircuitState:
    """현재 paper/real 봇 전체의 평가손익률 계산."""
    bots = db.query(TradingBot).filter(TradingBot.mode.in_(TRACKED_MODES)).all()

    total_initial = 0.0
    total_current = 0.0
    for b in bots:
        d = enrich_bot_assets(db, b)
        total_initial += float(b.initial_cash or 0)
        total_current += float(d.get("total_assets") or 0)

    if total_initial <= 0:
        return CircuitState(level="OK", portfolio_pnl_pct=0.0,
                            total_initial=0.0, total_current=0.0,
                            bot_count=len(bots), triggered_actions=[])

    pnl_pct = (total_current - total_initial) / total_initial * 100.0

    if pnl_pct <= -THRESHOLD_HALT_PCT:
        level = "HALT"
    elif pnl_pct <= -THRESHOLD_PAUSE_PCT:
        level = "PAUSE"
    elif pnl_pct <= -THRESHOLD_WARN_PCT:
        level = "WARN"
    else:
        level = "OK"

    return CircuitState(
        level=level, portfolio_pnl_pct=round(pnl_pct, 3),
        total_initial=round(total_initial, 2), total_current=round(total_current, 2),
        bot_count=len(bots), triggered_actions=[],
    )


def is_new_buy_blocked() -> bool:
    """다른 코드(bot_engine.py 등)에서 신규 매수 직전 호출 — 진입 차단 신호 확인."""
    try:
        r = redis_sync.from_url(settings.REDIS_URL)
        return bool(r.exists(NEW_BUY_BLOCK_KEY))
    except Exception:
        return False  # Redis 장애 시 차단하지 않음 (안전 우선 vs 가용성 트레이드오프)


def _enforce_warn(r) -> list:
    actions = []
    r.set(NEW_BUY_BLOCK_KEY, "1")
    actions.append("NEW_BUY_BLOCK_set")
    return actions


def _enforce_pause(db: Session, r) -> list:
    actions = _enforce_warn(r)
    bots = db.query(TradingBot).filter(
        TradingBot.mode.in_(TRACKED_MODES),
        TradingBot.status == "RUNNING",
    ).all()
    for b in bots:
        b.status = "PAUSED"
        actions.append(f"bot_{b.id}_PAUSED")
    db.commit()
    return actions


def _enforce_halt(db: Session, r) -> list:
    """HALT는 즉각 청산이 필요하지만 실제 시장가 매도는 broker 의존이므로,
    여기서는 봇 STOPPED로 신규 동작 차단 + 보유 포지션 청산 신호만 발행한다.
    실제 청산은 별도 task(emergency_liquidate)에서 처리하거나 사람 개입.
    """
    actions = _enforce_warn(r)
    bots = db.query(TradingBot).filter(
        TradingBot.mode.in_(TRACKED_MODES),
        TradingBot.status.in_(["RUNNING", "PAUSED"]),
    ).all()
    halted_ids = []
    for b in bots:
        b.status = "STOPPED"
        halted_ids.append(b.id)
        actions.append(f"bot_{b.id}_STOPPED")
    db.commit()

    # 청산 시그널 — 별도 task가 picking up
    r.set("autostock:cb:emergency_liquidate", json.dumps({
        "bots": halted_ids,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }))
    actions.append(f"emergency_liquidate_signal({len(halted_ids)} bots)")
    return actions


def _publish_state(r, state: CircuitState) -> None:
    r.set(STATE_KEY, json.dumps({
        "level": state.level,
        "portfolio_pnl_pct": state.portfolio_pnl_pct,
        "total_initial": state.total_initial,
        "total_current": state.total_current,
        "bot_count": state.bot_count,
        "triggered_actions": state.triggered_actions,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False))


def evaluate_and_enforce() -> CircuitState:
    """Beat 매 분 호출 — 포트폴리오 평가 + 임계치 진입 시 즉각 enforce + 알림."""
    db = SessionLocal()
    r = redis_sync.from_url(settings.REDIS_URL)
    try:
        state = compute_portfolio_state(db)

        if state.level == "HALT":
            state.triggered_actions = _enforce_halt(db, r)
            if _alert_dedup(r, "HALT"):
                _push_alert(r, "PORTFOLIO_CIRCUIT_BREAKER", (
                    f"[HALT] 포트폴리오 손실 {state.portfolio_pnl_pct:+.2f}% (≤-{THRESHOLD_HALT_PCT}%) — "
                    f"전 봇 STOPPED + 청산 시그널 발행. 직접 개입 요구."
                ), {"state": state.level, "pnl_pct": state.portfolio_pnl_pct})
        elif state.level == "PAUSE":
            state.triggered_actions = _enforce_pause(db, r)
            if _alert_dedup(r, "PAUSE"):
                _push_alert(r, "PORTFOLIO_DRAWDOWN_PAUSE", (
                    f"[PAUSE] 포트폴리오 손실 {state.portfolio_pnl_pct:+.2f}% (≤-{THRESHOLD_PAUSE_PCT}%) — "
                    f"모든 봇 PAUSED, 신규 매수 차단."
                ), {"state": state.level, "pnl_pct": state.portfolio_pnl_pct})
        elif state.level == "WARN":
            state.triggered_actions = _enforce_warn(r)
            if _alert_dedup(r, "WARN"):
                _push_alert(r, "PORTFOLIO_DRAWDOWN_WARN", (
                    f"[WARN] 포트폴리오 손실 {state.portfolio_pnl_pct:+.2f}% (≤-{THRESHOLD_WARN_PCT}%) — "
                    f"신규 매수 차단. 운영 점검 필요."
                ), {"state": state.level, "pnl_pct": state.portfolio_pnl_pct})
        else:
            # OK 회복 — 차단 해제 (PAUSE/HALT는 자동 복귀 안 함, 사람 결정)
            if r.exists(NEW_BUY_BLOCK_KEY):
                r.delete(NEW_BUY_BLOCK_KEY)
                state.triggered_actions = ["NEW_BUY_BLOCK_cleared"]
                if _alert_dedup(r, "RECOVERED"):
                    _push_alert(r, "PORTFOLIO_DRAWDOWN_RECOVERED", (
                        f"[OK] 포트폴리오 손실 {state.portfolio_pnl_pct:+.2f}% — 신규 매수 차단 해제."
                    ), {"state": state.level, "pnl_pct": state.portfolio_pnl_pct})

        _publish_state(r, state)
        return state
    finally:
        db.close()
