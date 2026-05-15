# 매커니즘 감사 Task 설계 (Mechanism Audit)

> 작성일: 2026-05-05
> 목적: 5/6(수)~5/8(금) 본 첫 거래일 3일간 봇이 **정의된 룰대로 동작했는지** 자동 감사. 수익성이 아닌 매커니즘 무결성 검증.
> 실행: 이 문서로 새 세션에서 코드 작성 시작 가능 (자체완결).

---

## 0. 새 세션 부트 컨텍스트

이 섹션만 읽으면 코드 작성 진입 가능.

### 환경
- 프로젝트: `C:\Users\windg\Desktop\PROJECT\AutoStock`
- DB: PostgreSQL 5433 (컨테이너 `autostock-postgres`, user/db: `autostock` / pass: `autostock123`)
- Redis: 6379 (`autostock-redis`)
- Backend API: http://localhost:8001 (`autostock-backend`)
- Celery worker: `autostock-celery-worker` (concurrency=4, Q=celery)
- Celery stream worker: `autostock-celery-stream-worker` (concurrency=1, Q=stream)
- Celery beat: `autostock-celery-beat` — 이 task가 주기 발사
- Frontend: `npm run dev -- --host --port 3001` (Docker 미사용)

### 모니터링 대상 봇 (5/4 15:10 KST 처음 RUNNING 전환)
| bot_id | 이름 | 타입 | 모드 | strategy_id | 핵심 risk_params |
|---|---|---|---|---|---|
| 19 | 포폴_눌림목 | swing | mock | 47 | SL 3.5 / TP 8.0 / MDD 10 / pos **20%** / max_pos **5** / max_daily 10 / candle 5 *(2026-05-15 비중↑ — 포폴 흑자축, [개발일지 5/15](개발일지.md) 참조)* |
| 20 | 포폴_변동성압축 | swing | mock | 48 | SL **5.0** / TP **12.0** / MDD **12** / pos 15% / max_pos 4 / max_daily 10 / candle 5 *(2026-05-15 보유기간 완화 — 회전과다 보정, [개발일지 5/15](개발일지.md) 참조)* |
| 21 | 포폴_과매도단타 | scalping | mock | 49 | SL 1.5 / TP 3.0 / MDD 5 / pos 10% / max_pos 3 / max_daily 30 / candle 3 / **intraday_close 15:10** |
| 22 | 포폴_돌파단타 | scalping | mock | 50 | SL 1.5 / TP 3.0 / MDD 5 / pos 10% / max_pos 2 / max_daily 30 / candle 3 / **intraday_close 15:10** |
| 16 | 실전투자 테스트봇 | swing | real | — | STOPPED (모니터링 제외) |

### 핵심 코드 진입점
- `backend/tasks/bot_engine.py` — `run_all_bots`, 봇별 사이클, 포지션 사이징
- `backend/tasks/scalping_engine.py` — 분봉 단타 사이클
- `backend/tasks/circuit_breaker_task.py` — 매분 평가 (`autostock:cb:state`)
- `backend/tasks/kis_price_stream.py` — `start_price_stream`, `watchdog_price_stream`
- `backend/tasks/celery_app.py` — beat schedule 등록 위치
- `backend/broker/kis_broker.py` — KIS API 호출 (paper TR `VTTCxxxx`)
- `backend/services/trading_service.py` — bot_type 프로필 (SCALPING_PROFILE / SWING_PROFILE)

### 핵심 Redis 키
| 키 | TTL | 의미 |
|---|---|---|
| `rt:price:{ticker}` | 60s | 실시간 시세 |
| `rt:peak:{bot_id}:{ticker}` | — | trailing 추적 피크 |
| `rt:sig:{bot_id}:{ticker}` | — | 신호 마커 |
| `autostock:price_stream_heartbeat` | 120s | KIS 스트림 헬스 |
| `autostock:bot_cycle_lock:{bot_id}` | 6분 | 사이클 중복 락 |
| `autostock:cb:state` | — | CB 평가 결과 JSON |
| `autostock:cb:new_buy_blocked` | — | CB 신규매수 차단 플래그 |
| `autostock:cb:last_alert:{level}` | 60m | CB 알림 쿨다운 |
| `autostock:diag:last:{bot_id}` | 7d | 진단 fingerprint 디덥 |
| `autostock:watchdog:restart_count` | — | 워치독 재기동 카운트 |
| `autostock:watchdog:escalated` | — | 에스컬레이션 발령 여부 |
| `autostock:alerts` (LIST) | — | 알림 push 채널 (frontend 노출) |
| `autostock:ml_scores` | — | ML 점수 |

