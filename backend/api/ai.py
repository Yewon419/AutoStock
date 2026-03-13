from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.security import get_current_user
from core.config import settings
from core.database import get_db

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


# ── LLM 전략 생성 ────────────────────────────────────────────────────

@router.post("/generate-strategy")
def trigger_generate_strategy(
    current_user: dict = Depends(get_current_user),
):
    """LLM 전략 생성 태스크 실행 (수동 트리거)"""
    from tasks.llm_strategy import generate_strategy
    task = generate_strategy.delay(user_id=int(current_user["sub"]))
    return {"task_id": str(task.id), "status": "queued"}


@router.get("/generate-strategy/{task_id}")
def get_generate_strategy_result(
    task_id: str,
    _: dict = Depends(get_current_user),
):
    return _task_status(task_id)


@router.get("/generated-strategies")
def get_generated_strategies(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI가 생성한 전략 목록 (최신 20개)"""
    from models.strategy import Strategy
    strategies = (
        db.query(Strategy)
        .filter(
            Strategy.user_id == int(current_user["sub"]),
            Strategy.source == "ai_generated",
        )
        .order_by(Strategy.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "strategy_type": s.strategy_type,
            "conditions": s.conditions,
            "ai_analysis": s.ai_analysis,
            "ai_confidence": s.ai_confidence,
            "created_at": s.created_at,
        }
        for s in strategies
    ]


# ── 캔버스 전용 엔드포인트 ────────────────────────────────────────────

@router.get("/tech-indicators-summary")
def get_tech_indicators_summary(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """기술 지표 DB 최신 요약 (캔버스 techIndicators 노드용)"""
    import math
    from models.market import TechnicalIndicator

    latest = (
        db.query(TechnicalIndicator.date)
        .order_by(TechnicalIndicator.date.desc())
        .first()
    )
    if not latest:
        return {"status": "no_data"}

    latest_date = latest[0]
    inds = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.date == latest_date)
        .limit(500)
        .all()
    )

    def sf(v, d=0.0):
        if v is None: return d
        try:
            f = float(v)
            return d if math.isnan(f) or math.isinf(f) else f
        except: return d

    rsi_vals = [sf(i.rsi) for i in inds if i.rsi is not None]
    adx_vals = [sf(i.adx) for i in inds if i.adx is not None]

    return {
        "status": "ok",
        "latest_date": str(latest_date),
        "ticker_count": len(inds),
        "avg_rsi": round(sum(rsi_vals) / len(rsi_vals), 1) if rsi_vals else 0,
        "avg_adx": round(sum(adx_vals) / len(adx_vals), 1) if adx_vals else 0,
    }


class BacktestStrategyRequest(BaseModel):
    strategy_id: int
    tickers_source: str = "ml_top"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/backtest-strategy")
def trigger_backtest_strategy(
    req: BacktestStrategyRequest,
    _: dict = Depends(get_current_user),
):
    """전략 백테스트 태스크 실행 (캔버스 backtest 노드용)"""
    from tasks.ai_tasks import backtest_on_ml_top
    task = backtest_on_ml_top.delay(
        strategy_id=req.strategy_id,
        tickers_source=req.tickers_source,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return {"task_id": str(task.id), "status": "queued"}


@router.get("/backtest-strategy/{task_id}")
def get_backtest_strategy_result(task_id: str, _: dict = Depends(get_current_user)):
    return _task_status(task_id)


class CanvasNode(BaseModel):
    id: str
    type: str
    status: str = "idle"


class CanvasEdge(BaseModel):
    source: str = ""
    target: str = ""
    source_type: str = ""
    target_type: str = ""


class CanvasState(BaseModel):
    nodes: List[CanvasNode] = []
    edges: List[CanvasEdge] = []


class CanvasAssistantRequest(BaseModel):
    message: str
    canvas: CanvasState = CanvasState()


@router.post("/canvas-assistant")
def canvas_assistant(
    req: CanvasAssistantRequest,
    _: dict = Depends(get_current_user),
):
    """캔버스 AI 어시스턴트 — 자연어로 캔버스 조작 명령 반환"""
    if not settings.ANTHROPIC_API_KEY:
        return {"reply": "ANTHROPIC_API_KEY가 설정되지 않았습니다.", "commands": []}

    import anthropic, json

    nodes = req.canvas.nodes
    edges = req.canvas.edges

    if nodes:
        node_desc = f"노드 {len(nodes)}개: " + ", ".join(
            f"{n.type}({n.status})" for n in nodes
        )
        edge_desc = (f" / 연결 {len(edges)}개: " + ", ".join(
            f"{e.source_type}→{e.target_type}" for e in edges[:6]
        )) if edges else ""
        canvas_desc = f"\n현재 캔버스: {node_desc}{edge_desc}"
    else:
        canvas_desc = "\n현재 캔버스: 비어 있음"

    system_prompt = """당신은 AutoStock 자동매매 시스템의 캔버스 AI 어시스턴트입니다.
사용자의 자연어 요청을 분석하여 캔버스 조작 명령을 JSON으로 반환합니다.

[사용 가능한 노드]
소스 노드: marketContext(시장 컨텍스트), techIndicators(기술 지표 DB), mlScores(ML 스코어 캐시)
처리 노드: mlModel(ML 모델 학습), llmGenerator(LLM 전략 생성), backtest(백테스트)
출력 노드: botApply(봇 적용)

[연결 규칙]
marketContext.market_data → llmGenerator.market_data
techIndicators.indicator_data → mlModel.indicator_data
mlScores.ml_scores → llmGenerator.ml_scores
mlModel.ml_scores → llmGenerator.ml_scores
llmGenerator.strategy → backtest.strategy
llmGenerator.strategy → botApply.strategy

[레이아웃 프리셋]
풀 파이프라인: marketContext(80,120) techIndicators(80,320) mlModel(340,220) llmGenerator(600,120) backtest(600,340) botApply(860,120)
빠른 전략: marketContext(80,180) mlScores(80,340) llmGenerator(360,270) botApply(640,270)
ML만: techIndicators(80,200) mlModel(360,200)
LLM만: marketContext(80,200) llmGenerator(360,200) botApply(640,200)

[응답 형식 — 반드시 JSON만, 다른 텍스트 없이]
{
  "reply": "사용자에게 보여줄 설명",
  "commands": [
    {"type": "clear"},
    {"type": "add_node", "node_type": "marketContext", "x": 80, "y": 120},
    {"type": "connect", "source_type": "marketContext", "target_type": "llmGenerator", "source_handle": "market_data", "target_handle": "market_data"},
    {"type": "run_node", "node_type": "mlModel"},
    {"type": "remove_node", "node_type": "backtest"}
  ]
}
commands가 필요 없으면 []로."""

    user_msg = f"{canvas_desc}\n\n사용자 요청: {req.message}"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        result = json.loads(raw.strip())
        return result
    except json.JSONDecodeError:
        return {"reply": raw, "commands": []}
    except Exception as e:
        return {"reply": f"오류: {str(e)}", "commands": []}


@router.get("/canvas-state")
def get_canvas_state(current_user: dict = Depends(get_current_user)):
    """사용자별 캔버스 레이아웃 조회"""
    import json, redis
    r = redis.from_url(settings.REDIS_URL)
    key = f"autostock:canvas:{current_user['sub']}"
    data = r.get(key)
    if not data:
        return {"nodes": [], "edges": []}
    return json.loads(data)


@router.post("/canvas-state")
def save_canvas_state(payload: dict, current_user: dict = Depends(get_current_user)):
    """사용자별 캔버스 레이아웃 저장 (만료 없음)"""
    import json, redis
    r = redis.from_url(settings.REDIS_URL)
    key = f"autostock:canvas:{current_user['sub']}"
    r.set(key, json.dumps(payload))
    return {"status": "ok"}


@router.get("/market-context")
def get_market_context(_: dict = Depends(get_current_user)):
    """현재 시장 컨텍스트 수집 (미리보기용)"""
    from tasks.news_crawler import collect_market_context
    try:
        ctx = collect_market_context()
        return {"status": "ok", "context": ctx}
    except Exception as e:
        return {"status": "error", "message": str(e)}
