from datetime import datetime, time
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from services import trading_service

router = APIRouter(tags=["trading"])


def _user_id(current_user: dict) -> int:
    return int(current_user['sub'])


# ── 스키마 ──────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    account_number: str
    owner_name: str
    broker: str = 'kiwoom'
    account_type: str = 'paper'   # paper=모의투자 | real=실계좌


class AccountResponse(BaseModel):
    id: int
    owner_name: str
    broker: str
    account_type: str = 'paper'
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BotCreate(BaseModel):
    name: str
    mode: str = 'mock'            # mock | paper | real
    strategy_id: Optional[int] = None
    account_id: Optional[int] = None
    tickers: List[str] = []
    initial_cash: float = 10_000_000
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    max_drawdown_pct: float = 15.0
    position_size_pct: float = 10.0
    max_positions: int = 5
    max_daily_trades: int = 20
    max_order_amount: float = 1_000_000
    trading_start_time: Optional[str] = "09:00"   # "HH:MM"
    trading_end_time: Optional[str] = "15:20"
    # 단타 설정
    bot_type: str = 'swing'                        # swing | scalping
    candle_interval: int = 5                       # 분봉 단위 (1,3,5,10,15)
    intraday_close: bool = False                   # 당일 강제 청산 여부
    intraday_close_time: Optional[str] = "14:50"  # "HH:MM"
    trailing_stop_pct: Optional[float] = None      # 트레일링 스탑 % (None=비활성화)
    confirm_bars: int = 1                          # 연속 신호 확인 봉 수 (1=즉시 진입)


class BotUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    strategy_id: Optional[int] = None
    tickers: Optional[List[str]] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    max_positions: Optional[int] = None
    max_daily_trades: Optional[int] = None
    max_order_amount: Optional[float] = None
    trading_start_time: Optional[str] = None
    trading_end_time: Optional[str] = None
    # 단타 설정
    bot_type: Optional[str] = None
    candle_interval: Optional[int] = None
    intraday_close: Optional[bool] = None
    intraday_close_time: Optional[str] = None
    trailing_stop_pct: Optional[float] = None
    confirm_bars: Optional[int] = None


class BotResponse(BaseModel):
    id: int
    name: str
    status: str
    mode: str = 'mock'
    strategy_id: Optional[int] = None
    account_id: Optional[int] = None
    tickers: Optional[list] = []
    initial_cash: Optional[float] = None
    cash: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    max_positions: Optional[int] = None
    max_daily_trades: Optional[int] = None
    max_order_amount: Optional[float] = None
    trading_start_time: Optional[time] = None
    trading_end_time: Optional[time] = None
    created_at: Optional[datetime] = None
    # 단타 설정
    bot_type: Optional[str] = 'swing'
    candle_interval: Optional[int] = None
    intraday_close: Optional[bool] = None
    intraday_close_time: Optional[time] = None
    trailing_stop_pct: Optional[float] = None
    confirm_bars: Optional[int] = None

    class Config:
        from_attributes = True


# ── 계좌 ────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=List[AccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return trading_service.get_accounts(db, _user_id(current_user))


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    req: AccountCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return trading_service.create_account(
        db, _user_id(current_user), req.account_number, req.owner_name, req.broker, req.account_type
    )


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not trading_service.delete_account(db, account_id, _user_id(current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계좌를 찾을 수 없습니다")


# ── 봇 ──────────────────────────────────────────────────────────────

@router.get("/bots", response_model=List[BotResponse])
def list_bots(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return trading_service.get_bots(db, _user_id(current_user))


@router.post("/bots", response_model=BotResponse, status_code=201)
def create_bot(
    req: BotCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    data = req.model_dump()
    # time 문자열 → time 객체 변환
    for key in ('trading_start_time', 'trading_end_time', 'intraday_close_time'):
        val = data.get(key)
        if val and isinstance(val, str):
            try:
                h, m = val.split(':')
                data[key] = time(int(h), int(m))
            except Exception:
                data[key] = None
    return trading_service.create_bot(db, _user_id(current_user), data)


@router.get("/bots/{bot_id}", response_model=BotResponse)
def get_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    return bot


@router.put("/bots/{bot_id}", response_model=BotResponse)
def update_bot(
    bot_id: int,
    req: BotUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    data = req.model_dump(exclude_none=True)
    for key in ('trading_start_time', 'trading_end_time', 'intraday_close_time'):
        val = data.get(key)
        if val and isinstance(val, str):
            try:
                h, m = val.split(':')
                data[key] = time(int(h), int(m))
            except Exception:
                data.pop(key, None)
    bot = trading_service.update_bot(db, bot_id, _user_id(current_user), data)
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없거나 실행 중입니다")
    return bot


@router.delete("/bots/{bot_id}", status_code=204)
def delete_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not trading_service.delete_bot(db, bot_id, _user_id(current_user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없거나 실행 중입니다")


@router.post("/bots/{bot_id}/start", response_model=BotResponse)
def start_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.start_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=400, detail="봇을 시작할 수 없습니다")
    return bot


@router.post("/bots/{bot_id}/stop", response_model=BotResponse)
def stop_bot(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.stop_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=400, detail="봇을 정지할 수 없습니다")
    return bot


# ── 봇 데이터 ────────────────────────────────────────────────────────

@router.get("/bots/{bot_id}/positions")
def get_positions(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # 봇 소유 확인
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    return trading_service.get_positions(db, bot_id)


@router.get("/bots/{bot_id}/orders")
def get_orders(
    bot_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    orders = trading_service.get_orders(db, bot_id, limit)
    return [
        {
            'id': o.id,
            'ticker': o.ticker,
            'order_type': o.order_type,
            'quantity': o.quantity,
            'price': float(o.price) if o.price else 0,
            'status': o.status,
            'created_at': o.created_at,
        }
        for o in orders
    ]


@router.get("/bots/{bot_id}/executions")
def get_executions(
    bot_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    from models.trading import Execution
    execs = (
        db.query(Execution)
        .filter(Execution.bot_id == bot_id)
        .order_by(Execution.executed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': e.id,
            'ticker': e.ticker,
            'execution_type': e.execution_type,
            'quantity': e.quantity,
            'price': float(e.price),
            'fee': float(e.fee or 0),
            'tax': float(e.tax or 0),
            'profit_loss': float(e.profit_loss) if e.profit_loss is not None else None,
            'profit_loss_pct': float(e.profit_loss_pct) if e.profit_loss_pct is not None else None,
            'executed_at': e.executed_at,
        }
        for e in execs
    ]


@router.get("/bots/{bot_id}/reports")
def get_reports(
    bot_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    reports = trading_service.get_reports(db, bot_id, limit)
    return [
        {
            'id': r.id,
            'date': str(r.date),
            'total_assets': float(r.total_assets or 0),
            'cash': float(r.cash or 0),
            'holdings_value': float(r.holdings_value or 0),
            'daily_pnl': float(r.daily_pnl or 0),
            'total_pnl': float(r.total_pnl or 0),
            'win_rate': float(r.win_rate or 0),
            'total_trades': r.total_trades or 0,
            'max_drawdown': float(r.max_drawdown or 0),
            'sharpe_ratio': float(r.sharpe_ratio or 0),
            'profit_factor': float(r.profit_factor or 0),
        }
        for r in reports
    ]


@router.get("/bots/{bot_id}/performance")
def get_performance(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """봇 종합 성과 통계 (전체 누적 기준)"""
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    return trading_service.get_performance_stats(db, bot)
