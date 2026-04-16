"""
봇 실행 엔진
- 매 5분마다 RUNNING 상태 봇의 전략 조건을 체크
- 조건 충족 시 브로커(mock/kiwoom)를 통해 체결
- 손절/익절 조건 체크
- 장 마감 후 일별 보고서 생성
"""
import json
import logging
import math
import time as _time
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

import redis
from sqlalchemy import func

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
BOT_LAST_SIGNAL_KEY = "autostock:bot_last_signal:{bot_id}"  # 일봉 봇 중복 신호 방지

_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


# ── 공통 유틸 ──────────────────────────────────────────────────────────

def _calc_mdd(assets: list, initial: float) -> float:
    """최대 낙폭(%) 계산"""
    peak = initial
    max_dd = 0.0
    for a in assets:
        if a > peak:
            peak = a
        dd = (peak - a) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _calc_sharpe(daily_returns: list) -> float:
    """샤프 비율 계산 (연환산, clamp -999~999)"""
    if len(daily_returns) < 2:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    variance = sum((x - mean_r) ** 2 for x in daily_returns) / len(daily_returns)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return max(-999.0, min(999.0, mean_r / std_r * math.sqrt(252)))


def _retry_order(fn, ticker: str, side: str, max_retries: int = 2, delay: float = 1.5):
    """주문 실패 시 최대 max_retries회 재시도. 마지막 예외를 그대로 raise."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                logger.warning(
                    f"[bot_engine] {side} {ticker} 재시도 {attempt + 1}/{max_retries - 1}: {exc}"
                )
                _time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _latest_prices_map(db, tickers: list) -> dict:
    """종목 리스트의 최신 종가를 {ticker: StockPrice} dict로 반환 (2쿼리)"""
    if not tickers:
        return {}
    latest_date = (
        db.query(func.max(StockPrice.date))
        .filter(StockPrice.ticker.in_(tickers))
        .scalar()
    )
    if not latest_date:
        return {}
    return {
        sp.ticker: sp
        for sp in db.query(StockPrice)
        .filter(StockPrice.ticker.in_(tickers), StockPrice.date == latest_date)
        .all()
    }


@celery_app.task(name="tasks.bot_engine.run_all_bots")
def run_all_bots():
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(
            TradingBot.status == 'RUNNING',
            TradingBot.bot_type != 'scalping',
        ).all()
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
    # ── 중복 실행 방지: Celery 사이클이 겹칠 경우 선행 사이클이 끝날 때까지 스킵 ──
    lock_key = f"autostock:bot_cycle_lock:{bot.id}"
    acquired = _redis_client.set(lock_key, "1", nx=True, ex=360)  # 6분 TTL
    if not acquired:
        logger.info(f"[bot_engine] bot_id={bot.id} 이전 사이클 실행 중 — 스킵")
        return

    try:
        _run_cycle_inner(db, bot)
    finally:
        _redis_client.delete(lock_key)


def _run_cycle_inner(db, bot: TradingBot):
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

    # ── 루프 전 일괄 로드 (N+1 → 4쿼리) ──────────────────────────────
    price_map = _latest_prices_map(db, tickers)

    latest_ind_date = (
        db.query(func.max(TechnicalIndicator.date))
        .filter(TechnicalIndicator.ticker.in_(tickers))
        .scalar()
    )
    ind_map = {}
    prev_ind_map = {}
    if latest_ind_date:
        ind_map = {
            i.ticker: i
            for i in db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.ticker.in_(tickers), TechnicalIndicator.date == latest_ind_date)
            .all()
        }
        prev_ind_date = (
            db.query(func.max(TechnicalIndicator.date))
            .filter(TechnicalIndicator.ticker.in_(tickers), TechnicalIndicator.date < latest_ind_date)
            .scalar()
        )
        if prev_ind_date:
            prev_ind_map = {
                i.ticker: i
                for i in db.query(TechnicalIndicator)
                .filter(TechnicalIndicator.ticker.in_(tickers), TechnicalIndicator.date == prev_ind_date)
                .all()
            }

    position_map = {
        p.ticker: p
        for p in db.query(Position).filter(Position.bot_id == bot.id).all()
    }

    # 종목당 배분 예산: 초기자금 기준 고정 분배
    # total_portfolio(현재 평가액) 기준이면 수익 시 예산이 커져 비의도적 레버리지 발생
    per_pos_budget = float(bot.initial_cash) * float(bot.position_size_pct) / 100

    max_daily = int(bot.max_daily_trades)
    max_pos = int(bot.max_positions)

    # 브로커 초기화 및 잔고 사이클 시작 전 1회 검증
    # real/paper: 실패 시 stale 잔고로 주문하는 것을 막기 위해 사이클 전체 skip
    bot_mode = getattr(bot, 'mode', 'mock')
    broker = get_broker(bot_mode)
    if bot_mode in ('real', 'paper'):
        try:
            verified_cash = broker.get_available_cash()
            bot.cash = verified_cash
        except Exception as e:
            logger.error(
                f"[bot_engine] bot_id={bot.id} 잔고 조회 실패 — 사이클 전체 skip "
                f"(mode={bot_mode}, error={e!r})"
            )
            return

    for ticker in tickers:
        latest_price = price_map.get(ticker)
        if not latest_price:
            continue

        latest_ind = ind_map.get(ticker)
        prev_ind = prev_ind_map.get(ticker)
        position = position_map.get(ticker)

        rt = _redis_client.get(f"rt:price:{ticker}")
        if rt:
            curr_price = float(rt)
        else:
            curr_price = float(latest_price.close_price)
            if bot_mode in ('real', 'paper'):
                logger.warning(
                    f"[bot_engine] bot_id={bot.id} {ticker} 실시간가 없음 — 전일 종가 사용 "
                    f"({curr_price:,.0f}). 실시간 피드가 실행 중인지 확인하세요."
                )

        if position is None:
            # 매수 신호 체크
            if today_count >= max_daily:
                continue
            pos_count = len(position_map)
            if pos_count >= max_pos:
                continue

            # 일봉 봇: 종목당 하루 1회만 매수 신호 처리 (중복 매수 방지)
            last_signal_key = BOT_LAST_SIGNAL_KEY.format(bot_id=bot.id) + f":{ticker}"
            last_signal_date = _redis_client.get(last_signal_key)
            today_str = now_kr.date().isoformat()
            if last_signal_date == today_str:
                continue

            if _all_conditions_met(strategy.conditions, latest_ind, prev_ind):
                # 총 포트폴리오 기준 종목당 예산으로 수량 결정
                qty = int(per_pos_budget / curr_price)
                if qty <= 0:
                    continue
                fee = round(curr_price * qty * COMMISSION, 2)
                cost = curr_price * qty + fee
                if cost > float(bot.cash):
                    continue
                # 단일 주문 최대 금액 안전장치 (설정값과 per_pos_budget 중 작은 값)
                max_amt = float(bot.max_order_amount or 0)
                if max_amt > 0 and cost > min(max_amt, per_pos_budget * 1.1):
                    logger.warning(f"[bot_engine] bot_id={bot.id} {ticker} 주문 금액 초과 ({cost:,.0f} > budget:{per_pos_budget:,.0f})")
                    continue
                try:
                    result = _retry_order(lambda: broker.place_buy(bot.id, ticker, qty, curr_price), ticker, "BUY")
                    _execute_buy(db, bot, ticker, qty, result.filled_price, fee, result.order_number)
                    today_count += 1
                    # 오늘 신호 처리 완료 기록 (자정에 만료)
                    _redis_client.set(last_signal_key, today_str, ex=86400)
                    logger.info(f"[bot_engine] bot_id={bot.id} BUY {ticker} {qty}주 @{result.filled_price:,.0f}")
                except Exception as e:
                    logger.error(f"[bot_engine] BUY 최종 실패 {ticker}: {e}")
        else:
            # 손절/익절 체크
            avg = float(position.avg_price)
            pnl_pct = (curr_price - avg) / avg * 100
            if pnl_pct <= -float(bot.stop_loss_pct) or pnl_pct >= float(bot.take_profit_pct):
                try:
                    result = _retry_order(lambda: broker.place_sell(bot.id, ticker, position.quantity, curr_price), ticker, "SELL")
                    _execute_sell(db, bot, position, result.filled_price, result.order_number)
                    today_count += 1
                    logger.info(f"[bot_engine] bot_id={bot.id} SELL {ticker} pnl={pnl_pct:.1f}%")
                except Exception as e:
                    logger.error(f"[bot_engine] SELL 최종 실패 {ticker}: {e}")

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
    cost_basis = avg * qty
    profit_loss_pct = round(profit_loss / cost_basis * 100, 4) if cost_basis else 0.0

    order = Order(bot_id=bot.id, ticker=position.ticker, order_type='SELL',
                  quantity=qty, price=price, status='FILLED',
                  order_number=order_number, created_at=now)
    db.add(order)
    db.flush()
    db.add(Execution(
        order_id=order.id, bot_id=bot.id, ticker=position.ticker,
        execution_type='SELL', quantity=qty, price=price,
        fee=fee, tax=tax, profit_loss=profit_loss,
        profit_loss_pct=profit_loss_pct, executed_at=now,
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
    if positions:
        price_map = _latest_prices_map(db, [p.ticker for p in positions])
        holdings = sum(float(price_map[p.ticker].close_price) * p.quantity
                       for p in positions if p.ticker in price_map)
    else:
        holdings = 0.0
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
            if positions:
                price_map = _latest_prices_map(db, [p.ticker for p in positions])
                holdings = sum(float(price_map[p.ticker].close_price) * p.quantity
                               for p in positions if p.ticker in price_map)
            else:
                holdings = 0.0

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

            # MDD / 샤프: 누적 보고서 이력 기반
            initial = float(bot.initial_cash or 1)
            all_reports = db.query(BotReport).filter(
                BotReport.bot_id == bot.id
            ).order_by(BotReport.date).all()
            assets_series = [float(r.total_assets or 0) for r in all_reports] + [total]
            max_dd = _calc_mdd(assets_series, initial)

            daily_returns = []
            prev_a = initial
            for r in all_reports:
                ta = float(r.total_assets or 0)
                if prev_a > 0:
                    daily_returns.append((ta - prev_a) / prev_a * 100)
                prev_a = ta
            sharpe = _calc_sharpe(daily_returns)

            # 손익비: 누적 전체 매도 체결 기준
            all_sells = db.query(Execution).filter(
                Execution.bot_id == bot.id,
                Execution.execution_type == 'SELL',
            ).all()
            total_gain = sum(float(e.profit_loss) for e in all_sells if (e.profit_loss or 0) > 0)
            total_loss = sum(abs(float(e.profit_loss)) for e in all_sells if (e.profit_loss or 0) < 0)
            profit_factor = round(total_gain / total_loss, 4) if total_loss > 0 else (
                round(total_gain, 4) if total_gain > 0 else 0.0
            )

            safe_sharpe = max(-999.0, min(999.0, sharpe))
            safe_pf = max(0.0, min(999.0, profit_factor))
            try:
                db.add(BotReport(
                    bot_id=bot.id, date=today,
                    total_assets=round(total, 2), cash=round(cash, 2),
                    holdings_value=round(holdings, 2),
                    daily_pnl=round(daily_pnl, 2), total_pnl=round(total_pnl, 2),
                    win_rate=round(win_rate, 2), total_trades=len(today_sells),
                    max_drawdown=round(max_dd, 4),
                    sharpe_ratio=round(safe_sharpe, 4),
                    profit_factor=round(safe_pf, 4),
                ))
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[bot_engine] bot_id={bot.id} 보고서 저장 실패: {e}")

        logger.info(f"[bot_engine] 일별 보고서 생성: {len(bots)}개 봇")
    finally:
        db.close()
