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
    total_assets: Optional[float] = None
    holdings_value: Optional[float] = None
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
    bots = trading_service.get_bots(db, _user_id(current_user))
    return [trading_service.enrich_bot_assets(db, b) for b in bots]


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


def _score_bot(perf: dict, reports: list) -> dict:
    """봇 성과를 happystocklife 방식의 5개 카테고리로 100점 평가"""
    total_return_pct = perf.get('total_return_pct', 0)
    sharpe = perf.get('sharpe_ratio', 0)
    max_dd = perf.get('max_drawdown', 0)        # 양수 %
    win_rate = perf.get('win_rate', 0) / 100    # 0~1
    profit_factor = perf.get('profit_factor', 0)
    avg_win = perf.get('avg_win', 0)
    avg_loss = abs(perf.get('avg_loss', -1) or -1)
    total_trades = perf.get('total_trades', 0)

    # reports 기반 일관성 보조 지표
    winning_days_pct = 0.0
    max_consec_loss = 0
    if reports:
        daily_pnls = [r['daily_pnl'] for r in reports]
        if daily_pnls:
            winning_days_pct = sum(1 for x in daily_pnls if x > 0) / len(daily_pnls)
        curr = 0
        for d in daily_pnls:
            if d < 0:
                curr += 1
                if curr > max_consec_loss:
                    max_consec_loss = curr
            else:
                curr = 0

    def clamp(v): return max(0.0, min(100.0, v))

    # ── 수익률 점수 (30%) ──────────────────────────────────────────
    r = total_return_pct
    if r >= 15:     return_s = 100.0
    elif r >= 10:   return_s = 70 + (r - 10) / 5 * 30
    elif r >= 5:    return_s = 45 + (r - 5)  / 5 * 25
    elif r >= 0:    return_s = 25 + r / 5 * 20
    else:           return_s = max(0, 25 + r * 2.5)
    # 샤프 보너스
    if sharpe >= 1.5:
        return_s = min(100, return_s + 10)
    return_s = clamp(return_s)

    # ── 리스크 점수 (25%) ─────────────────────────────────────────
    if sharpe >= 2.0:     sharpe_s = 100.0
    elif sharpe >= 1.0:   sharpe_s = 65 + (sharpe - 1.0) / 1.0 * 35
    elif sharpe >= 0.5:   sharpe_s = 40 + (sharpe - 0.5) / 0.5 * 25
    elif sharpe >= 0:     sharpe_s = sharpe / 0.5 * 40
    else:                 sharpe_s = max(0, 20 + sharpe * 10)
    sharpe_s = clamp(sharpe_s)

    dd = max_dd
    if dd <= 5:     mdd_s = 100.0
    elif dd <= 10:  mdd_s = 70 + (10 - dd) / 5  * 30
    elif dd <= 20:  mdd_s = 35 + (20 - dd) / 10 * 35
    elif dd <= 30:  mdd_s = max(0, 35 - (dd - 20) / 10 * 35)
    else:           mdd_s = 0.0
    mdd_s = clamp(mdd_s)

    risk_s = clamp(sharpe_s * 0.6 + mdd_s * 0.4)

    # ── 안정성 점수 (20%) ─────────────────────────────────────────
    wd = winning_days_pct
    if wd >= 0.6:     wd_s = 100.0
    elif wd >= 0.5:   wd_s = 65 + (wd - 0.5) / 0.1 * 35
    elif wd >= 0.4:   wd_s = 35 + (wd - 0.4) / 0.1 * 30
    else:             wd_s = max(0, wd / 0.4 * 35)
    wd_s = clamp(wd_s)

    stability_s = clamp(mdd_s * 0.5 + wd_s * 0.5)

    # ── 일관성 점수 (15%) ─────────────────────────────────────────
    if win_rate >= 0.6:   wr_s = 100.0
    elif win_rate >= 0.5: wr_s = 65 + (win_rate - 0.5) / 0.1 * 35
    elif win_rate >= 0.4: wr_s = 35 + (win_rate - 0.4) / 0.1 * 30
    else:                 wr_s = max(0, win_rate / 0.4 * 35)
    wr_s = clamp(wr_s)

    mcl = max_consec_loss
    if mcl <= 2:    mcl_s = 100.0
    elif mcl <= 5:  mcl_s = 60 - (mcl - 2) / 3 * 20
    elif mcl <= 10: mcl_s = max(0, 40 - (mcl - 5) / 5 * 40)
    else:           mcl_s = 0.0
    mcl_s = clamp(mcl_s)

    if total_trades >= 20:   tr_s = 100.0
    elif total_trades >= 10: tr_s = 50 + (total_trades - 10) / 10 * 50
    elif total_trades >= 5:  tr_s = 25 + (total_trades - 5)  / 5  * 25
    else:                    tr_s = total_trades / 5 * 25 if total_trades else 0
    tr_s = clamp(tr_s)

    consistency_s = clamp(wr_s * 0.5 + mcl_s * 0.3 + tr_s * 0.2)

    # ── 효율성 점수 (10%) ─────────────────────────────────────────
    pf = profit_factor
    if pf >= 2.0:   pf_s = 100.0
    elif pf >= 1.5: pf_s = 65 + (pf - 1.5) / 0.5 * 35
    elif pf >= 1.0: pf_s = 35 + (pf - 1.0) / 0.5 * 30
    else:           pf_s = max(0, pf / 1.0 * 35)
    pf_s = clamp(pf_s)

    rr = avg_win / avg_loss if avg_loss > 0 else (1.0 if avg_win > 0 else 0.0)
    if rr >= 3:     rr_s = 100.0
    elif rr >= 2:   rr_s = 65 + (rr - 2) / 1 * 35
    elif rr >= 1.5: rr_s = 35 + (rr - 1.5) / 0.5 * 30
    else:           rr_s = max(0, rr / 1.5 * 35)
    rr_s = clamp(rr_s)

    efficiency_s = clamp(pf_s * 0.6 + rr_s * 0.4)

    # ── 종합 ──────────────────────────────────────────────────────
    total_s = (
        return_s * 0.30 + risk_s * 0.25 +
        stability_s * 0.20 + consistency_s * 0.15 + efficiency_s * 0.10
    )
    total_s = clamp(total_s)

    if total_s >= 90:   grade = 'S'
    elif total_s >= 80: grade = 'A'
    elif total_s >= 70: grade = 'B'
    elif total_s >= 60: grade = 'C'
    elif total_s >= 50: grade = 'D'
    else:               grade = 'F'

    categories = {
        '수익률':    round(return_s, 1),
        '리스크 관리': round(risk_s, 1),
        '안정성':    round(stability_s, 1),
        '일관성':    round(consistency_s, 1),
        '거래 효율': round(efficiency_s, 1),
    }
    strengths    = [f"{k} 우수 ({v}점)" for k, v in categories.items() if v >= 75]
    weaknesses   = [f"{k} 개선 필요 ({v}점)" for k, v in categories.items() if v < 50]
    if not strengths:   strengths  = ["전반적으로 균형잡힌 성과"]
    if not weaknesses:  weaknesses = ["특별한 약점 없음"]

    recs = []
    if return_s < 50:
        recs.append("수익률 개선: 손절/익절 비율 또는 진입 조건을 최적화하세요")
    if sharpe < 1.0:
        recs.append("리스크 대비 수익 개선: 변동성 높은 종목 비중을 줄여보세요")
    if max_dd > 15:
        recs.append(f"낙폭 관리: 최대 낙폭 {max_dd:.1f}%로 높습니다. 포지션 크기 축소를 고려하세요")
    if win_rate < 0.45:
        recs.append(f"승률 개선: 현재 승률 {win_rate*100:.1f}%로 낮습니다. 진입 조건을 더 엄격히 하세요")
    if profit_factor < 1.2:
        recs.append("손익비 개선: 익절 목표를 높이거나 손절 기준을 엄격히 설정하세요")
    if not recs:
        recs.append("현재 전략을 유지하며 정기적으로 성과를 모니터링하세요")

    grade_emojis = {'S': '💎', 'A': '🌟', 'B': '✨', 'C': '⚠️', 'D': '📉', 'F': '🚨'}
    emoji = grade_emojis.get(grade, '')
    ts = round(total_s, 1)
    if ts >= 90:   summary = f"{emoji} 최상급 전략입니다. 샤프 비율 {sharpe:.2f}로 탁월한 리스크 대비 수익을 달성했습니다."
    elif ts >= 80: summary = f"{emoji} 우수한 전략입니다. 샤프 비율 {sharpe:.2f}로 리스크 대비 높은 수익을 달성했습니다."
    elif ts >= 70: summary = f"{emoji} 양호한 전략입니다. 전반적으로 안정적인 성과를 보였으나 일부 개선 여지가 있습니다."
    elif ts >= 60: summary = f"{emoji} 보통 수준의 전략입니다. 일부 지표에서 개선이 필요합니다."
    elif ts >= 50: summary = f"{emoji} 개선이 필요한 전략입니다. 리스크 관리 및 수익률 최적화가 시급합니다."
    else:          summary = f"{emoji} 재검토가 필요한 전략입니다. 전면적인 전략 수정을 권장합니다."

    return {
        "total_score": ts,
        "grade": grade,
        "categories": categories,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recs,
        "summary": summary,
        "meta": {
            "total_return_pct": round(total_return_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "win_rate": round(win_rate * 100, 1),
            "profit_factor": round(profit_factor, 2),
            "winning_days_pct": round(winning_days_pct * 100, 1),
            "max_consecutive_losses": max_consec_loss,
        },
    }


_MIN_TRADES_FOR_SCORE = 5
_MIN_REPORTS_FOR_SCORE = 3

@router.get("/bots/{bot_id}/report-score")
def get_report_score(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """봇 성과를 100점 만점으로 평가 (5개 카테고리) — 데이터 부족 시 insufficient 반환"""
    bot = trading_service.get_bot(db, bot_id, _user_id(current_user))
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="봇을 찾을 수 없습니다")
    perf = trading_service.get_performance_stats(db, bot)
    reports_raw = trading_service.get_reports(db, bot_id, limit=90)

    total_trades = perf.get('total_trades', 0)
    num_reports = len(reports_raw)

    if total_trades < _MIN_TRADES_FOR_SCORE:
        return {
            "insufficient": True,
            "reason": f"체결 거래 {total_trades}건 — 평가에 최소 {_MIN_TRADES_FOR_SCORE}건 필요합니다",
        }
    if num_reports < _MIN_REPORTS_FOR_SCORE:
        return {
            "insufficient": True,
            "reason": f"일별 보고서 {num_reports}일치 — 평가에 최소 {_MIN_REPORTS_FOR_SCORE}일 필요합니다",
        }

    reports = [{'daily_pnl': float(r.daily_pnl or 0)} for r in reports_raw]
    return _score_bot(perf, reports)
