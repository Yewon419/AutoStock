"""봇 단위 strategy·canvas 관리 라우터.

봇 1:1 모델: 각 봇은 자기 전용 strategy를 보유. 캔버스에서 conditions·risk_params
를 변경할 때마다 strategy_history에 before/after 기록 → undo 가능.

08:30 자동 task가 만든 tuning_suggestions(=알림함) 조회·적용도 여기서 처리.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.strategy import Strategy, StrategyHistory, TuningSuggestion
from models.trading import TradingBot


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
