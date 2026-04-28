"""
봇 자동 진단 태스크 (프리미엄 기능)
- 평일 15:35 KST (장 마감 후) 실행
- RUNNING 봇 성과를 Claude로 분석 → Redis 알림 푸시
- PREMIUM_FEATURE 플래그: 나중에 구독 플랜 게이팅 포인트
- 디덥/쿨다운: (bot_id, 결함 fingerprint) 단위로 알림 압축, status별 쿨다운 적용,
  결함 해소 시 DIAGNOSTIC_RESOLVED 별도 발령
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta

import redis as redis_sync

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Position, Execution
from models.strategy import Strategy
from tasks.bot_engine import _push_alert

logger = logging.getLogger(__name__)

PREMIUM_FEATURE = True  # True = 프리미엄 전용 (현재는 무조건 실행, 나중에 구독 체크로 교체)

# 디덥/쿨다운 정책
_DIAG_LAST_KEY = "autostock:diag:last:{bot_id}"           # JSON {status, fingerprint, ts} (TTL 7d)
_DIAG_LAST_TTL = 7 * 24 * 3600
_COOLDOWN_HOURS = {
    "critical": 24,   # 동일 fingerprint 24h 내 재발령 금지 (단, fingerprint 변경 시 즉시 통과)
    "warning": 48,
    "ok": 0,          # OK는 항상 발령
}


def _bucket(value: float, edges: list[float]) -> int:
    """수치를 단조 증가 버킷 인덱스로 변환. fingerprint 안정화용."""
    for i, e in enumerate(edges):
        if value < e:
            return i
    return len(edges)


def _compute_fingerprint(db, bot: TradingBot) -> str:
    """봇 *상황 스냅샷*의 해시. (bot, strategy, 거래/손익 분포 버킷, 포지션 수)가
    같으면 동일 결함 재진단 가능성이 높다고 보고 디덥한다.

    Claude 응답 텍스트는 매번 다르므로 메시지 해시는 부적합. 대신 봇 상태로 fingerprint를 만든다.
    """
    strat = db.query(Strategy).filter_by(id=bot.strategy_id).first()
    cond_str = json.dumps(strat.conditions if strat else [], ensure_ascii=False, sort_keys=True)

    since = datetime.now(tz=timezone.utc) - timedelta(days=30)
    sells = db.query(Execution).filter(
        Execution.bot_id == bot.id,
        Execution.execution_type == "SELL",
        Execution.executed_at >= since,
    ).all()
    trade_count = len(sells)
    win_count = sum(1 for e in sells if float(e.profit_loss or 0) > 0)
    loss_count = trade_count - win_count
    win_rate = (win_count / trade_count) if trade_count else 0.0

    positions = db.query(Position).filter_by(bot_id=bot.id).count()

    # 버킷화: 거래 수가 1~2건 변하는 정도로 fingerprint가 흔들리지 않게 한다.
    trade_bucket = _bucket(trade_count, [1, 5, 10, 20, 50])
    win_bucket = _bucket(win_count, [1, 3, 5, 10, 20])
    loss_bucket = _bucket(loss_count, [1, 3, 5, 10, 20])
    win_rate_bucket = _bucket(win_rate, [0.25, 0.40, 0.55, 0.70])
    pos_bucket = _bucket(positions, [1, 3, 5, 8])

    raw = "|".join([
        str(bot.id),
        str(bot.strategy_id or ""),
        cond_str,
        f"t{trade_bucket}",
        f"w{win_bucket}",
        f"l{loss_bucket}",
        f"r{win_rate_bucket}",
        f"p{pos_bucket}",
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _load_last_diag(r, bot_id: int) -> dict:
    raw = r.get(_DIAG_LAST_KEY.format(bot_id=bot_id))
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _save_last_diag(r, bot_id: int, status: str, fingerprint: str) -> None:
    payload = {
        "status": status,
        "fingerprint": fingerprint,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    r.setex(_DIAG_LAST_KEY.format(bot_id=bot_id), _DIAG_LAST_TTL, json.dumps(payload, ensure_ascii=False))


def _should_emit(last: dict, status: str, fingerprint: str) -> tuple[bool, str]:
    """디덥/쿨다운 판정 → (발령 여부, 사유).

    - 직전 진단이 없으면 무조건 발령
    - status가 ok로 호전되면 무조건 발령 (RESOLVED는 별도로 발령됨)
    - fingerprint가 다르면 무조건 발령 (상황 변화)
    - fingerprint 같고 status 같으면 쿨다운 체크
    """
    if not last:
        return True, "first_diagnosis"
    if status == "ok":
        return True, "status_ok_always_emit"
    if last.get("fingerprint") != fingerprint:
        return True, "fingerprint_changed"
    if last.get("status") != status:
        return True, "status_changed"

    cooldown_h = _COOLDOWN_HOURS.get(status, 0)
    if cooldown_h <= 0:
        return True, "no_cooldown"
    last_ts_str = last.get("timestamp")
    if not last_ts_str:
        return True, "no_last_timestamp"
    try:
        last_ts = datetime.fromisoformat(last_ts_str)
    except Exception:
        return True, "bad_last_timestamp"
    age_h = (datetime.now(tz=timezone.utc) - last_ts).total_seconds() / 3600
    if age_h >= cooldown_h:
        return True, f"cooldown_passed({age_h:.1f}h>={cooldown_h}h)"
    return False, f"cooldown_active({age_h:.1f}h<{cooldown_h}h, fingerprint_unchanged)"


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

        r = redis_sync.from_url(settings.REDIS_URL)

        for diag in parsed.get("diagnostics", []):
            bot_id = diag.get("bot_id")
            status = (diag.get("status") or "ok").lower()
            summary = diag.get("summary", "")
            issues = diag.get("issues", [])
            suggestion = diag.get("suggestion", "")

            bot = next((b for b in bots if b.id == bot_id), None)
            if not bot:
                continue

            fingerprint = _compute_fingerprint(db, bot)
            last = _load_last_diag(r, bot_id)

            # 결함 해소 감지: 직전이 warning/critical이고 신규가 ok → RESOLVED 별도 발령
            prev_status = (last.get("status") or "").lower() if last else ""
            if status == "ok" and prev_status in ("warning", "critical"):
                resolved_msg = (
                    f"[자동진단] 직전 {prev_status.upper()} 결함 해소됨 → 현재 OK\n"
                    f"현재 진단: {summary}"
                )
                _push_alert(bot_id, bot.name, "DIAGNOSTIC_RESOLVED", resolved_msg)
                logger.info("[bot_diagnostics] bot_id=%d %s→ok RESOLVED 발령", bot_id, prev_status)

            alert_type = "DIAGNOSTIC_WARNING" if status == "warning" else (
                "DIAGNOSTIC_CRITICAL" if status == "critical" else "DIAGNOSTIC_OK"
            )

            should_emit, reason = _should_emit(last, status, fingerprint)
            if not should_emit:
                logger.info(
                    "[bot_diagnostics] bot_id=%d status=%s SUPPRESSED — %s (fp=%s)",
                    bot_id, status, reason, fingerprint,
                )
                # 디덥됐어도 last 레코드의 timestamp는 갱신하지 않음 — 쿨다운 기준은 첫 발령 시점 유지
                continue

            msg_parts = [f"[자동진단] {summary}"]
            if issues:
                msg_parts.append("이슈: " + " / ".join(issues))
            if suggestion:
                msg_parts.append(f"제안: {suggestion}")

            _push_alert(bot_id, bot.name, alert_type, "\n".join(msg_parts))
            _save_last_diag(r, bot_id, status, fingerprint)
            logger.info(
                "[bot_diagnostics] bot_id=%d status=%s 발령 (reason=%s, fp=%s)",
                bot_id, status, reason, fingerprint,
            )

    except json.JSONDecodeError as e:
        logger.error("[bot_diagnostics] Claude 응답 파싱 실패: %s | raw=%s", e, raw[:200])
    except Exception as e:
        logger.error("[bot_diagnostics] 진단 태스크 오류: %s", e, exc_info=True)
    finally:
        db.close()
