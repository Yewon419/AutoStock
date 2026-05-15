"""봇 단위 자동 튜닝 제안 task.

매일 평일 08:30 KST 실행 — RUNNING 봇 순회하며 LLM에게 진단을 받아
tuning_suggestions 테이블에 'pending' 상태로 드롭. 사용자는 캔버스 알림함에서
확인 후 [적용]/[기각]을 선택한다.

bot_canvas API의 LLM 헬퍼(_build_tuning_context, _call_tuning_llm)를 재활용.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException

from tasks.celery_app import celery_app
from core.database import SessionLocal
from models.strategy import Strategy, TuningSuggestion
from models.trading import TradingBot


logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.bot_tuning.propose_tuning_for_running_bots")
def propose_tuning_for_running_bots() -> dict:
    """RUNNING 봇별로 LLM 진단을 받아 tuning_suggestions에 'pending'으로 저장."""
    from api.bot_canvas import _build_tuning_context, _call_tuning_llm

    db = SessionLocal()
    proposed = 0
    skipped = 0
    failed = 0
    try:
        running_bots = (
            db.query(TradingBot)
            .filter(TradingBot.status == "RUNNING")
            .all()
        )
        logger.info("[bot_tuning] RUNNING 봇 %d개 순회 시작", len(running_bots))

        for bot in running_bots:
            try:
                strategy = (
                    db.query(Strategy).filter(Strategy.bot_id == bot.id).first()
                )
                if not strategy:
                    logger.warning("[bot_tuning] bot_%d: strategy 없음 (skip)", bot.id)
                    skipped += 1
                    continue

                context = _build_tuning_context(db, bot, strategy)
                user_msg = (
                    "이 봇의 최근 성과를 분석해서 개선안"
                    "(strategy.conditions 또는 risk_params)을 제시하세요."
                )
                result = _call_tuning_llm(context, user_msg)

                proposed_conditions = result.get("proposed_conditions")
                proposed_risk_params = result.get("proposed_risk_params")
                if proposed_conditions is None and proposed_risk_params is None:
                    logger.info("[bot_tuning] bot_%d: 변경 제안 없음 (skip)", bot.id)
                    skipped += 1
                    continue

                sugg = TuningSuggestion(
                    bot_id=bot.id,
                    suggested_conditions=proposed_conditions,
                    suggested_risk_params=proposed_risk_params,
                    diagnosis_text=result.get("diagnosis") or result.get("reply") or "(no diagnosis)",
                )
                db.add(sugg)
                db.commit()
                db.refresh(sugg)
                logger.info(
                    "[bot_tuning] bot_%d: 제안 생성 (suggestion_id=%d)",
                    bot.id, sugg.id,
                )
                proposed += 1
            except HTTPException as e:
                logger.error("[bot_tuning] bot_%d: LLM 호출 실패 (%d) %s", bot.id, e.status_code, e.detail)
                db.rollback()
                failed += 1
            except Exception as e:
                logger.exception("[bot_tuning] bot_%d: 예외 발생: %s", bot.id, e)
                db.rollback()
                failed += 1

        result_summary = {
            "running_bots": len(running_bots),
            "proposed": proposed,
            "skipped": skipped,
            "failed": failed,
        }
        logger.info("[bot_tuning] 완료: %s", result_summary)
        return result_summary
    finally:
        db.close()
