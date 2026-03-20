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
    error: Optional[str] = None


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
    insights: Optional[dict] = None  # GET /ai/canvas-insights 결과


@router.post("/canvas-assistant")
def canvas_assistant(
    req: CanvasAssistantRequest,
    _: dict = Depends(get_current_user),
):
    """캔버스 AI 어시스턴트 — 자연어로 캔버스 조작 명령 반환"""
    if not settings.ANTHROPIC_API_KEY:
        return {"reply": "ANTHROPIC_API_KEY가 설정되지 않았습니다.", "commands": []}

    import anthropic, json, os

    # 주식 전문 지식 베이스 로드
    _kb_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "stock_knowledge.md")
    try:
        with open(_kb_path, encoding="utf-8") as f:
            stock_knowledge = f.read()
    except Exception:
        stock_knowledge = ""

    nodes = req.canvas.nodes
    edges = req.canvas.edges

    if nodes:
        def _node_str(n):
            s = f"{n.type}({n.status})"
            if n.status == "error" and getattr(n, "error", None):
                s += f"[에러: {n.error}]"
            return s
        node_desc = f"노드 {len(nodes)}개: " + ", ".join(_node_str(n) for n in nodes)
        edge_desc = (f" / 연결 {len(edges)}개: " + ", ".join(
            f"{e.source_type}→{e.target_type}" for e in edges[:6]
        )) if edges else ""
        canvas_desc = f"\n현재 캔버스: {node_desc}{edge_desc}"
    else:
        canvas_desc = "\n현재 캔버스: 비어 있음"

    knowledge_section = f"\n\n[주식 전문 지식 베이스]\n{stock_knowledge}\n" if stock_knowledge else ""

    system_prompt = f"""당신은 AutoStock 자동매매 시스템의 캔버스 AI 어시스턴트이자 한국 주식 전문가입니다.
주식 기술적 분석, 리스크 관리, 시장 국면 판단에 대한 깊은 전문 지식을 갖추고 있으며,
사용자의 자연어 요청을 분석하여 캔버스 조작 명령을 JSON으로 반환합니다.
{knowledge_section}

[사용 가능한 노드]
소스 노드: marketContext(시장 컨텍스트), techIndicators(기술 지표 DB), mlScores(ML 스코어 캐시)
전략 노드: strategy(기존 전략 선택), strategyBuilder(조건 직접 설정 전략 빌더)
처리 노드: mlModel(ML 모델 학습), llmGenerator(LLM 전략 생성), backtest(백테스트)
출력 노드: botApply(봇 적용)

[연결 규칙]
marketContext.market_data → llmGenerator.market_data
techIndicators.indicator_data → mlModel.indicator_data
mlScores.ml_scores → llmGenerator.ml_scores
mlModel.ml_scores → llmGenerator.ml_scores
llmGenerator.strategy → backtest.strategy
llmGenerator.strategy → botApply.strategy
strategy.strategy → backtest.strategy
strategy.strategy → botApply.strategy
strategyBuilder.strategy → backtest.strategy
strategyBuilder.strategy → botApply.strategy

[레이아웃 프리셋]
풀 파이프라인: marketContext(80,120) techIndicators(80,320) mlModel(340,220) llmGenerator(600,120) backtest(600,340) botApply(860,120)
빠른 전략: marketContext(80,180) mlScores(80,340) llmGenerator(360,270) botApply(640,270)
ML만: techIndicators(80,200) mlModel(360,200)
LLM만: marketContext(80,200) llmGenerator(360,200) botApply(640,200)
기존전략+백테스트: strategy(80,200) backtest(360,200) botApply(640,200)
전략빌더+백테스트: strategyBuilder(80,200) backtest(360,200) botApply(640,200)

[add_node 추가 옵션]
strategyBuilder 노드 추가 시 "name" 필드로 전략명을 지정하세요 (예: "RSI 과매도 전략", "MACD 골든크로스 전략").
사용자 요청에서 전략 성격을 파악해 적절한 전략명을 자동으로 생성하세요.

[에러 진단 및 수정]
노드의 status가 "error"이고 error 필드가 있으면 원인을 분석하고 수정 commands를 반환하세요.
에러별 수정 방법:
- "전략 노드를 연결한 후 먼저 실행하세요" → 상위 전략/LLM 노드를 run_node로 먼저 실행, 이후 botApply run_node
- "LLM 전략이 품질 기준 미달" → llmGenerator를 run_node로 재실행 (다른 전략 생성 시도)
- "봇을 선택하세요" / "로그인이 만료" / "전략명 입력" → commands [] + reply에 안내
- 일반 실행 오류 → 해당 노드 run_node로 재실행

[실시간 데이터 기반 자동 최적화]
사용자 메시지에 [실시간 데이터] 섹션이 포함되어 있으면 반드시 이를 분석하여 전략/파라미터를 최적화하세요.

데이터 해석 가이드:
- market.regime = "횡보장" (avg_adx < 20): RSI 역투자 전략 권장 → RSI < 30 + volume_ratio > 1.5
- market.regime = "추세장" (avg_adx >= 25): 추세추종 권장 → MACD 골든크로스 + ADX > 25
- market.avg_rsi < 35: 시장 전반 과매도 → 매수 기회, RSI 기준 완화 (< 35)
- market.avg_rsi > 65: 시장 전반 과매수 → 매수 자제, RSI 기준 강화 (< 25)
- market.rsi_oversold_pct > 20%: 과매도 종목 많음 → 분할매수 좋은 타이밍
- ml.oos_accuracy > 0.55: ML 신뢰도 높음 → ML 상위 종목 대상 백테스트 권장
- ml.oos_accuracy < 0.52: ML 신뢰도 낮음 → 거래량 상위(volume_top) 대상으로 변경
- backtests 승률 < 40%: 전략 조건 강화 필요 → 조건 추가
- backtests 승률 > 60%: 검증된 전략 → 해당 조건 재사용 권장

update_config 명령으로 기존 노드 설정을 직접 업데이트하세요:
- strategyBuilder 조건 업데이트: {{"type": "update_config", "node_type": "strategyBuilder", "config": {{"name": "전략명", "strategy_type": "swing", "conditions": [{{"indicator": "rsi", "condition": "below", "value": 30}}]}}}}
- backtest 종목소스 변경: {{"type": "update_config", "node_type": "backtest", "config": {{"tickers_source": "ml_top"}}}}
- strategy 선택 변경: {{"type": "update_config", "node_type": "strategy", "config": {{"strategy_id": 5}}}}

[자동 최적화 시 노드 추가·제거 규칙]
최적화는 기존 노드를 수정하는 것에 그치지 않고, 파이프라인 구성 자체를 자유롭게 변경해도 됩니다.
- 필요한 노드가 없으면 add_node + connect로 추가하세요.
  예) backtest 노드가 없는데 백테스트 검증이 필요하다 → backtest 노드 추가 후 연결
  예) ML 신뢰도가 낮은데 mlModel 노드가 없다 → mlModel + techIndicators 추가
- 현재 파이프라인에 불필요한 노드가 있으면 remove_node로 제거하세요.
  예) ML 신뢰도가 낮아 mlScores 노드가 무의미하다 → 제거
  예) 단순 전략 검증인데 marketContext/llmGenerator가 있다 → 제거
- remove_node: {{"type": "remove_node", "node_type": "mlScores"}}
- 노드 추가·제거 후 연결(connect)도 함께 구성해 파이프라인이 완결되게 하세요.
- botApply 노드는 자동 최적화 시 반드시 포함되어야 합니다. 없으면 add_node로 추가하세요.
- 추가된 모든 노드는 반드시 연결되어야 합니다. 고립된 노드(어떤 엣지에도 연결되지 않은 노드)가 있어서는 안 됩니다.
  예) techIndicators 추가 → mlModel에 connect / mlModel 추가 → llmGenerator 또는 backtest에 connect
- 파이프라인의 마지막 전략 노드(backtest 또는 전략 노드)는 반드시 botApply에 connect 하세요.
- 전체 파이프라인이 소스→전략→처리→botApply로 이어지는 완결된 흐름이어야 합니다.

자동 최적화 응답 시 반드시: ① 데이터 해석 결과 ② 어떤 파이프라인 구성을 왜 선택했는지 (추가·제거 이유 포함) ③ 노드 추가/제거/update_config/connect/run_node 명령 순서로 포함하세요.

[응답 형식 — 반드시 JSON만, 다른 텍스트 없이]
{{"reply": "사용자에게 보여줄 설명", "commands": [{{"type": "clear"}}, {{"type": "add_node", "node_type": "strategyBuilder", "x": 80, "y": 200, "name": "RSI 과매도 전략"}}, {{"type": "update_config", "node_type": "strategyBuilder", "config": {{"conditions": [{{"indicator": "rsi", "condition": "below", "value": 30}}]}}}}, {{"type": "connect", "source_type": "strategyBuilder", "target_type": "backtest", "source_handle": "strategy", "target_handle": "strategy"}}, {{"type": "run_node", "node_type": "strategyBuilder"}}, {{"type": "run_node", "node_type": "backtest"}}]}}
commands가 필요 없으면 []로."""

    # 실시간 데이터 인사이트 메시지 구성
    insights_desc = ""
    if req.insights:
        insights_desc = f"\n\n[실시간 데이터]\n{json.dumps(req.insights, ensure_ascii=False, indent=2)}"

    user_msg = f"{canvas_desc}{insights_desc}\n\n사용자 요청: {req.message}"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=12000,
            thinking={"type": "enabled", "budget_tokens": 8000},
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        thinking_text = ""
        raw = ""
        for block in message.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                raw = block.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        result = json.loads(raw.strip())
        if thinking_text:
            result["thinking"] = thinking_text
        return result
    except json.JSONDecodeError:
        return {"reply": raw, "commands": []}
    except Exception as e:
        return {"reply": f"오류: {str(e)}", "commands": []}


