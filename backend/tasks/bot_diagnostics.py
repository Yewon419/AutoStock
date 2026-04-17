"""
봇 자동 진단 태스크 (프리미엄 기능)
- 평일 15:35 KST (장 마감 후) 실행
- RUNNING 봇 성과를 Claude로 분석 → Redis 알림 푸시
- PREMIUM_FEATURE 플래그: 나중에 구독 플랜 게이팅 포인트
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Position, Execution
from models.strategy import Strategy
from tasks.bot_engine import _push_alert

logger = logging.getLogger(__name__)

PREMIUM_FEATURE = True  # True = 프리미엄 전용 (현재는 무조건 실행, 나중에 구독 체크로 교체)


def _build_bot_summary(db, bot: TradingBot) -> str:
    """봇 1개의 성과 요약 텍스트 생성"""
    strat = db.query(Strategy).filter_by(id=bot.strategy_id).first()
    positions = db.query(Position).filter_by(bot_id=bot.id).all()
    since = datetime.now(tz=timezone.utc) - timedelta(days=30)
    sells = db.query(Execution).filter(
        Execution.bot_id == bot.id,
        Execution.execution_type == "SELL",
        Execution.executed_at >= since,
    ).all()

    trade_count = len(sells)
    win_count = sum(1 for e in sells if float(e.profit_loss or 0) > 0)
    realized_pnl = sum(float(e.profit_loss or 0) for e in sells)
    win_rate = round(win_count / trade_count * 100, 1) if trade_count else None
    cash_pnl = float(bot.cash) - float(bot.initial_cash)

    lines = [
        f"봇: {bot.name} (id={bot.id}, mode={bot.mode})",
        f"전략: {strat.name if strat else '없음'} / 타입: {strat.strategy_type if strat else '-'}",
        f"조건: {json.dumps(strat.conditions, ensure_ascii=False) if strat else '[]'}",
        f"stop_loss={float(bot.stop_loss_pct)}% / take_profit={float(bot.take_profit_pct)}%",
        f"초기자금={float(bot.initial_cash):,.0f} / 현재cash={float(bot.cash):,.0f} / 현금손익={cash_pnl:+,.0f}",
        f"포지션: {len(positions)}개 (max={bot.max_positions})",
    ]

    for p in positions:
        lines.append(f"  - {p.ticker} {p.quantity}주 avg={float(p.avg_price):,.0f}")

    lines += [
        f"최근30일 매도: {trade_count}건 / 익절:{win_count} 손절:{trade_count - win_count}",
        f"승률: {win_rate}% / 실현손익: {realized_pnl:+,.0f}원" if win_rate is not None else "승률: 데이터 없음",
    ]

    return "\n".join(lines)


@celery_app.task(name="tasks.bot_diagnostics.run_bot_diagnostics")
def run_bot_diagnostics():
    """평일 15:35 KST 실행 — RUNNING 봇 전체 성과 자동 진단"""
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("[bot_diagnostics] ANTHROPIC_API_KEY 없음 — 진단 스킵")
        return

    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(TradingBot.status == "RUNNING").all()
        if not bots:
            logger.info("[bot_diagnostics] RUNNING 봇 없음")
            return

        summaries = []
        for bot in bots:
            try:
                summaries.append(_build_bot_summary(db, bot))
            except Exception as e:
                logger.error("[bot_diagnostics] bot_id=%d 요약 실패: %s", bot.id, e)

        if not summaries:
            return

        combined = "\n\n---\n\n".join(summaries)
        prompt = f"""아래는 오늘 장 마감 기준 자동매매 봇들의 성과 요약입니다.
각 봇에 대해 한국 주식 전문가 관점에서 간결하게 진단하세요.

분석 항목:
1. 전략 조건의 적절성 (지표 범위, 과매수/과매도 구간 여부)
2. 손익 구조 (stop_loss vs take_profit 비율, 승률)
3. 포지션 수 이상 여부 (max_positions 초과 시 명시)
4. 핵심 개선 제안 1~2가지 (구체적으로)

응답 형식 (JSON):
{{"diagnostics": [{{"bot_id": 17, "status": "warning", "summary": "한 문장 요약", "issues": ["이슈1", "이슈2"], "suggestion": "핵심 개선 제안"}}]}}

status: "ok" | "warning" | "critical"
---
{combined}"""

        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())

        for diag in parsed.get("diagnostics", []):
            bot_id = diag.get("bot_id")
            status = diag.get("status", "ok")
            summary = diag.get("summary", "")
            issues = diag.get("issues", [])
            suggestion = diag.get("suggestion", "")

            bot = next((b for b in bots if b.id == bot_id), None)
            if not bot:
                continue

            alert_type = "DIAGNOSTIC_WARNING" if status == "warning" else (
                "DIAGNOSTIC_CRITICAL" if status == "critical" else "DIAGNOSTIC_OK"
            )
            msg_parts = [f"[자동진단] {summary}"]
            if issues:
                msg_parts.append("이슈: " + " / ".join(issues))
            if suggestion:
                msg_parts.append(f"제안: {suggestion}")

            _push_alert(bot_id, bot.name, alert_type, "\n".join(msg_parts))
            logger.info("[bot_diagnostics] bot_id=%d status=%s 진단 완료", bot_id, status)

    except json.JSONDecodeError as e:
        logger.error("[bot_diagnostics] Claude 응답 파싱 실패: %s | raw=%s", e, raw[:200])
    except Exception as e:
        logger.error("[bot_diagnostics] 진단 태스크 오류: %s", e, exc_info=True)
    finally:
        db.close()