### DB 테이블
- `trading_bots` — 컬럼: id, name, status, strategy_id, account_id, stop_loss_pct, take_profit_pct, max_drawdown_pct, position_size_pct, max_positions, max_daily_trades, intraday_close, intraday_close_time, trailing_stop_pct, confirm_bars, candle_interval, mode, cash, initial_cash, bot_type, tickers(json), trading_start_time, trading_end_time
- `positions` — UNIQUE(bot_id, ticker), 컬럼: bot_id, ticker, quantity, avg_price, trailing_peak, updated_at
- `orders` — 컬럼: bot_id, ticker, order_type, quantity, price, status, order_number, created_at. 상태 머신: SUBMITTED → PENDING/PARTIAL/FILLED/REJECTED/CANCELLED/TIMEOUT
- `executions` — 컬럼: bot_id, order_id, execution_type, executed_at, profit_loss
- `strategies` — pattern, risk_params(JSON)
- `accounts` — 잔고 컬럼 없음 (KIS API 실시간 조회)

### 운영 시간 (KST)
- 정규장: 09:00~15:30
- 동시호가: 08:30~09:00 (전), 15:20~15:30 (후)
- 스캘핑 강제청산: 15:10
- Celery beat 시간대는 **UTC** (한국과 +9h 차이) — 정규장 09:00 KST = 00:00 UTC

---

## 1. 목적과 비기능 요건

### 목적
- 5/6 09:00 KST 첫 거래 사이클부터 5/8 15:30 KST까지 3거래일간, 시스템이 **설계 문서대로 동작했는가** 자동 검증.
- 위반 발견 시 즉각 alert + 일일 롤업으로 누적 가시화.
- Phase 1(수익성 readiness) 시작 전 인프라 신뢰도 확보.

### 비기능 요건
- **자율성**: Claude 세션·터미널과 무관. Celery beat이 발사. PC만 켜져 있으면 됨.
- **저소음**: 위반 0건이면 silent. 위반 시에만 alert. 일일 롤업은 매일 1회만.
- **무파괴**: 감사 task는 read-only. DB·Redis 상태 변경 금지 (예외: 자기 결과 기록).
- **저비용**: API 호출 없음, DB read만. 5분 주기여도 부담 없음.

---

## 2. 검사 룰 카탈로그 (확정본)

