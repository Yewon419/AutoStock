"""
봇 실행 엔진
- 매 5분마다 RUNNING 상태 봇의 전략 조건을 체크
- 조건 충족 시 브로커(mock/kiwoom)를 통해 체결
- 손절/익절 조건 체크
- 장 마감 후 일별 보고서 생성
"""
import json
import logging
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

import redis

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Order, Execution, Position, BotReport
from models.market import StockPrice, TechnicalIndicator
from models.strategy import Strategy
from services.backtest_engine import _all_conditions_met
from broker.factory import get_broker

logger = logging.getLogger(__name__)

SEOUL = ZoneInfo('Asia/Seoul')
COMMISSION = 0.00015  # 매수/매도 0.015%
TAX = 0.002           # 증권거래세 0.2% (매도 시)
ALERTS_KEY = "autostock:alerts"


@celery_app.task(name="tasks.bot_engine.run_all_bots")
def run_all_bots():
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(TradingBot.status == 'RUNNING').all()
        if not bots:
            return
        logger.info(f"[bot_engine] 실행 봇: {len(bots)}개")
        for bot in bots:
            try:
                _run_cycle(db, bot)
            except Exception as e:
                logger.error(f"[bot_engine] bot_id={bot.id} 오류: {e}", exc_info=True)
                bot.status = 'ERROR'
                db.commit()
                _push_alert(bot.id, bot.name, 'ERROR', str(e))
    finally:
        db.close()


