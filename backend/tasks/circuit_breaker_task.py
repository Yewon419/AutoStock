"""Circuit Breaker Celery 래퍼 — 매 1분 정규장 시간 평가."""
from __future__ import annotations

import logging

from tasks.celery_app import celery_app
from services.circuit_breaker import evaluate_and_enforce

logger = logging.getLogger(__name__)


def _is_market_hours() -> bool:
    from datetime import datetime, timezone, timedelta
    kst = datetime.now(timezone(timedelta(hours=9)))
    if kst.weekday() >= 5:
        return False
    cur = kst.hour * 60 + kst.minute
    # 09:00 ~ 15:30 KST + 종가 후 15분 여유 (장 마감 직후 평가도 실행)
    return 9 * 60 <= cur < 15 * 60 + 45


@celery_app.task(name="tasks.circuit_breaker_task.run_circuit_breaker")
def run_circuit_breaker():
    if not _is_market_hours():
        return {"status": "skipped", "reason": "outside_market_hours"}
    state = evaluate_and_enforce()
    return {
        "status": "ok",
        "level": state.level,
        "portfolio_pnl_pct": state.portfolio_pnl_pct,
        "bot_count": state.bot_count,
        "actions": state.triggered_actions,
    }