| ID | 카테고리 | 룰 | 검사 방법 | 주기 | severity |
|---|---|---|---|---|---|
| **A1** | 사이클 | `run_all_bots`이 09:00~15:30 KST 매 5분 ±60s 안에 발사됐는가 | celery beat 로그 또는 `autostock:beat_last_fire:run_all_bots` 키(없으면 신설) 비교 | 5min | warning |
| **A2** | 사이클 | 봇별 사이클 락 stale 여부 (`autostock:bot_cycle_lock:{bot_id}` TTL 만료 직전인데 키 잔존) | Redis TTL 검사 | 5min | warning |
| **A3** | 사이클 | KisPriceStream heartbeat ≤180s 유지 | `autostock:price_stream_heartbeat` 마지막 갱신 시각 | 5min | critical (정규장 시간 한정) |
| **B1** | 흐름 | signal 발생 후 5분 내 order INSERT 여부 (drop된 신호) | `rt:sig:{bot_id}:{ticker}` 발생 시각 vs `orders.created_at` 매칭 | 5min | warning |
| **B2** | 흐름 | order INSERT 후 ODNO 누락, status가 SUBMITTED에 1분 이상 머무름 | orders.status, order_number, created_at | 5min | warning |
| **B3** | 흐름 | Position 있는데 매수 Order 흔적 0개 / FILLED Order 있는데 Position 미반영 | JOIN orders·positions·executions | 15min | critical |
| **B4** | 흐름 | PARTIAL Order이 reconcile 큐에 등록 안 됨 | celery 큐에 `reconcile_partial` task 잔존 여부 | 5min | warning |
| **B5** | 흐름 | Order.quantity vs Execution 합계 불일치 | SUM(executions.quantity) == orders.quantity | 15min | critical |
| **C1** | 리스크 | 포지션 사이즈가 정의값 ±2%p 초과 | (avg_price * quantity) / bot.initial_cash * 100 vs position_size_pct | 15min | warning |
| **C2** | 리스크 | max_positions 한도 초과 | COUNT(positions WHERE bot_id=X) > bot.max_positions | 5min | critical |
| **C3** | 리스크 | SL/TP 트리거 정합성 (도달했는데 청산 안 됨, 또는 임계 전 청산) | rt:price 대비 손익률 vs stop_loss_pct/take_profit_pct vs 청산 이벤트 | 15min | critical |
| **C4** | 리스크 | 스캘핑봇(21,22) 15:10 이후에 보유 포지션 잔존 | 15:15 KST 기준 positions WHERE bot_id IN (21,22) | 1회/일 (15:15 KST) | critical |
| **C5** | 리스크 | trailing_stop 추적·발동 정합성 | rt:peak 갱신 vs 청산 시점 손익률 | 15min | warning |
| **C6** | 리스크 | max_daily_trades 한도 초과 | 당일 executions 카운트 vs bot.max_daily_trades | 5min | warning |
| **D1** | CB | 매분 평가 누락 (`cb:state.evaluated_at` 가 1분 초과 stale) | Redis 키 시각 | 5min | warning |
| **D2** | CB | 임계 전이 정확성 (-7% WARN / -8.5% PAUSE / -10% HALT) | cb:state.portfolio_pnl_pct vs level | 5min | critical |
| **D3** | CB | PAUSE/HALT 중 신규 매수 발생 | cb:new_buy_blocked=true인 동안 BUY order INSERT 여부 | 5min | critical |
| **D4** | CB | 동일 level 알림 쿨다운(60m) 중복 발령 | `autostock:cb:last_alert:{level}` TTL vs alert 로그 | 15min | warning |
| **E1** | 인프라 | Watchdog 재기동 카운트 증가 / escalate 발생 | `autostock:watchdog:restart_count`, `escalated` | 5min | warning (escalate는 critical) |
| **E2** | 인프라 | celery 큐 적체 (celery / stream backlog ≥ 100) | `LLEN celery`, `LLEN stream` | 5min | warning |
| **E3** | 인프라 | KIS API 에러율 (1분당 ≥5회) | `autostock:kis_error_count:{minute_bucket}` 키(없으면 신설) | 5min | warning |
| **E4** | 인프라 | Position UNIQUE IntegrityError | celery worker 로그 grep `IntegrityError.*positions` (or 신설 카운터 키) | 15min | critical |
| **F1** | 진단 | fingerprint 동일한데 쿨다운 무시 발령 | `autostock:diag:last:{bot_id}` JSON에서 fingerprint·시각 vs 새 알림 | 15min | warning |

### 신설이 필요한 Redis 키
구현 단계에서 **소스 코드를 직접 수정해야** 검사 가능한 항목 (감사 task 단독으로는 검사 불가):
- `autostock:beat_last_fire:run_all_bots` (A1) — beat schedule 후크 또는 task 시작 시 SET
- `autostock:kis_error_count:{minute_bucket}` (E3) — kis_broker.py 예외 처리에서 INCR
- `autostock:integrity_error_count` (E4) — 봇 엔진 IntegrityError 캐치에서 INCR

이 3개는 **Phase 1.5 (코드 후크 삽입)** 로 분리. Phase 1 본 코드 작성 시 함께.

---

## 3. 출력 설계