def _run_cycle(db, bot: TradingBot):
    now_kr = datetime.now(tz=SEOUL)
    now_t = now_kr.time().replace(tzinfo=None)

    # 거래 시간 체크
    start_t = bot.trading_start_time
    end_t = bot.trading_end_time
    if start_t and end_t and not (start_t <= now_t <= end_t):
        return

    strategy = db.query(Strategy).filter(Strategy.id == bot.strategy_id).first()
    if not strategy:
        return

    tickers = bot.tickers or []
    if not tickers:
        return

    # 최대 낙폭 체크
    if _exceeds_max_drawdown(db, bot):
        bot.status = 'ERROR'
        logger.warning(f"[bot_engine] bot_id={bot.id} 최대 낙폭 초과 → ERROR")
        db.commit()
        _push_alert(bot.id, bot.name, 'MAX_DRAWDOWN', '최대 낙폭 초과로 봇이 정지되었습니다')
        return

    # 오늘 거래 수
    today_start = datetime.combine(now_kr.date(), time.min, tzinfo=timezone.utc)
    today_count = db.query(Order).filter(
        Order.bot_id == bot.id,
        Order.created_at >= today_start,
    ).count()

    for ticker in tickers:
        latest_price = (
            db.query(StockPrice)
            .filter(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .first()
        )
        if not latest_price:
            continue

        latest_ind = (
            db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.ticker == ticker)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        prev_ind = None
        if latest_ind:
            prev_ind = (
                db.query(TechnicalIndicator)
                .filter(
                    TechnicalIndicator.ticker == ticker,
                    TechnicalIndicator.date < latest_ind.date,
                )
                .order_by(TechnicalIndicator.date.desc())
                .first()
            )

        position = db.query(Position).filter(
            Position.bot_id == bot.id,
            Position.ticker == ticker,
        ).first()

        curr_price = float(latest_price.close_price)

        if position is None:
            # 매수 신호 체크
            if today_count >= int(bot.max_daily_trades):
                continue
            pos_count = db.query(Position).filter(Position.bot_id == bot.id).count()
            if pos_count >= int(bot.max_positions):
                continue
            if _all_conditions_met(strategy.conditions, latest_ind, prev_ind):
                qty = int(float(bot.cash) * float(bot.position_size_pct) / 100 / curr_price)
                if qty <= 0:
                    continue
                fee = round(curr_price * qty * COMMISSION, 2)
                cost = curr_price * qty + fee
                if cost > float(bot.cash):
                    continue
                # 단일 주문 최대 금액 체크 (real/paper 모드 안전장치)
                max_amt = float(bot.max_order_amount or 0)
                if max_amt > 0 and cost > max_amt:
                    logger.warning(f"[bot_engine] bot_id={bot.id} {ticker} 주문 금액 초과 ({cost:,.0f} > {max_amt:,.0f})")
                    continue
                try:
                    broker = get_broker(getattr(bot, 'mode', 'mock'))
                    result = broker.place_buy(bot.id, ticker, qty, curr_price)
                    _execute_buy(db, bot, ticker, qty, result.filled_price, fee, result.order_number)
                    today_count += 1
                    logger.info(f"[bot_engine] bot_id={bot.id} BUY {ticker} {qty}주 @{result.filled_price:,.0f}")
                except Exception as e:
                    logger.error(f"[bot_engine] BUY 실패 {ticker}: {e}")
        else:
            # 손절/익절 체크
            avg = float(position.avg_price)
            pnl_pct = (curr_price - avg) / avg * 100
            if pnl_pct <= -float(bot.stop_loss_pct) or pnl_pct >= float(bot.take_profit_pct):
                try:
                    broker = get_broker(getattr(bot, 'mode', 'mock'))
                    result = broker.place_sell(bot.id, ticker, position.quantity, curr_price)
                    _execute_sell(db, bot, position, result.filled_price, result.order_number)
                    today_count += 1
                    logger.info(f"[bot_engine] bot_id={bot.id} SELL {ticker} pnl={pnl_pct:.1f}%")
                except Exception as e:
                    logger.error(f"[bot_engine] SELL 실패 {ticker}: {e}")

    db.commit()


def _execute_buy(db, bot, ticker, qty, price, fee, order_number=None):
    now = datetime.now(tz=timezone.utc)
    order = Order(bot_id=bot.id, ticker=ticker, order_type='BUY',
                  quantity=qty, price=price, status='FILLED',
                  order_number=order_number, created_at=now)
    db.add(order)
    db.flush()
    db.add(Execution(
        order_id=order.id, bot_id=bot.id, ticker=ticker,
        execution_type='BUY', quantity=qty, price=price,
        fee=fee, tax=0, executed_at=now,
    ))
    db.add(Position(bot_id=bot.id, ticker=ticker, quantity=qty, avg_price=price))
    bot.cash = float(bot.cash) - (price * qty + fee)


def _execute_sell(db, bot, position, price, order_number=None):
    now = datetime.now(tz=timezone.utc)
    qty = position.quantity
    fee = round(price * qty * COMMISSION, 2)
    tax = round(price * qty * TAX, 2)
    avg = float(position.avg_price)
    profit_loss = round((price - avg) * qty - fee - tax, 2)

    order = Order(bot_id=bot.id, ticker=position.ticker, order_type='SELL',
                  quantity=qty, price=price, status='FILLED',
                  order_number=order_number, created_at=now)
    db.add(order)
    db.flush()
    db.add(Execution(
        order_id=order.id, bot_id=bot.id, ticker=position.ticker,
        execution_type='SELL', quantity=qty, price=price,
        fee=fee, tax=tax, profit_loss=profit_loss, executed_at=now,
    ))
    bot.cash = float(bot.cash) + (price * qty - fee - tax)
    db.delete(position)


def _push_alert(bot_id: int, bot_name: str, alert_type: str, message: str):
    """Redis에 알림 저장 (최근 100개 유지)"""
    try:
        r = redis.from_url(settings.REDIS_URL)
        payload = json.dumps({
            'bot_id': bot_id,
            'bot_name': bot_name,
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
        }, ensure_ascii=False)
        r.lpush(ALERTS_KEY, payload)
        r.ltrim(ALERTS_KEY, 0, 99)
    except Exception as e:
        logger.error(f"[bot_engine] 알림 저장 실패: {e}")


def _exceeds_max_drawdown(db, bot) -> bool:
    initial = float(bot.initial_cash or 0)
    if initial <= 0:
        return False
    cash = float(bot.cash or 0)
    positions = db.query(Position).filter(Position.bot_id == bot.id).all()
    holdings = 0.0
    for pos in positions:
        lp = db.query(StockPrice).filter(StockPrice.ticker == pos.ticker).order_by(StockPrice.date.desc()).first()
        if lp:
            holdings += float(lp.close_price) * pos.quantity
    total = cash + holdings
    drawdown = (initial - total) / initial * 100
    return drawdown >= float(bot.max_drawdown_pct)


@celery_app.task(name="tasks.bot_engine.generate_daily_reports")
def generate_daily_reports():
    db = SessionLocal()
    try:
        today = date.today()
        bots = db.query(TradingBot).filter(
            TradingBot.status.in_(['RUNNING', 'STOPPED', 'ERROR'])
        ).all()

        for bot in bots:
            existing = db.query(BotReport).filter(
                BotReport.bot_id == bot.id, BotReport.date == today
            ).first()
            if existing:
                continue

            cash = float(bot.cash or 0)
            positions = db.query(Position).filter(Position.bot_id == bot.id).all()
            holdings = 0.0
            for pos in positions:
                lp = db.query(StockPrice).filter(StockPrice.ticker == pos.ticker).order_by(StockPrice.date.desc()).first()
                if lp:
                    holdings += float(lp.close_price) * pos.quantity

            total = cash + holdings
            total_pnl = total - float(bot.initial_cash or 0)

            today_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
            today_sells = db.query(Execution).filter(
                Execution.bot_id == bot.id,
                Execution.execution_type == 'SELL',
                Execution.executed_at >= today_start,
            ).all()
            daily_pnl = sum(float(e.profit_loss or 0) for e in today_sells)
            wins = sum(1 for e in today_sells if float(e.profit_loss or 0) > 0)
            win_rate = wins / len(today_sells) * 100 if today_sells else 0

            db.add(BotReport(
                bot_id=bot.id, date=today,
                total_assets=round(total, 2), cash=round(cash, 2),
                holdings_value=round(holdings, 2),
                daily_pnl=round(daily_pnl, 2), total_pnl=round(total_pnl, 2),
                win_rate=round(win_rate, 2), total_trades=len(today_sells),
            ))

        db.commit()
        logger.info(f"[bot_engine] 일별 보고서 생성: {len(bots)}개 봇")
    finally:
        db.close()
