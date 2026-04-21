from datetime import datetime
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from services import strategy_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


# --- 스키마 ---

class ConditionItem(BaseModel):
    indicator: str
    condition: str  # above / below / between / golden_cross / dead_cross
    value: Optional[float] = None
    value2: Optional[float] = None  # between 전용


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    conditions: List[ConditionItem]
    strategy_type: Literal['swing', 'scalping'] = 'swing'


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[ConditionItem]] = None
    is_active: Optional[bool] = None
    strategy_type: Optional[Literal['swing', 'scalping']] = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    conditions: list
    strategy_type: str = 'swing'
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    tickers: List[str]
    start_date: str   # YYYY-MM-DD
    end_date: str
    initial_capital: float = 10_000_000
    stop_loss_pct: Optional[float] = None   # e.g. 5.0 → 5%
    take_profit_pct: Optional[float] = None
    transaction_cost: float = 0.003


# --- 엔드포인트 ---

def _user_id(current_user: dict) -> int:
    return int(current_user['sub'])


@router.get("", response_model=List[StrategyResponse])
def list_strategies(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return strategy_service.get_strategies(db, _user_id(current_user))


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    s = strategy_service.get_strategy(db, strategy_id, _user_id(current_user))
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다")
    return s


@router.post("", response_model=StrategyResponse, status_code=201)
def create_strategy(
    req: StrategyCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return strategy_service.create_strategy(
        db, _user_id(current_user), req.name, req.description,
        [c.model_dump() for c in req.conditions],
        strategy_type=req.strategy_type,
    )


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(
    strategy_id: int,
    req: StrategyUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    data = req.model_dump(exclude_none=True)
    if 'conditions' in data:
        data['conditions'] = [c.model_dump() if hasattr(c, 'model_dump') else c for c in req.conditions]
    s = strategy_service.update_strategy(db, strategy_id, _user_id(current_user), data)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다")
    return s


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not strategy_service.delete_strategy(db, strategy_id, _user_id(current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다")


@router.post("/{strategy_id}/backtest")
def trigger_backtest(
    strategy_id: int,
    req: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    s = strategy_service.get_strategy(db, strategy_id, _user_id(current_user))
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다")
    if not req.tickers:
        raise HTTPException(status_code=400, detail="백테스트할 종목을 하나 이상 입력하세요")

    from tasks.backtest import run_backtest_task
    task = run_backtest_task.delay(
        strategy_id=strategy_id,
        conditions=s.conditions,
        tickers=req.tickers,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        transaction_cost=req.transaction_cost,
    )
    return {"task_id": str(task.id), "status": "queued"}


@router.get("/{strategy_id}/backtest/{task_id}")
def get_backtest_result(
    strategy_id: int,
    task_id: str,
    _: dict = Depends(get_current_user),
):
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