### 3.1 즉시 알림
- 위반 발생 시 `autostock:alerts` LIST에 LPUSH (기존 알림 파이프라인 재사용)
- 페이로드:
```json
{
  "type": "AUDIT_VIOLATION",
  "rule_id": "C2",
  "category": "risk",
  "severity": "critical",
  "bot_id": 21,
  "message": "max_positions=3 초과: 현재 4건",
  "evidence": {"positions": ["005930", "035420", "000660", "012450"]},
  "ts": "2026-05-06T01:23:45+00:00"
}
```
- 디덥: 같은 `(rule_id, bot_id)` 30분 쿨다운 (`autostock:audit:dedup:{rule_id}:{bot_id}` TTL 30m). 디덥 무시 옵션 = critical은 5분 쿨다운만.

### 3.2 일일 누적 SET
- `autostock:audit:violations:{YYYY-MM-DD}` SET — 위반 fingerprint 누적
- TTL 14d (주간 리포트 후 폐기)

### 3.3 일일 롤업 리포트 (Phase 3)
- 매일 15:35 KST에 `audit_daily_summary` task 실행
- 결과를 DB `audit_daily_reports` 테이블에 INSERT
- 컬럼: report_date, cycle_count, signal_count, order_count, fill_count, violations_by_category(JSON), violations_by_severity(JSON), notes(TEXT)
- frontend `AuditView.vue`에서 조회 (Phase 4)

### 3.4 주간 롤업 (Phase 3)
- 매주 일 22:00 KST에 5거래일 통계 + Phase 1 readiness 게이트 자동 평가
- 임계값(메모리): 거래 30/봇, 누적 수익 >0%, Sharpe ≥0.8, MDD <10%, KOSPI 초과, backtest-live gap <5%p, watchdog escalate=0, active critical=0
- 결과는 `autostock:alerts` push 1건 (요약만)

---

## 4. Phase 분할

### Phase 1 — 핵심 룰 (5/5 밤 / 5/6 09:00 전 필수)
- [ ] `backend/tasks/mechanism_audit.py` 신설
- [ ] 룰 A1, A2, A3, B1, B2, C2, C4, D1, D2, D3, E1, E2 구현 (12개 — 가장 영향 큰 것 우선)
- [ ] `autostock:alerts` push + dedup 키 처리
- [ ] `backend/tasks/celery_app.py` beat 등록: `audit-mechanisms` cron `*/5 * * * *` (UTC, 정규장 시간만)
- [ ] 룰별 단위 함수 분리, pure function 위주

**파일 수**: 2 (신규 1 + 수정 1)
**의존**: Phase 1.5 (코드 후크) 없이 동작 가능한 룰만 포함

### Phase 1.5 — 검사용 후크 삽입 (Phase 1과 같은 PR)
- [ ] `backend/tasks/celery_app.py` — beat task 시작 시 `autostock:beat_last_fire:{task}` SET (A1용)
- [ ] `backend/broker/kis_broker.py` — 예외 처리에서 `autostock:kis_error_count:{minute_bucket}` INCR (E3용)
- [ ] `backend/services/trading_service.py` 또는 `_upsert_position` — IntegrityError 캐치에서 `autostock:integrity_error_count` INCR (E4용)

**파일 수**: 3
**주의**: 후크는 모두 try/except로 감싸 실패 시 본 거래 흐름에 영향 0

### Phase 2 — 보조 룰
- [ ] mechanism_audit.py 확장: B3, B4, B5, C1, C3, C5, C6, D4, F1 (9개)
- [ ] E3, E4 — Phase 1.5 후크 키를 참조해서 검사
- [ ] **파일 수**: 1 (수정만)

### Phase 3 — 일일·주간 롤업
- [ ] `backend/models/audit_report.py` — `AuditDailyReport` ORM 모델
- [ ] `backend/migrations/` 또는 SQL 파일로 테이블 생성
- [ ] mechanism_audit.py에 `audit_daily_summary` task 추가
- [ ] beat 등록: cron `35 6 * * 1-5` (15:35 KST = 06:35 UTC, 평일)
- [ ] 주간 롤업 task: cron `0 13 * * 0` (일 22:00 KST = 13:00 UTC)

