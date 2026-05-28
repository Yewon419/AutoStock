"""
대시보드 집계 API
- 봇 상태 현황 (RUNNING/STOPPED/ERROR 수)
- 전체 봇 총 자산 합계
- 오늘 PnL 합계
- 최근 알림
"""
import json
from datetime import date, datetime, time, timezone

import redis
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from models.trading import TradingBot, BotReport, Position, Execution
from models.market import StockPrice

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ALERTS_KEY = "autostock:alerts"


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = int(current_user['sub'])
    bots = db.query(TradingBot).filter(TradingBot.user_id == user_id).all()

    running = sum(1 for b in bots if b.status == 'RUNNING')
    stopped = sum(1 for b in bots if b.status == 'STOPPED')
    error = sum(1 for b in bots if b.status == 'ERROR')

    # 전체 총 자산 계산 (mock / paper / real 분리) — BotDetailView와 동일한 rt:price→StockPrice→avg 3단 fallback
    from services import trading_service
    total_assets = 0.0
    total_pnl = 0.0
    mock_assets = 0.0
    mock_pnl = 0.0
    paper_assets = 0.0
    paper_pnl = 0.0
    real_assets = 0.0
    real_pnl = 0.0
    enriched_bots = []
    for bot in bots:
        enriched = trading_service.enrich_bot_assets(db, bot)
        enriched_bots.append(enriched)
        bot_total = float(enriched['total_assets'])
        bot_pnl = bot_total - float(bot.initial_cash or 0)
        total_assets += bot_total
        total_pnl += bot_pnl
        mode = getattr(bot, 'mode', 'mock') or 'mock'
        if mode == 'paper':
            paper_assets += bot_total
            paper_pnl += bot_pnl
        elif mode == 'real':
            real_assets += bot_total
            real_pnl += bot_pnl
        else:
            mock_assets += bot_total
            mock_pnl += bot_pnl

    # 오늘 거래 수 및 일일 PnL
    today = date.today()
    today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    today_sells = db.query(Execution).join(
        TradingBot, Execution.bot_id == TradingBot.id
    ).filter(
        TradingBot.user_id == user_id,
        Execution.execution_type == 'SELL',
        Execution.executed_at >= today_start,
    ).all()
    daily_realized_pnl = sum(float(e.profit_loss or 0) for e in today_sells)
    # 당일 평가손익: 봇별 today_evaluation_pnl 합 — enrich_bot_assets에서 이미 계산됨
    daily_evaluation_pnl = sum(float(b.get('today_evaluation_pnl') or 0) for b in enriched_bots)
    daily_pnl = daily_realized_pnl + daily_evaluation_pnl
    today_trades = db.query(Execution).join(
        TradingBot, Execution.bot_id == TradingBot.id
    ).filter(
        TradingBot.user_id == user_id,
        Execution.executed_at >= today_start,
    ).count()

    # 알림 (최근 5개)
    r = redis.from_url(settings.REDIS_URL)
    raw_alerts = r.lrange(ALERTS_KEY, 0, 4)
    alerts = []
    for item in raw_alerts:
        try:
            alerts.append(json.loads(item))
        except Exception:
            pass

    return {
        "bot_count": len(bots),
        "running": running,
        "stopped": stopped,
        "error": error,
        "total_assets": round(total_assets, 0),
        "total_pnl": round(total_pnl, 0),
        "mock_assets": round(mock_assets, 0),
        "mock_pnl": round(mock_pnl, 0),
        "paper_assets": round(paper_assets, 0),
        "paper_pnl": round(paper_pnl, 0),
        "real_assets": round(real_assets, 0),
        "real_pnl": round(real_pnl, 0),
        "daily_pnl": round(daily_pnl, 0),
        "daily_realized_pnl": round(daily_realized_pnl, 0),
        "daily_evaluation_pnl": round(daily_evaluation_pnl, 0),
        "today_trades": today_trades,
        "alerts": alerts,
    }


@router.get("/bots")
def get_bot_snapshots(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """각 봇의 현재 자산 스냅샷 목록"""
    user_id = int(current_user['sub'])
    bots = db.query(TradingBot).filter(TradingBot.user_id == user_id).order_by(TradingBot.id).all()

    result = []
    for bot in bots:
        cash = float(bot.cash or 0)
        positions = db.query(Position).filter(Position.bot_id == bot.id).all()
        holdings = 0.0
        for pos in positions:
            lp = db.query(StockPrice).filter(StockPrice.ticker == pos.ticker).order_by(StockPrice.date.desc()).first()
            if lp and lp.close_price is not None:
                holdings += float(lp.close_price) * pos.quantity

        total = cash + holdings
        pnl = total - float(bot.initial_cash or 0)
        pnl_pct = pnl / float(bot.initial_cash or 1) * 100

        result.append({
            "id": bot.id,
            "name": bot.name,
            "status": bot.status,
            "mode": getattr(bot, 'mode', 'mock'),
            "total_assets": round(total, 0),
            "pnl": round(pnl, 0),
            "pnl_pct": round(pnl_pct, 2),
            "position_count": len(positions),
        })

    return result


@router.get("/today-trades")
def get_today_trades(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """오늘 체결된 거래 목록 (봇 이름 포함)"""
    user_id = int(current_user['sub'])
    today = date.today()
    today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)

    rows = (
        db.query(Execution, TradingBot.name.label("bot_name"), TradingBot.mode.label("bot_mode"))
        .join(TradingBot, Execution.bot_id == TradingBot.id)
        .filter(
            TradingBot.user_id == user_id,
            Execution.executed_at >= today_start,
        )
        .order_by(Execution.executed_at.desc())
        .all()
    )

    result = []
    for e, bot_name, bot_mode in rows:
        result.append({
            "id": e.id,
            "bot_id": e.bot_id,
            "bot_name": bot_name,
            "bot_mode": bot_mode or "mock",
            "ticker": e.ticker,
            "execution_type": e.execution_type,
            "quantity": e.quantity,
            "price": float(e.price),
            "profit_loss": float(e.profit_loss) if e.profit_loss is not None else None,
            "profit_loss_pct": float(e.profit_loss_pct) if e.profit_loss_pct is not None else None,
            "executed_at": e.executed_at.isoformat() if e.executed_at else None,
        })
    return result
