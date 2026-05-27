import logging
import time as _time

import redis as _redis_sync
from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, worker_ready
from core.config import settings

_logger = logging.getLogger(__name__)
_BEAT_LAST_FIRE_KEY_FMT = "autostock:beat_last_fire:{task}"
_BEAT_LAST_FIRE_TTL = 3600  # 1h — 매커니즘 감사가 정규장 5분 주기로 충분히 읽을 수 있는 길이

celery_app = Celery(
    "autostock",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.collect", "tasks.indicators", "tasks.backtest",
        "tasks.bot_engine", "tasks.scanner", "tasks.ai_tasks",
        "tasks.kis_price_stream",
        "tasks.intraday_collector", "tasks.scalping_engine",
        "tasks.bot_diagnostics",
        "tasks.circuit_breaker_task",
        "tasks.mechanism_audit",
        "tasks.bot_tuning",
        "tasks.knowledge_ingestion",
    ],
)

celery_app.conf.update(
    timezone="Asia/Seoul",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # 기본 큐: 'celery' (분 단위 cron, 짧은 작업). long-running은 'stream'으로 분리.
    task_default_queue="celery",
)

# 큐 라우팅 — long-running task는 별도 worker(autostock-celery-stream-worker)로 격리.
# 기존 celery-worker(concurrency 다수)는 'celery' 큐만 처리하므로 분 단위 task 적체 방지.
# watchdog_price_stream도 'stream' 큐로 격리: default 큐 backlog 폭증 시에도 스트림 감시 보장.
celery_app.conf.task_routes = {
    "tasks.kis_price_stream.start_price_stream": {"queue": "stream"},
    "tasks.kis_price_stream.watchdog_price_stream": {"queue": "stream"},
}

# 스케줄
celery_app.conf.beat_schedule = {
    # 평일 16:30 - 장 마감 후 전체 데이터 수집
    "collect-daily-data": {
        "task": "tasks.collect.collect_all_stocks",
        "schedule": crontab(hour=16, minute=30, day_of_week="1-5"),
    },
    # 평일 09:00 - 서비스 다운으로 놓친 데이터 자동 보완
    "collect-missing-check": {
        "task": "tasks.collect.collect_missing_data",
        "schedule": crontab(hour=9, minute=0, day_of_week="1-5"),
    },
    "run-bots": {
        "task": "tasks.bot_engine.run_all_bots",
        "schedule": crontab(minute="*/5"),
    },
    "daily-reports": {
        "task": "tasks.bot_engine.generate_daily_reports",
        "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
    },
    # 평일 17:00 - 데이터 수집 완료 후 전략 스캐너 실행 (봇 tickers 자동 갱신)
    "scan-bot-tickers": {
        "task": "tasks.scanner.scan_bot_tickers",
        "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),
    },
    # 평일 17:30 - 스캐너 완료 후 ML 종목 스코어링
    "ml-score-stocks": {
        "task": "tasks.ai_tasks.train_and_score",
        "schedule": crontab(hour=17, minute=30, day_of_week="1-5"),
    },
    # 평일 08:30 - RUNNING 봇별 LLM 튜닝 제안 (tuning_suggestions 알림함에 드롭)
    # 봇 1:1 모델 전환으로 전역 generate_strategy / reopen_pending_patterns는 폐기.
    "propose-tuning-for-running-bots": {
        "task": "tasks.bot_tuning.propose_tuning_for_running_bots",
        "schedule": crontab(hour=8, minute=30, day_of_week="1-5"),
    },
    # 평일 08:55 - 장 시작 전 KIS WebSocket 실시간 시세 스트림 시작
    "start-price-stream": {
        "task": "tasks.kis_price_stream.start_price_stream",
        "schedule": crontab(hour=8, minute=55, day_of_week="1-5"),
    },
    # 평일 09:00~15:59 매 1분 - heartbeat 감시 + 자동 재기동
    "watchdog-price-stream": {
        "task": "tasks.kis_price_stream.watchdog_price_stream",
        "schedule": crontab(minute="*", hour="9-15", day_of_week="1-5"),
    },
    # 평일 정규장 매 1분 - 포트폴리오 Circuit Breaker (-7/-8.5/-10% 자동 방어)
    "portfolio-circuit-breaker": {
        "task": "tasks.circuit_breaker_task.run_circuit_breaker",
        "schedule": crontab(minute="*", hour="9-15", day_of_week="1-5"),
    },
    # 평일 09:00~15:00 매 1분 - scalping 봇 분봉 수집 & 지표 계산
    "collect-intraday-data": {
        "task": "tasks.intraday_collector.collect_intraday_data",
        "schedule": crontab(minute="*", hour="9-15", day_of_week="1-5"),
    },
    # 평일 09:00~15:00 매 1분 - scalping 봇 매매 엔진
    "run-scalping-bots": {
        "task": "tasks.scalping_engine.run_scalping_bots",
        "schedule": crontab(minute="*", hour="9-15", day_of_week="1-5"),
    },
    # 평일 15:35 KST - 장 마감 후 봇 전략 자동 진단 (프리미엄 기능)
    "bot-diagnostics": {
        "task": "tasks.bot_diagnostics.run_bot_diagnostics",
        "schedule": crontab(hour=15, minute=35, day_of_week="1-5"),
    },
    # 평일 정규장 매 5분 - 매커니즘 감사 (봇 invariant 검사, 위반 시에만 alert)
    "audit-mechanisms": {
        "task": "tasks.mechanism_audit.run_audit",
        "schedule": crontab(minute="*/5", hour="9-15", day_of_week="1-5"),
    },
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """워커 시작 시 누락 데이터 즉시 체크"""
    from tasks.collect import collect_missing_data
    collect_missing_data.delay()


# ── Phase 1.5 후크: 매커니즘 감사용 발사 시각 기록 ────────────────────
# beat이 발사한 모든 task의 시작 시각을 Redis에 SET. mechanism_audit.run_audit이
# A1(run_all_bots 5분 주기) 등의 발사 누락 검사에 사용. 본 task 흐름에 영향 없도록 try/except.
@task_prerun.connect
def _record_beat_last_fire(task_id=None, task=None, **kwargs):
    if task is None:
        return
    try:
        client = _redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
        key = _BEAT_LAST_FIRE_KEY_FMT.format(task=task.name)
        client.setex(key, _BEAT_LAST_FIRE_TTL, str(int(_time.time())))
    except Exception as e:
        _logger.warning("[celery_app] beat_last_fire 기록 실패 task=%s: %r", getattr(task, "name", "?"), e)