**파일 수**: 3~4

### Phase 4 — UI (선택)
- [ ] `backend/api/audit.py` — GET /audit/daily, /audit/weekly
- [ ] `frontend/src/views/AuditView.vue` — 일/주간 위반 리스트, 카테고리별 차트
- [ ] router 등록

**파일 수**: 3

---

## 5. 코드 스켈레톤 (Phase 1 진입용)

```python
# backend/tasks/mechanism_audit.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timezone, timedelta
from typing import Literal
import json
import logging

import redis
from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.config import settings
from models.trading_bot import TradingBot
from models.position import Position
from models.order import Order

logger = logging.getLogger(__name__)

Severity = Literal["info", "warning", "critical"]
KST = timezone(timedelta(hours=9))
MARKET_OPEN_KST = time(9, 0)
MARKET_CLOSE_KST = time(15, 30)
SCALP_FORCE_CLOSE_KST = time(15, 10)


@dataclass(frozen=True)
class Violation:
    rule_id: str
    category: str
    severity: Severity
    bot_id: int | None
    message: str
    evidence: dict[str, object]


def _is_market_hours(now_utc: datetime) -> bool:
    kst = now_utc.astimezone(KST)
    if kst.weekday() >= 5:
        return False
    return MARKET_OPEN_KST <= kst.time() <= MARKET_CLOSE_KST


def _push_alert(r: redis.Redis, v: Violation) -> None:
    dedup_key = f"autostock:audit:dedup:{v.rule_id}:{v.bot_id or 'global'}"
    cooldown = 300 if v.severity == "critical" else 1800
    if r.set(dedup_key, "1", ex=cooldown, nx=True) is None:
        return
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
    r.lpush("autostock:alerts", json.dumps(payload))
    r.ltrim("autostock:alerts", 0, 999)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    r.sadd(f"autostock:audit:violations:{today}", f"{v.rule_id}:{v.bot_id or 'global'}")
    r.expire(f"autostock:audit:violations:{today}", 14 * 24 * 3600)
    logger.warning("AUDIT_VIOLATION %s bot=%s %s", v.rule_id, v.bot_id, v.message)


# ----- 룰 함수 (각각 list[Violation] 반환) -----

def check_a3_stream_heartbeat(r: redis.Redis, now_utc: datetime) -> list[Violation]:
    """A3: KisPriceStream heartbeat ≤180s 유지 (정규장 시간만)."""
    if not _is_market_hours(now_utc):
        return []
    raw = r.get("autostock:price_stream_heartbeat")
    if raw is None:
        return [Violation("A3", "cycle", "critical", None,
                          "price_stream_heartbeat 키 없음 (스트림 미가동 추정)",
                          {})]
    # 키가 단순 timestamp string인지 JSON인지 코드 확인 후 파싱 — TODO
    # ...
    return []


def check_c2_max_positions(db: Session) -> list[Violation]:
    """C2: max_positions 한도 초과."""
    bots = db.query(TradingBot).filter(
        TradingBot.id.in_([19, 20, 21, 22]),
        TradingBot.status == "RUNNING",
    ).all()
    out: list[Violation] = []
    for bot in bots:
        limit = bot.max_positions or 0
        if limit <= 0:
            continue
        actual = db.query(Position).filter(Position.bot_id == bot.id).count()
        if actual > limit:
            tickers = [p.ticker for p in db.query(Position).filter(Position.bot_id == bot.id).all()]
            out.append(Violation("C2", "risk", "critical", bot.id,
                                 f"max_positions={limit} 초과: 현재 {actual}건",
                                 {"positions": tickers, "limit": limit}))
    return out


def check_c4_scalping_intraday_close(db: Session, now_utc: datetime) -> list[Violation]:
    """C4: 스캘핑봇 15:10 이후 보유 포지션 잔존 (15:15 KST 한정 검사)."""
    kst = now_utc.astimezone(KST)
    if kst.weekday() >= 5:
        return []
    if not (time(15, 15) <= kst.time() <= time(15, 30)):
        return []
    out: list[Violation] = []
    for bot_id in (21, 22):
        positions = db.query(Position).filter(Position.bot_id == bot_id).all()
        if positions:
            out.append(Violation("C4", "risk", "critical", bot_id,
                                 f"15:10 강제청산 후에도 포지션 {len(positions)}건 잔존",
                                 {"positions": [p.ticker for p in positions]}))
    return out


# ... 나머지 룰 함수 (A1, A2, B1, B2, D1, D2, D3, E1, E2)


@shared_task(name="tasks.mechanism_audit.run_audit")
def run_audit() -> dict[str, int]:
    """매 5분 발사. 룰 12개 실행, 위반은 alert + SET 누적."""
    now_utc = datetime.now(timezone.utc)
    r = redis.from_url(settings.REDIS_URL)
    db: Session = SessionLocal()
    try:
        all_violations: list[Violation] = []
        all_violations.extend(check_a3_stream_heartbeat(r, now_utc))
        all_violations.extend(check_c2_max_positions(db))
        all_violations.extend(check_c4_scalping_intraday_close(db, now_utc))
        # ... 나머지
        for v in all_violations:
            _push_alert(r, v)
        return {"checked_rules": 12, "violations": len(all_violations)}
    finally:
        db.close()
```

