from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready
from core.config import settings

celery_app = Celery(
    "autostock",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.collect", "tasks.indicators", "tasks.backtest",
        "tasks.bot_engine", "tasks.scanner", "tasks.ai_tasks",
        "tasks.kis_price_stream",
        "tasks.intraday_collector", "tasks.scalping_engine",
        "tasks.llm_strategy",
    ],
)

celery_app.conf.update(
    timezone="Asia/Seoul",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

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
    # 평일 08:30 - 장 시작 전 LLM 전략 자동 생성
    "llm-generate-strategy": {
        "task": "tasks.llm_strategy.generate_strategy",
        "schedule": crontab(hour=8, minute=30, day_of_week="1-5"),
        "kwargs": {"user_id": 1},
    },
    # 평일 08:55 - 장 시작 전 KIS WebSocket 실시간 시세 스트림 시작
    "start-price-stream": {
        "task": "tasks.kis_price_stream.start_price_stream",
        "schedule": crontab(hour=8, minute=55, day_of_week="1-5"),
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
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """워커 시작 시 누락 데이터 즉시 체크"""
    from tasks.collect import collect_missing_data
    collect_missing_data.delay()
