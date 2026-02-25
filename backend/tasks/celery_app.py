from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery(
    "autostock",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.collect", "tasks.indicators", "tasks.backtest", "tasks.bot_engine"],
)

celery_app.conf.update(
    timezone="Asia/Seoul",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

# 스케줄: 평일 16:30 (장 마감 후) 전체 데이터 수집
celery_app.conf.beat_schedule = {
    "collect-daily-data": {
        "task": "tasks.collect.collect_all_stocks",
        "schedule": crontab(hour=16, minute=30, day_of_week="1-5"),
    },
    "run-bots": {
        "task": "tasks.bot_engine.run_all_bots",
        "schedule": crontab(minute="*/5"),
    },
    "daily-reports": {
        "task": "tasks.bot_engine.generate_daily_reports",
        "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
    },
}