### celery_app.py 등록
```python
# beat_schedule에 추가
"audit-mechanisms": {
    "task": "tasks.mechanism_audit.run_audit",
    # 정규장 시간만 (UTC): 평일 00:00~06:30 매 5분
    "schedule": crontab(minute="*/5", hour="0-6", day_of_week="1-5"),
},
```

---

## 6. 검증 시나리오 (5/6 09:00 KST 첫 거래일)

### 정상 케이스
- 09:00 첫 사이클 발사 → A1 통과 (autostock:beat_last_fire 갱신 확인)
- 어떤 봇도 매수 안 함 → C2/C3/C5 통과 (포지션 0개)
- 15:30 마감까지 알림 0건이면 → 매커니즘 안정 GO

### 의도적 위반 시뮬 (Phase 1 완료 후 데모)
- bot_21에 fake position 5건 INSERT → 다음 사이클에 C2 critical alert 발생 확인 → 롤백
- price_stream_heartbeat 키 DEL → A3 critical 발생 확인 → watchdog 자동 복구 관찰

### 실패 케이스 (실제 발생 시)
- alert에서 즉시 식별 → 일일 롤업에서 카테고리별 카운트 → 주간 롤업에서 패턴 식별

---

## 7. 새 세션 진입 프롬프트 (복붙용)

```
AutoStock 매커니즘 감사 task Phase 1 구현하자. 설계 문서:
C:\Users\windg\Desktop\PROJECT\AutoStock\회의\13_매커니즘_감사_task_설계.md

이 문서의 §0(부트 컨텍스트), §2(룰 카탈로그), §4(Phase 분할), §5(스켈레톤)
를 읽고 Phase 1 + Phase 1.5 코드 작성 시작. 작성 후 docker compose
restart celery-worker celery-beat로 반영하고, 컨테이너 부팅 로그에서
'audit-mechanisms' beat 등록 확인까지 진행.

Phase 2~4는 별도 작업이니 이번엔 건드리지 마.
```

---

## 8. 미해결·확인 필요

- [ ] `autostock:price_stream_heartbeat` 값 형식 (단순 timestamp str / JSON?) — 코드 확인 후 A3 파서 작성
- [ ] `autostock:bot_cycle_lock:{bot_id}` 키가 실제로 존재하는지 (감사 코드 확인 docs vs 실 운영) — A2 룰 적용 여부 결정
- [ ] `bot_engine.run_all_bots`이 거래 시간 외에도 발사되는가 (5분 cron이 24/7?) → A1 임계 시간대 한정 필요
- [ ] `paper` 모드도 실제 KIS 모의 API에 주문이 가서 ODNO 오는가 (B2 검사 의미가 있는가) — KIS 모의 응답 형식 확인

이 4개는 Phase 1 작성 시 코드 확인하면서 해결.
