from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.security import get_current_user
from core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])


class OptimizeRequest(BaseModel):
    strategy_id: int
    indicator: str
    condition: str
    value_min: float
    value_max: float
    value_step: float
    value2_fixed: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _task_status(task_id: str):
    from tasks.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.state == 'PENDING':
        return {"status": "pending"}
    elif result.state == 'STARTED':
        return {"status": "running"}
    elif result.state == 'SUCCESS':
        return {"status": "completed", "result": result.get()}
    elif result.state == 'FAILURE':
        return {"status": "failed", "error": str(result.result)}
    return {"status": result.state.lower()}


@router.post("/score")
def trigger_score(_: dict = Depends(get_current_user)):
    """ML 종목 스코어링 태스크 실행"""
    from tasks.ai_tasks import train_and_score
    task = train_and_score.delay()
    return {"task_id": str(task.id), "status": "queued"}


@router.get("/score/{task_id}")
def get_score_result(task_id: str, _: dict = Depends(get_current_user)):
    return _task_status(task_id)


@router.get("/scores")
def get_latest_scores(_: dict = Depends(get_current_user)):
    """Redis에 저장된 최신 ML 스코어 조회"""
    import json
    import redis
    from tasks.ai_tasks import ML_SCORES_KEY, ML_SCORES_META_KEY

    r = redis.from_url(settings.REDIS_URL)
    scores_json = r.get(ML_SCORES_KEY)
    meta_json = r.get(ML_SCORES_META_KEY)

    if not scores_json:
        return {"scores": {}, "meta": None}

    scores = json.loads(scores_json)
    meta = json.loads(meta_json) if meta_json else None
    return {"scores": scores, "meta": meta}


@router.post("/optimize")
def trigger_optimize(req: OptimizeRequest, _: dict = Depends(get_current_user)):
    """전략 파라미터 최적화 태스크 실행"""
    from tasks.ai_tasks import optimize_strategy
    task = optimize_strategy.delay(
        strategy_id=req.strategy_id,
        indicator=req.indicator,
        condition=req.condition,
        value_min=req.value_min,
        value_max=req.value_max,
        value_step=req.value_step,
        value2_fixed=req.value2_fixed,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return {"task_id": str(task.id), "status": "queued"}


@router.get("/optimize/{task_id}")
def get_optimize_result(task_id: str, _: dict = Depends(get_current_user)):
    return _task_status(task_id)
