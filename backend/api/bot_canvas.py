"""봇 단위 strategy·canvas 관리 라우터.

봇 1:1 모델: 각 봇은 자기 전용 strategy를 보유. 캔버스에서 conditions·risk_params
를 변경할 때마다 strategy_history에 before/after 기록 → undo 가능.

08:30 자동 task가 만든 tuning_suggestions(=알림함) 조회·적용도 여기서 처리.
LLM 대화·자동 진단 응답을 tuning_suggestion으로 저장 후 사용자가 [적용] 클릭.
"""
from __future__ import annotations

import json as _json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from models.strategy import Strategy, StrategyHistory, TuningSuggestion, ChatMessage
from models.trading import TradingBot, Execution


CHAT_HISTORY_LLM_TURNS = 10  # LLM에 같이 보내는 직전 대화 턴 수 (user+assistant 합산 메시지)


router = APIRouter(tags=["bot-canvas"])


# risk_params dict ↔ trading_bots 컬럼 매핑
_RISK_PARAM_KEYS = {
    'stop_loss_pct',
    'take_profit_pct',
    'max_drawdown_pct',
    'position_size_pct',
    'max_positions',
    'max_daily_trades',
    'trailing_stop_pct',
    'confirm_bars',
}


def _user_id(current_user: dict) -> int:
    return int(current_user['sub'])


def _load_bot_and_strategy(db: Session, bot_id: int, user_id: int) -> tuple[TradingBot, Strategy]:
    """봇 + 그 봇의 strategy 동시 로드 (소유자 검증 포함)."""
    bot = (
        db.query(TradingBot)
        .filter(TradingBot.id == bot_id, TradingBot.user_id == user_id)
        .first()
    )
    if not bot:
        raise HTTPException(status_code=404, detail="봇을 찾을 수 없습니다")
    strategy = (
        db.query(Strategy)
        .filter(Strategy.bot_id == bot_id)
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=500, detail="봇과 연결된 strategy가 없습니다 (데이터 정합 오류)")
    return bot, strategy


def _snapshot_risk_params(bot: TradingBot) -> dict:
    """봇의 현재 risk_params 컬럼들을 dict로 스냅샷.
    NUMERIC 컬럼은 Decimal로 반환되는데 JSON 직렬화가 안 되니 float로 변환.
    """
    snapshot: dict = {}
    for k in _RISK_PARAM_KEYS:
        v = getattr(bot, k, None)
        if v is None:
            continue
        snapshot[k] = float(v) if isinstance(v, Decimal) else v
    return snapshot


def _apply_risk_params(bot: TradingBot, new: dict) -> None:
    """risk_params dict의 알려진 키들을 봇 컬럼에 적용."""
    for k, v in new.items():
        if k in _RISK_PARAM_KEYS:
            setattr(bot, k, v)


# ── 스키마 ──────────────────────────────────────────────────────────

class ApplyDiffRequest(BaseModel):
    """strategy 변경 1클릭 적용."""
    conditions: Optional[list] = None             # 새 strategy.conditions (None=변경 없음)
    risk_params: Optional[dict] = None            # 새 risk_params dict (None=변경 없음)
    source: Literal['manual', 'ai_chat', 'ai_suggestion'] = 'manual'
    llm_reasoning: Optional[str] = None
    suggestion_id: Optional[int] = None           # tuning_suggestions에서 온 거면 표기


class ApplyDiffResponse(BaseModel):
    history_id: int
    applied_at: datetime
    before_conditions: Optional[list] = None
    after_conditions: Optional[list] = None
    before_risk_params: Optional[dict] = None
    after_risk_params: Optional[dict] = None


class HistoryItem(BaseModel):
    id: int
    applied_at: datetime
    strategy_id: int
    before_conditions: Optional[list] = None
    after_conditions: Optional[list] = None
    before_risk_params: Optional[dict] = None
    after_risk_params: Optional[dict] = None
    source: str
    llm_reasoning: Optional[str] = None

    class Config:
        from_attributes = True


class SuggestionItem(BaseModel):
    id: int
    created_at: datetime
    status: str
    suggested_conditions: Optional[list] = None
    suggested_risk_params: Optional[dict] = None
    diagnosis_text: str
    applied_at: Optional[datetime] = None
    applied_history_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── 엔드포인트 ─────────────────────────────────────────────────────

