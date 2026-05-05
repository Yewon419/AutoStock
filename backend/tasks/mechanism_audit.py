"""매커니즘 감사 — 봇이 정의된 룰대로 동작했는지 검증 (수익성 X, invariant 검사).

5/6~5/8 첫 거래일 3일간 5분마다 발사. 정규장(KST 09:00~15:30)만 의미 있는 검사.
위반 발생 시에만 autostock:alerts에 push. 디덥으로 저소음 유지.

Phase 1 룰 카탈로그 (12개):
- A1: run_all_bots beat 발사 (5분 ±90s)
- A2: 봇별 cycle_lock 잔존 (swing TTL≤30s / scalping TTL≤10s)
- A3: price_stream heartbeat ≤180s
- B1: scalping 신호 카운터 폭주 + BUY 누락
- B2: SUBMITTED + order_number NULL이 1분 이상
- C2: max_positions 초과
- C4: scalping 15:10 이후 포지션 잔존 (검사창 15:15~15:30)
- D1: CB 평가 1분 초과 stale
- D2: CB 임계 전이 정확성 (-7/-8.5/-10%)
- D3: cb:new_buy_blocked 동안 BUY order INSERT
- E1: watchdog restart 증가 / escalated
- E2: celery/stream 큐 적체 ≥100

설계: 회의/13_매커니즘_감사_task_설계.md
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Literal

import redis
from celery import shared_task
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from models.trading import Order, Position, TradingBot

logger = logging.getLogger(__name__)

Severity = Literal["info", "warning", "critical"]

# ── 운영 시간 (KST) ────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
MARKET_OPEN_KST = time(9, 0)
MARKET_CLOSE_KST = time(15, 30)
SCALP_FORCE_CLOSE_KST = time(15, 10)
SCALP_AUDIT_WINDOW_START = time(15, 15)
SCALP_AUDIT_WINDOW_END = time(15, 30)

# ── 모니터링 대상 봇 ───────────────────────────────────────────────
SWING_BOT_IDS: tuple[int, ...] = (19, 20)
SCALPING_BOT_IDS: tuple[int, ...] = (21, 22)
ALL_MONITORED_BOT_IDS: tuple[int, ...] = SWING_BOT_IDS + SCALPING_BOT_IDS

# ── Redis 키 ──────────────────────────────────────────────────────
ALERTS_KEY = "autostock:alerts"
DEDUP_KEY_FMT = "autostock:audit:dedup:{rule_id}:{bot_id}"
DAILY_SET_FMT = "autostock:audit:violations:{date}"
DAILY_SET_TTL = 14 * 24 * 3600  # 14일

# Phase 1.5 후크 키
BEAT_LAST_FIRE_KEY_FMT = "autostock:beat_last_fire:{task}"

# 외부 서비스 키
HEARTBEAT_KEY = "autostock:price_stream_heartbeat"
CYCLE_LOCK_KEY_FMT = "autostock:bot_cycle_lock:{bot_id}"
CB_STATE_KEY = "autostock:cb:state"
CB_NEW_BUY_BLOCK_KEY = "autostock:cb:new_buy_blocked"
WATCHDOG_RESTART_KEY = "autostock:watchdog:restart_count"
WATCHDOG_ESCALATED_KEY = "autostock:watchdog:escalated"
AUDIT_LAST_SEEN_RESTART = "autostock:audit:last_seen:watchdog_restart"

# scalping 신호 카운터 (B1)
SIG_KEY_FMT = "rt:sig:{bot_id}:{ticker}"

# ── 임계값 ──────────────────────────────────────────────────────
A1_TASK_NAME = "tasks.bot_engine.run_all_bots"
A1_TOLERANCE_SECONDS = 5 * 60 + 90  # 5분 ±90s
A2_SWING_LOCK_TTL_THRESHOLD = 30  # 6분 락 중 30s 미만 = 5.5분 점유
A2_SCALPING_LOCK_TTL_THRESHOLD = 10  # 2분 락 중 10s 미만 = 1m50s 점유
A3_HEARTBEAT_STALE_SECONDS = 180
B1_SIG_OVERFLOW_MULTIPLIER = 5  # confirm_bars * 5 이상이면 폭주 의심
B1_RECENT_BUY_WINDOW_MIN = 6
B2_SUBMITTED_GRACE_SECONDS = 60
D1_CB_STALE_SECONDS = 60
D2_THRESHOLD_WARN = -7.0
D2_THRESHOLD_PAUSE = -8.5
D2_THRESHOLD_HALT = -10.0
D3_BUY_LOOKBACK_MIN = 5
E2_QUEUE_BACKLOG_THRESHOLD = 100

# ── 디덥 쿨다운 ──────────────────────────────────────────────────
COOLDOWN_CRITICAL = 300   # 5분
COOLDOWN_WARNING = 1800   # 30분


@dataclass(frozen=True)
class Violation:
    rule_id: str
    category: str
    severity: Severity
    bot_id: int | None
    message: str
    evidence: dict[str, object]


# ── 공통 유틸 ────────────────────────────────────────────────────

def _kst_now(now_utc: datetime) -> datetime:
    return now_utc.astimezone(KST)


def _is_market_hours(now_utc: datetime) -> bool:
    kst = _kst_now(now_utc)
    if kst.weekday() >= 5:
        return False
    return MARKET_OPEN_KST <= kst.time() <= MARKET_CLOSE_KST


def _push_alert(r: redis.Redis, v: Violation) -> bool:
    """디덥 통과 시 alert push. push했으면 True."""
    bot_part = str(v.bot_id) if v.bot_id is not None else "global"
    dedup_key = DEDUP_KEY_FMT.format(rule_id=v.rule_id, bot_id=bot_part)
    cooldown = COOLDOWN_CRITICAL if v.severity == "critical" else COOLDOWN_WARNING
    if r.set(dedup_key, "1", ex=cooldown, nx=True) is None:
        return False
    payload = {
        "type": "AUDIT_VIOLATION",
        "rule_id": v.rule_id,
        "category": v.category,
        "severity": v.severity,
        "bot_id": v.bot_id,
        "message": v.message,
        "evidence": v.evidence,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    r.lpush(ALERTS_KEY, json.dumps(payload, ensure_ascii=False))
    r.ltrim(ALERTS_KEY, 0, 999)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    daily_key = DAILY_SET_FMT.format(date=today)
    r.sadd(daily_key, f"{v.rule_id}:{bot_part}")
    r.expire(daily_key, DAILY_SET_TTL)
    logger.warning("AUDIT_VIOLATION %s bot=%s sev=%s %s", v.rule_id, v.bot_id, v.severity, v.message)
    return True


# ── 룰 함수 ─────────────────────────────────────────────────────

def check_a1_run_bots_fire(r: redis.Redis, now_utc: datetime) -> list[Violation]:
    """A1: run_all_bots이 5분 ±90s 안에 발사됐는가 (정규장 시간만)."""
    if not _is_market_hours(now_utc):
        return []
    raw = r.get(BEAT_LAST_FIRE_KEY_FMT.format(task=A1_TASK_NAME))
    now_ts = int(now_utc.timestamp())
    if raw is None:
        return [Violation(
            "A1", "cycle", "warning", None,
            "run_all_bots beat_last_fire 키 없음 — 발사 기록 누락",
            {"task": A1_TASK_NAME},
        )]
    try:
        last_fire = int(raw)
    except (TypeError, ValueError):
        return [Violation(
            "A1", "cycle", "warning", None,
            f"beat_last_fire 값 파싱 실패: {raw!r}",
            {"raw": str(raw)},
        )]
    delta = now_ts - last_fire
    if delta > A1_TOLERANCE_SECONDS:
        return [Violation(
            "A1", "cycle", "warning", None,
            f"run_all_bots 발사 지연 {delta}s (임계 {A1_TOLERANCE_SECONDS}s)",
            {"last_fire_ts": last_fire, "delta_seconds": delta},
        )]
    return []


def check_a2_cycle_lock_stale(r: redis.Redis) -> list[Violation]:
    """A2: 봇별 cycle_lock TTL이 임계 이하로 떨어졌는데 잔존 — 사이클 hang 의심."""
    out: list[Violation] = []
    for bot_id in ALL_MONITORED_BOT_IDS:
        key = CYCLE_LOCK_KEY_FMT.format(bot_id=bot_id)
        ttl = r.ttl(key)
        if ttl is None or ttl < 0:
            # -1: 키는 있는데 TTL 없음 / -2: 키 없음 — 둘 다 정상 또는 비대상
            continue
        threshold = (
            A2_SCALPING_LOCK_TTL_THRESHOLD if bot_id in SCALPING_BOT_IDS
            else A2_SWING_LOCK_TTL_THRESHOLD
        )
        if ttl <= threshold:
            out.append(Violation(
                "A2", "cycle", "warning", bot_id,
                f"cycle_lock TTL {ttl}s ≤ 임계 {threshold}s — 사이클 hang 의심",
                {"ttl_seconds": ttl, "threshold_seconds": threshold},
            ))
    return out


def check_a3_stream_heartbeat(r: redis.Redis, now_utc: datetime) -> list[Violation]:
    """A3: price_stream heartbeat 180s+ stale (정규장 시간만)."""
    if not _is_market_hours(now_utc):
        return []
    raw = r.get(HEARTBEAT_KEY)
    if raw is None:
        return [Violation(
            "A3", "cycle", "critical", None,
            "price_stream_heartbeat 키 없음 — 스트림 미가동 추정",
            {},
        )]
    try:
        last_ts = int(raw)
    except (TypeError, ValueError):
        return [Violation(
            "A3", "cycle", "critical", None,
            f"heartbeat 값 파싱 실패: {raw!r}",
            {"raw": str(raw)},
        )]
    delta = int(now_utc.timestamp()) - last_ts
    if delta > A3_HEARTBEAT_STALE_SECONDS:
        return [Violation(
            "A3", "cycle", "critical", None,
            f"price_stream heartbeat {delta}s stale (임계 {A3_HEARTBEAT_STALE_SECONDS}s)",
            {"delta_seconds": delta, "last_ts": last_ts},
        )]
    return []


def check_b1_scalping_signal_overflow(
    r: redis.Redis, db: Session, now_utc: datetime
) -> list[Violation]:
    """B1: scalping 신호 카운터가 confirm_bars * 5 이상인데 BUY order 누락 — drop된 신호 의심.

    정상 흐름은 confirm_bars 도달 시 진입 직후 키 삭제. 카운터가 폭주 = 진입 차단(CB/한도/잔고)
    또는 _submit_and_track 실패. dedup 30m으로 false-positive 흡수.
    """
    if not _is_market_hours(now_utc):
        return []
    out: list[Violation] = []
    bots = db.query(TradingBot).filter(
        TradingBot.id.in_(SCALPING_BOT_IDS),
        TradingBot.status == "RUNNING",
    ).all()
    if not bots:
        return []
    window_start = now_utc - timedelta(minutes=B1_RECENT_BUY_WINDOW_MIN)
    for bot in bots:
        confirm_bars = int(bot.confirm_bars or 1)
        threshold = max(confirm_bars * B1_SIG_OVERFLOW_MULTIPLIER, confirm_bars + 5)
        tickers: list[str] = list(bot.tickers or [])
        if not tickers:
            continue
        keys = [SIG_KEY_FMT.format(bot_id=bot.id, ticker=t) for t in tickers]
        values = r.mget(keys)
        overflow: list[tuple[str, int]] = []
        for ticker, raw in zip(tickers, values):
            if raw is None:
                continue
            try:
                count = int(raw)
            except (TypeError, ValueError):
                continue
            if count >= threshold:
                overflow.append((ticker, count))
        if not overflow:
            continue
        recent_buy = {
            row.ticker for row in db.query(Order.ticker).filter(
                Order.bot_id == bot.id,
                Order.order_type == "BUY",
                Order.created_at >= window_start,
            ).all()
        }
        dropped = [(t, c) for t, c in overflow if t not in recent_buy]
        if dropped:
            out.append(Violation(
                "B1", "flow", "warning", bot.id,
                f"신호 카운터 폭주 {len(dropped)}건 (임계 {threshold}) — BUY order 누락",
                {
                    "dropped": [{"ticker": t, "count": c} for t, c in dropped],
                    "confirm_bars": confirm_bars,
                    "threshold": threshold,
                },
            ))
    return out


def check_b2_submitted_no_odno(db: Session, now_utc: datetime) -> list[Violation]:
    """B2: SUBMITTED 상태에 order_number NULL인 행이 1분 이상 머무름."""
    cutoff = now_utc - timedelta(seconds=B2_SUBMITTED_GRACE_SECONDS)
    rows = db.query(Order).filter(
        Order.bot_id.in_(ALL_MONITORED_BOT_IDS),
        Order.status == "SUBMITTED",
        Order.order_number.is_(None),
        Order.created_at < cutoff,
    ).all()
    out: list[Violation] = []
    for row in rows:
        out.append(Violation(
            "B2", "flow", "warning", row.bot_id,
            f"order_id={row.id} {row.ticker} {row.order_type} SUBMITTED + ODNO NULL "
            f"({(now_utc - row.created_at.astimezone(timezone.utc)).total_seconds():.0f}s)",
            {
                "order_id": row.id,
                "ticker": row.ticker,
                "order_type": row.order_type,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            },
        ))
    return out


def check_c2_max_positions(db: Session) -> list[Violation]:
    """C2: max_positions 한도 초과."""
    bots = db.query(TradingBot).filter(
        TradingBot.id.in_(ALL_MONITORED_BOT_IDS),
        TradingBot.status == "RUNNING",
    ).all()
    out: list[Violation] = []
    for bot in bots:
        limit = int(bot.max_positions or 0)
        if limit <= 0:
            continue
        positions = db.query(Position).filter(Position.bot_id == bot.id).all()
        actual = len(positions)
        if actual > limit:
            out.append(Violation(
                "C2", "risk", "critical", bot.id,
                f"max_positions={limit} 초과: 현재 {actual}건",
                {"positions": [p.ticker for p in positions], "limit": limit, "actual": actual},
            ))
    return out


def check_c4_scalping_intraday_close(db: Session, now_utc: datetime) -> list[Violation]:
    """C4: 스캘핑봇 15:10 강제청산 후 포지션 잔존 (15:15~15:30 KST 검사창)."""
    kst = _kst_now(now_utc)
    if kst.weekday() >= 5:
        return []
    if not (SCALP_AUDIT_WINDOW_START <= kst.time() <= SCALP_AUDIT_WINDOW_END):
        return []
    out: list[Violation] = []
    for bot_id in SCALPING_BOT_IDS:
        positions = db.query(Position).filter(Position.bot_id == bot_id).all()
        if positions:
            out.append(Violation(
                "C4", "risk", "critical", bot_id,
                f"15:10 강제청산 후에도 포지션 {len(positions)}건 잔존",
                {"positions": [p.ticker for p in positions]},
            ))
    return out


def check_d1_cb_stale(r: redis.Redis, now_utc: datetime) -> list[Violation]:
    """D1: cb:state.evaluated_at 1분 초과 stale (정규장 시간만)."""
    if not _is_market_hours(now_utc):
        return []
    raw = r.get(CB_STATE_KEY)
    if raw is None:
        return [Violation(
            "D1", "cb", "warning", None,
            "autostock:cb:state 키 없음 — Circuit Breaker 미가동 의심",
            {},
        )]
    try:
        state = json.loads(raw)
        evaluated_at = datetime.fromisoformat(str(state["evaluated_at"]))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        return [Violation(
            "D1", "cb", "warning", None,
            f"cb:state 파싱 실패: {e!r}",
            {"raw": str(raw)[:200]},
        )]
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
    delta = (now_utc - evaluated_at).total_seconds()
    if delta > D1_CB_STALE_SECONDS:
        return [Violation(
            "D1", "cb", "warning", None,
            f"CB 평가 {delta:.0f}s stale (임계 {D1_CB_STALE_SECONDS}s)",
            {"evaluated_at": evaluated_at.isoformat(), "delta_seconds": delta},
        )]
    return []


def check_d2_cb_threshold_consistency(r: redis.Redis, now_utc: datetime) -> list[Violation]:
    """D2: cb:state.level이 portfolio_pnl_pct와 일치하는가."""
    if not _is_market_hours(now_utc):
        return []
    raw = r.get(CB_STATE_KEY)
    if raw is None:
        return []  # D1이 처리
    try:
        state = json.loads(raw)
        level = str(state["level"])
        pnl_pct = float(state["portfolio_pnl_pct"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []  # D1이 처리
    expected: str
    if pnl_pct <= D2_THRESHOLD_HALT:
        expected = "HALT"
    elif pnl_pct <= D2_THRESHOLD_PAUSE:
        expected = "PAUSE"
    elif pnl_pct <= D2_THRESHOLD_WARN:
        expected = "WARN"
    else:
        expected = "OK"
    if level != expected:
        return [Violation(
            "D2", "cb", "critical", None,
            f"CB level 불일치: pnl={pnl_pct:.2f}% → 기대 {expected}, 실제 {level}",
            {"level": level, "expected": expected, "pnl_pct": pnl_pct},
        )]
    return []


def check_d3_buy_under_block(
    r: redis.Redis, db: Session, now_utc: datetime
) -> list[Violation]:
    """D3: cb:new_buy_blocked 키가 존재하는데 직전 5분에 BUY order INSERT."""
    if r.get(CB_NEW_BUY_BLOCK_KEY) is None:
        return []
    cutoff = now_utc - timedelta(minutes=D3_BUY_LOOKBACK_MIN)
    rows = db.query(Order).filter(
        Order.bot_id.in_(ALL_MONITORED_BOT_IDS),
        Order.order_type == "BUY",
        Order.created_at >= cutoff,
    ).all()
    if not rows:
        return []
    out: list[Violation] = []
    by_bot: dict[int, list[Order]] = {}
    for row in rows:
        by_bot.setdefault(row.bot_id, []).append(row)
    for bot_id, orders in by_bot.items():
        out.append(Violation(
            "D3", "cb", "critical", bot_id,
            f"new_buy_blocked 중 BUY order {len(orders)}건 INSERT — 차단 우회",
            {
                "orders": [
                    {
                        "id": o.id, "ticker": o.ticker, "qty": o.quantity,
                        "status": o.status,
                        "created_at": o.created_at.isoformat() if o.created_at else None,
                    }
                    for o in orders
                ],
            },
        ))
    return out


def check_e1_watchdog(r: redis.Redis) -> list[Violation]:
    """E1: watchdog restart_count 증가 또는 escalated 발생."""
    out: list[Violation] = []
    if r.get(WATCHDOG_ESCALATED_KEY) is not None:
        out.append(Violation(
            "E1", "infra", "critical", None,
            "watchdog escalated 키 활성 — 30분 내 3회 초과 재기동",
            {},
        ))
    raw = r.get(WATCHDOG_RESTART_KEY)
    if raw is None:
        return out
    try:
        current = int(raw)
    except (TypeError, ValueError):
        return out
    last_seen_raw = r.get(AUDIT_LAST_SEEN_RESTART)
    last_seen = 0
    if last_seen_raw is not None:
        try:
            last_seen = int(last_seen_raw)
        except (TypeError, ValueError):
            last_seen = 0
    if current > last_seen:
        out.append(Violation(
            "E1", "infra", "warning", None,
            f"watchdog restart 증가 {last_seen} → {current}",
            {"prev": last_seen, "current": current},
        ))
    # 다음 검사를 위해 갱신 (alert는 위에서 이미 dedup으로 보호됨)
    try:
        r.set(AUDIT_LAST_SEEN_RESTART, str(current))
    except Exception as e:
        logger.warning("[mechanism_audit] last_seen 갱신 실패: %r", e)
    return out


def check_e2_queue_backlog(r: redis.Redis) -> list[Violation]:
    """E2: celery / stream 큐 적체 ≥100."""
    out: list[Violation] = []
    for queue_name in ("celery", "stream"):
        try:
            backlog = int(r.llen(queue_name))
        except Exception as e:
            logger.warning("[mechanism_audit] LLEN %s 실패: %r", queue_name, e)
            continue
        if backlog >= E2_QUEUE_BACKLOG_THRESHOLD:
            out.append(Violation(
                "E2", "infra", "warning", None,
                f"celery 큐 '{queue_name}' 적체 {backlog}건 (임계 {E2_QUEUE_BACKLOG_THRESHOLD})",
                {"queue": queue_name, "backlog": backlog},
            ))
    return out


# ── Celery task ─────────────────────────────────────────────────

@shared_task(name="tasks.mechanism_audit.run_audit")
def run_audit() -> dict[str, int]:
    """매 5분 발사 (정규장 KST). 룰 12개 실행 후 위반은 alert + SET 누적."""
    now_utc = datetime.now(timezone.utc)
    r: redis.Redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    db: Session = SessionLocal()
    pushed = 0
    suppressed = 0
    violations: list[Violation] = []
    try:
        violations.extend(check_a1_run_bots_fire(r, now_utc))
        violations.extend(check_a2_cycle_lock_stale(r))
        violations.extend(check_a3_stream_heartbeat(r, now_utc))
        violations.extend(check_b1_scalping_signal_overflow(r, db, now_utc))
        violations.extend(check_b2_submitted_no_odno(db, now_utc))
        violations.extend(check_c2_max_positions(db))
        violations.extend(check_c4_scalping_intraday_close(db, now_utc))
        violations.extend(check_d1_cb_stale(r, now_utc))
        violations.extend(check_d2_cb_threshold_consistency(r, now_utc))
        violations.extend(check_d3_buy_under_block(r, db, now_utc))
        violations.extend(check_e1_watchdog(r))
        violations.extend(check_e2_queue_backlog(r))
        for v in violations:
            if _push_alert(r, v):
                pushed += 1
            else:
                suppressed += 1
    except Exception as e:
        logger.error("[mechanism_audit] run_audit 예외: %r", e, exc_info=True)
        raise
    finally:
        db.close()
    logger.info(
        "[mechanism_audit] checked rules=12 violations=%d pushed=%d suppressed=%d",
        len(violations), pushed, suppressed,
    )
    return {"checked_rules": 12, "violations": len(violations),
            "pushed": pushed, "suppressed": suppressed}