@router.get("/canvas-insights")
def get_canvas_insights(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """백테스트·ML·시장지표 실시간 데이터 요약 (AI 자동 최적화용)"""
    import json, redis, math
    from models.market import TechnicalIndicator
    from models.strategy import Strategy
    from models.trading import BotReport

    r = redis.from_url(settings.REDIS_URL)
    result = {}

    # ── ML 스코어 ────────────────────────────────────────────────
    try:
        from tasks.ai_tasks import ML_SCORES_KEY, ML_SCORES_META_KEY
        scores_json = r.get(ML_SCORES_KEY)
        meta_json   = r.get(ML_SCORES_META_KEY)
        if scores_json:
            scores = json.loads(scores_json)
            top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
            meta = json.loads(meta_json) if meta_json else {}
            result["ml"] = {
                "top_tickers": [t for t, _ in top],
                "top_scores": {t: round(s, 3) for t, s in top},
                "oos_accuracy": meta.get("oos_accuracy"),
                "trained_at": meta.get("trained_at"),
            }
    except Exception:
        pass

    # ── 시장 기술 지표 요약 ──────────────────────────────────────
    try:
        latest = (
            db.query(TechnicalIndicator.date)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        if latest:
            inds = (
                db.query(TechnicalIndicator)
                .filter(TechnicalIndicator.date == latest[0])
                .limit(500).all()
            )
            def _f(v):
                if v is None: return None
                try:
                    f = float(v)
                    return None if (math.isnan(f) or math.isinf(f)) else f
                except: return None

            rsi_vals = [_f(i.rsi) for i in inds if _f(i.rsi) is not None]
            adx_vals = [_f(i.adx) for i in inds if _f(i.adx) is not None]
            avg_adx  = round(sum(adx_vals) / len(adx_vals), 1) if adx_vals else 0
            avg_rsi  = round(sum(rsi_vals)  / len(rsi_vals),  1) if rsi_vals else 0

            result["market"] = {
                "latest_date": str(latest[0]),
                "ticker_count": len(inds),
                "avg_rsi": avg_rsi,
                "avg_adx": avg_adx,
                "rsi_oversold_count":   len([v for v in rsi_vals if v < 30]),
                "rsi_overbought_count": len([v for v in rsi_vals if v > 70]),
                "rsi_oversold_pct": round(len([v for v in rsi_vals if v < 30]) / len(rsi_vals) * 100, 1) if rsi_vals else 0,
                "regime": "추세장" if avg_adx >= 25 else ("추세형성중" if avg_adx >= 20 else "횡보장"),
            }
    except Exception:
        pass

    # ── 최근 백테스트 성과 (BotReport 기준) ─────────────────────
    try:
        reports = (
            db.query(BotReport)
            .order_by(BotReport.created_at.desc())
            .limit(10).all()
        )
        if reports:
            result["backtests"] = [
                {
                    "date": str(r_.date),
                    "total_pnl": float(r_.total_pnl or 0),
                    "win_rate":  float(r_.win_rate  or 0),
                    "total_trades": r_.total_trades,
                    "max_drawdown": float(r_.max_drawdown or 0),
                    "sharpe_ratio": float(r_.sharpe_ratio or 0),
                }
                for r_ in reports
            ]
    except Exception:
        pass

    # ── 최근 AI 생성 전략 ────────────────────────────────────────
    try:
        strategies = (
            db.query(Strategy)
            .filter(Strategy.source == "ai_generated")
            .order_by(Strategy.created_at.desc())
            .limit(5).all()
        )
        result["recent_strategies"] = [
            {
                "id": s.id,
                "name": s.name,
                "strategy_type": s.strategy_type,
                "confidence": s.ai_confidence,
                "conditions_count": len(s.conditions) if s.conditions else 0,
            }
            for s in strategies
        ]
    except Exception:
        pass

    return result


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