@router.post("/trading/bots/{bot_id}/strategy/apply-diff", response_model=ApplyDiffResponse)
def apply_diff(
    bot_id: int,
    req: ApplyDiffRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if req.conditions is None and req.risk_params is None:
        raise HTTPException(status_code=400, detail="conditions 또는 risk_params 중 하나 이상이 필요합니다")

    bot, strategy = _load_bot_and_strategy(db, bot_id, _user_id(current_user))

    before_conditions = list(strategy.conditions) if strategy.conditions is not None else None
    before_risk_params = _snapshot_risk_params(bot)

    after_conditions: Optional[list] = None
    after_risk_params: Optional[dict] = None

    if req.conditions is not None:
        strategy.conditions = req.conditions
        after_conditions = req.conditions

    if req.risk_params is not None:
        _apply_risk_params(bot, req.risk_params)
        strategy.risk_params = {**(strategy.risk_params or {}), **req.risk_params}
        after_risk_params = _snapshot_risk_params(bot)

    history = StrategyHistory(
        bot_id=bot.id,
        strategy_id=strategy.id,
        before_conditions=before_conditions,
        after_conditions=after_conditions,
        before_risk_params=before_risk_params or None,
        after_risk_params=after_risk_params,
        source=req.source,
        llm_reasoning=req.llm_reasoning,
    )
    db.add(history)
    db.flush()

    if req.suggestion_id is not None:
        sugg = (
            db.query(TuningSuggestion)
            .filter(TuningSuggestion.id == req.suggestion_id, TuningSuggestion.bot_id == bot.id)
            .first()
        )
        if sugg and sugg.status == 'pending':
            sugg.status = 'applied'
            sugg.applied_at = datetime.utcnow()
            sugg.applied_history_id = history.id

    db.commit()
    db.refresh(history)

    return ApplyDiffResponse(
        history_id=history.id,
        applied_at=history.applied_at,
        before_conditions=before_conditions,
        after_conditions=after_conditions,
        before_risk_params=before_risk_params or None,
        after_risk_params=after_risk_params,
    )


@router.post("/trading/bots/{bot_id}/strategy/undo", response_model=ApplyDiffResponse)
def undo_last(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot, strategy = _load_bot_and_strategy(db, bot_id, _user_id(current_user))

    last = (
        db.query(StrategyHistory)
        .filter(StrategyHistory.bot_id == bot.id)
        .order_by(StrategyHistory.applied_at.desc(), StrategyHistory.id.desc())
        .first()
    )
    if not last:
        raise HTTPException(status_code=404, detail="복원할 변경 이력이 없습니다")

    current_conditions = list(strategy.conditions) if strategy.conditions is not None else None
    current_risk_params = _snapshot_risk_params(bot)

    if last.before_conditions is not None:
        strategy.conditions = last.before_conditions
    if last.before_risk_params is not None:
        _apply_risk_params(bot, last.before_risk_params)
        strategy.risk_params = last.before_risk_params

    history = StrategyHistory(
        bot_id=bot.id,
        strategy_id=strategy.id,
        before_conditions=current_conditions,
        after_conditions=last.before_conditions,
        before_risk_params=current_risk_params or None,
        after_risk_params=last.before_risk_params,
        source='manual',
        llm_reasoning=f"undo of history #{last.id}",
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return ApplyDiffResponse(
        history_id=history.id,
        applied_at=history.applied_at,
        before_conditions=current_conditions,
        after_conditions=last.before_conditions,
        before_risk_params=current_risk_params or None,
        after_risk_params=last.before_risk_params,
    )


@router.get("/trading/bots/{bot_id}/strategy/history", response_model=list[HistoryItem])
def get_history(
    bot_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # 소유자 검증 (404 빠르게)
    _load_bot_and_strategy(db, bot_id, _user_id(current_user))
    rows = (
        db.query(StrategyHistory)
        .filter(StrategyHistory.bot_id == bot_id)
        .order_by(StrategyHistory.applied_at.desc(), StrategyHistory.id.desc())
        .limit(limit)
        .all()
    )
    return rows


class PendingCountBot(BaseModel):
    bot_id: int
    bot_name: str
    count: int
    max_id: int = 0  # 이 봇의 가장 최근 pending suggestion id (unread 추적용)


class PendingCountSummary(BaseModel):
    total: int
    by_bot: list[PendingCountBot]


@router.get("/trading/bots/suggestions/pending-summary", response_model=PendingCountSummary)
def pending_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """전 봇 합산 pending suggestions 개수 (헤더 배지용). 봇별 분포도 + 봇별 최대 id."""
    user_id = _user_id(current_user)
    rows = (
        db.query(TradingBot.id, TradingBot.name, TuningSuggestion.id)
        .join(TuningSuggestion, TuningSuggestion.bot_id == TradingBot.id)
        .filter(TradingBot.user_id == user_id, TuningSuggestion.status == 'pending')
        .all()
    )
    by_bot_map: dict[int, dict] = {}
    for bot_id, bot_name, sugg_id in rows:
        if bot_id not in by_bot_map:
            by_bot_map[bot_id] = {'bot_id': bot_id, 'bot_name': bot_name, 'count': 0, 'max_id': 0}
        by_bot_map[bot_id]['count'] += 1
        if sugg_id > by_bot_map[bot_id]['max_id']:
            by_bot_map[bot_id]['max_id'] = sugg_id
    by_bot = [PendingCountBot(**v) for v in by_bot_map.values()]
    return PendingCountSummary(total=sum(b.count for b in by_bot), by_bot=by_bot)


@router.get("/trading/bots/{bot_id}/suggestions", response_model=list[SuggestionItem])
def get_suggestions(
    bot_id: int,
    status_filter: Optional[Literal['pending', 'applied', 'dismissed']] = 'pending',
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _load_bot_and_strategy(db, bot_id, _user_id(current_user))
    query = db.query(TuningSuggestion).filter(TuningSuggestion.bot_id == bot_id)
    if status_filter:
        query = query.filter(TuningSuggestion.status == status_filter)
    rows = (
        query.order_by(TuningSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.post("/trading/bots/{bot_id}/suggestions/{suggestion_id}/dismiss", response_model=SuggestionItem)
def dismiss_suggestion(
    bot_id: int,
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _load_bot_and_strategy(db, bot_id, _user_id(current_user))
    sugg = (
        db.query(TuningSuggestion)
        .filter(TuningSuggestion.id == suggestion_id, TuningSuggestion.bot_id == bot_id)
        .first()
    )
    if not sugg:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    if sugg.status != 'pending':
        raise HTTPException(status_code=400, detail=f"이미 처리된 제안입니다 (status={sugg.status})")
    sugg.status = 'dismissed'
    db.commit()
    db.refresh(sugg)
    return sugg


# ── LLM 튜닝 어시스턴트 ──────────────────────────────────────────

_TUNING_SYSTEM_PROMPT = """당신은 AutoStock 자동매매 봇의 전략 튜닝 어시스턴트입니다.
주어진 봇의 현재 strategy.conditions·risk_params·최근 거래 통계를 분석해 개선안을 제시합니다.

응답은 반드시 다음 JSON 형식으로만 (다른 텍스트 없이):
{
  "reply": "사용자에게 한국어로 보여줄 친근한 응답",
  "diagnosis": "봇 현재 상태 진단 (200자 이내)",
  "proposed_conditions": [...] | null,
  "proposed_risk_params": {...} | null
}

proposed_conditions 원소 형식:
{"indicator": "rsi" | "macd_histogram" | "volume_ratio" | "bollinger_upper" | ...,
 "condition": "above" | "below" | "between" | "golden_cross" | "dead_cross",
 "value": 숫자, "value2": 숫자 | null}

proposed_risk_params 키: stop_loss_pct, take_profit_pct, max_drawdown_pct,
position_size_pct, max_positions, max_daily_trades, trailing_stop_pct, confirm_bars

원칙:
- 한 번에 1~2개 항목만 손대기. 무리한 큰 변경 금지.
- SL × max_positions × position_size_pct 합산이 MDD 가드를 넘지 않게.
- swing 봇 SL 2~7%, scalping SL 1~3% 범위 유지.
- 단순 대화·진단만 요구되면 proposed_* 모두 null로 두기."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    diagnosis: Optional[str] = None
    proposed_conditions: Optional[list] = None
    proposed_risk_params: Optional[dict] = None
    suggestion_id: Optional[int] = None


def _build_tuning_context(db: Session, bot: TradingBot, strategy: Strategy) -> str:
    sells = (
        db.query(Execution)
        .filter(Execution.bot_id == bot.id, Execution.execution_type == 'SELL')
        .order_by(Execution.executed_at.desc())
        .limit(50)
        .all()
    )
    buy_count = (
        db.query(Execution)
        .filter(Execution.bot_id == bot.id, Execution.execution_type == 'BUY')
        .count()
    )
    win = sum(1 for s in sells if s.profit_loss is not None and float(s.profit_loss) > 0)
    lose = len(sells) - win
    avg_pl_pct = (
        sum(float(s.profit_loss_pct or 0) for s in sells) / len(sells)
        if sells else 0.0
    )

    risk = _snapshot_risk_params(bot)
    risk_text = ", ".join(f"{k}={v}" for k, v in risk.items()) or "(없음)"
    cond_text = (
        _json.dumps(strategy.conditions, ensure_ascii=False)
        if strategy.conditions else "(없음)"
    )

    return (
        f"봇 ID: {bot.id} ({bot.name})\n"
        f"bot_type: {bot.bot_type}\n"
        f"현재 strategy.conditions: {cond_text}\n"
        f"현재 risk_params: {risk_text}\n"
        f"최근 거래: BUY {buy_count}건, SELL {len(sells)}건 "
        f"(승 {win} / 패 {lose}, SELL 평균 P&L {avg_pl_pct:.2f}%)"
    )


def _load_recent_chat(db: Session, bot_id: int, limit: int) -> list[ChatMessage]:
    """최근 N개 메시지를 시간 오름차순(오래된 → 최신)으로 반환."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.bot_id == bot_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def _call_tuning_llm(context: str, user_message: str, prior: list[ChatMessage]) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY 미설정")

    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # 다중턴: 직전 대화 + 이번 turn(현황 컨텍스트 + 사용자 메시지)
    msgs: list[dict] = [{"role": m.role, "content": m.content} for m in prior]
    msgs.append({
        "role": "user",
        "content": f"{context}\n\n사용자 메시지: {user_message}",
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=_TUNING_SYSTEM_PROMPT,
        messages=msgs,
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    try:
        return _json.loads(raw.strip())
    except _json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"LLM 응답 JSON 파싱 실패: {e}")


def _process_tuning(db: Session, bot: TradingBot, strategy: Strategy, user_message: str) -> ChatResponse:
    context = _build_tuning_context(db, bot, strategy)
    prior = _load_recent_chat(db, bot.id, CHAT_HISTORY_LLM_TURNS)
    result = _call_tuning_llm(context, user_message, prior)

    proposed_conditions = result.get('proposed_conditions')
    proposed_risk_params = result.get('proposed_risk_params')
    reply = result.get('reply', '')
    diagnosis = result.get('diagnosis')

    suggestion_id: Optional[int] = None
    if proposed_conditions is not None or proposed_risk_params is not None:
        sugg = TuningSuggestion(
            bot_id=bot.id,
            suggested_conditions=proposed_conditions,
            suggested_risk_params=proposed_risk_params,
            diagnosis_text=diagnosis or reply or "(no diagnosis)",
        )
        db.add(sugg)
        db.commit()
        db.refresh(sugg)
        suggestion_id = sugg.id

    # 대화 기록 영속화 (LLM 호출 성공 후에만)
    db.add(ChatMessage(bot_id=bot.id, role='user', content=user_message))
    if reply:
        db.add(ChatMessage(bot_id=bot.id, role='assistant', content=reply))
    db.commit()

    return ChatResponse(
        reply=reply,
        diagnosis=diagnosis,
        proposed_conditions=proposed_conditions,
        proposed_risk_params=proposed_risk_params,
        suggestion_id=suggestion_id,
    )


@router.post("/trading/bots/{bot_id}/strategy/chat", response_model=ChatResponse)
def strategy_chat(
    bot_id: int,
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """봇 단위 LLM 어시스턴트와 자연어 대화. 제안이 있으면 tuning_suggestion으로 저장."""
    bot, strategy = _load_bot_and_strategy(db, bot_id, _user_id(current_user))
    return _process_tuning(db, bot, strategy, req.message)


@router.post("/trading/bots/{bot_id}/strategy/ai-generate", response_model=ChatResponse)
def strategy_ai_generate(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """봇 현황을 자동 진단하고 개선안을 1건 제안."""
    bot, strategy = _load_bot_and_strategy(db, bot_id, _user_id(current_user))
    user_msg = "이 봇의 최근 성과를 분석해서 개선안(strategy.conditions 또는 risk_params)을 제시하세요."
    return _process_tuning(db, bot, strategy, user_msg)


class ChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


@router.get("/trading/bots/{bot_id}/strategy/chat-history", response_model=list[ChatMessageItem])
def chat_history(
    bot_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """봇 단위 LLM 어시스턴트 대화 기록 (오래된 → 최신 순으로 limit 만큼 반환)."""
    _load_bot_and_strategy(db, bot_id, _user_id(current_user))  # 소유자 검증
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.bot_id == bot_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [
        ChatMessageItem(id=r.id, role=r.role, content=r.content, created_at=r.created_at)
        for r in reversed(rows)
    ]
