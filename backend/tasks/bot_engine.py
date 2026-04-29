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
from datetime import datetime, date, time, timezone, timedelta
from zoneinfo import ZoneInfo

import redis
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Order, Execution, Position, BotReport
from models.market import StockPrice, TechnicalIndicator
from models.strategy import Strategy
from services.backtest_engine import _all_conditions_met
from broker.factory import get_broker
from broker.base import (
    FILL_FILLED, FILL_PARTIAL, FILL_PENDING, FILL_REJECTED, FILL_CANCELLED, FILL_UNKNOWN,
)

logger = logging.getLogger(__name__)

SEOUL = ZoneInfo('Asia/Seoul')
COMMISSION = 0.00015  # 매수/매도 0.015%
TAX = 0.002           # 증권거래세 0.2% (매도 시)
ALERTS_KEY = "autostock:alerts"
BOT_LAST_SIGNAL_KEY = "autostock:bot_last_signal:{bot_id}"  # 일봉 봇 중복 신호 방지

# KIS 비동기 주문 폴링 설정
FILL_POLL_DELAY_SEC = 3           # place 후 체결조회 대기 시간
PENDING_ORDER_TIMEOUT_MIN = 15    # PENDING 유지 허용 시간, 초과 시 TIMEOUT 마킹

# Order.status 상수 — DB 컬럼 VARCHAR(20)
ORDER_SUBMITTED = 'SUBMITTED'
ORDER_PENDING = 'PENDING'
ORDER_FILLED = 'FILLED'
ORDER_PARTIAL = 'PARTIAL'
ORDER_REJECTED = 'REJECTED'
ORDER_CANCELLED = 'CANCELLED'
ORDER_TIMEOUT = 'TIMEOUT'
ORDER_FAILED = 'FAILED'

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


def _cumulative_filled(db, order_id: int) -> int:
    """해당 Order가 지금까지 실제 체결된 수량 합계 (Execution 테이블 sum).

    KIS의 check_order_fill은 누적 체결 수량(tot_ccld_qty)을 반환. 여러 번 polling해도
    같은 누적값이 들어오므로 delta 계산을 위해 이전 기록 합을 알아야 함.
    """
    total = db.query(func.coalesce(func.sum(Execution.quantity), 0)).filter(
        Execution.order_id == order_id
    ).scalar()
    return int(total or 0)


def _upsert_position(db, bot_id: int, ticker: str, add_qty: int, add_price: float) -> None:
    """같은 (bot_id, ticker) Position이 있으면 가중평균 합산, 없으면 신규 insert.

    UNIQUE(bot_id, ticker) 제약 위반 방지. SELECT-then-insert 사이의 race는
    savepoint(begin_nested) + IntegrityError 캐치 → 재조회 update로 처리해
    바깥 트랜잭션의 다른 변경을 손실하지 않음.
    """
    def _apply_add(existing_row):
        exist_qty = int(existing_row.quantity)
        exist_avg = float(existing_row.avg_price)
        new_qty = exist_qty + add_qty
        if new_qty > 0:
            new_avg = (exist_qty * exist_avg + add_qty * add_price) / new_qty
            existing_row.quantity = new_qty
            existing_row.avg_price = round(new_avg, 2)

    existing = db.query(Position).filter(
        Position.bot_id == bot_id, Position.ticker == ticker
    ).first()
    if existing:
        _apply_add(existing)
        return

    try:
        with db.begin_nested():
            db.add(Position(
                bot_id=bot_id, ticker=ticker,
                quantity=add_qty, avg_price=add_price,
            ))
    except IntegrityError:
        # 동시 race로 같은 (bot_id, ticker) row가 선점됨 → 재조회 후 update.
        # savepoint가 rollback되어 바깥 트랜잭션은 유지됨.
        existing = db.query(Position).filter(
            Position.bot_id == bot_id, Position.ticker == ticker
        ).first()
        if existing:
            _apply_add(existing)
        else:
            logger.error(
                f"[bot_engine] _upsert_position IntegrityError but row not found "
                f"bot_id={bot_id} ticker={ticker}"
            )


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


# ── 비동기 주문 처리 ──────────────────────────────────────────────────
#
# 실거래(KIS) 주문은 접수 → 체결이 비동기이므로 다음 순서로 분리 처리:
#   1. broker.place_buy/sell() → Order(status=SUBMITTED) 저장 + 커밋 (복구용 idempotent 기록)
#   2. FILL_POLL_DELAY_SEC 대기 후 broker.check_order_fill(ODNO) 조회
#   3. 체결/부분체결 → Execution + Position 갱신, 미체결 → PENDING 유지 → 다음 사이클 reconcile
#
# Mock은 OrderResult.immediate_fill이 세팅되어 있어 즉시 완결.


def _pending_order_sets(db, bot_id: int) -> tuple[set, set]:
    """현재 미완료(SUBMITTED/PENDING/PARTIAL) 주문의 티커를 BUY/SELL 분리 반환.

    PARTIAL도 포함 — 부분 체결 주문은 나머지가 아직 미체결이므로 동일 ticker에
    중복 접수 방지 대상. 사이클 내 중복 주문 차단 용도.
    """
    rows = db.query(Order.ticker, Order.order_type).filter(
        Order.bot_id == bot_id,
        Order.status.in_([ORDER_SUBMITTED, ORDER_PENDING, ORDER_PARTIAL]),
    ).all()
    buy = {t for t, s in rows if s == 'BUY'}
    sell = {t for t, s in rows if s == 'SELL'}
    return buy, sell


def _save_submitted_order(db, bot: TradingBot, ticker: str, side: str,
                           qty: int, submitted_price: float, order_number) -> int:
    """브로커 접수 성공 직후 Order를 SUBMITTED로 저장. 복구 경로 확보용 즉시 commit.

    실패 시 rollback하고 예외 전파 — 호출자가 fallback 알림 처리.
    """
    now = datetime.now(tz=timezone.utc)
    order = Order(
        bot_id=bot.id, ticker=ticker, order_type=side,
        quantity=qty, price=submitted_price, status=ORDER_SUBMITTED,
        order_number=order_number, created_at=now,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order.id


def _finalize_buy(db, bot: TradingBot, order_id: int,
                   submitted_qty: int, submitted_price: float,
                   fill_status: str, filled_qty: int, avg_price: float,
                   skip_cash_adjust: bool = False) -> None:
    """체결 결과를 반영해 Order/Execution/Position/bot.cash 갱신.

    filled_qty는 브로커가 반환하는 **누적** 체결 수량. 이미 기록된 Execution 합계와 비교해
    순증 delta만 처리 → partial fill 다중 polling 시 중복 방지.

    skip_cash_adjust=True면 bot.cash 조정을 생략 — real/paper 모드의 reconcile 경로에서
    broker.get_available_cash()로 이미 잔고가 동기화된 경우 이중 차감 방지.

    Order.quantity는 원 주문 수량(submitted_qty)을 유지해 추후 remainder 추적 가능.
    누적 체결이 submitted_qty에 도달하면 status=FILLED, 아니면 PARTIAL (reconcile 대상 유지).
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.error(f"[bot_engine] _finalize_buy: Order id={order_id} 없음")
        return

    try:
        if fill_status in (FILL_FILLED, FILL_PARTIAL):
            if filled_qty <= 0 or avg_price <= 0:
                logger.warning(
                    f"[bot_engine] {order.ticker} BUY 상태 {fill_status}인데 qty/price 비정상 "
                    f"(filled_qty={filled_qty}, avg={avg_price}) → FAILED 마킹"
                )
                order.status = ORDER_FAILED
                db.commit()
                return

            prev_filled = _cumulative_filled(db, order.id)
            delta = filled_qty - prev_filled
            if delta <= 0:
                # 새 체결 없음. status만 최종화.
                if fill_status == FILL_FILLED:
                    order.status = ORDER_FILLED
                    db.commit()
                return

            fee = round(avg_price * delta * COMMISSION, 2)
            now = datetime.now(tz=timezone.utc)
            new_cumulative = prev_filled + delta
            if fill_status == FILL_FILLED or new_cumulative >= submitted_qty:
                order.status = ORDER_FILLED
            else:
                order.status = ORDER_PARTIAL
            # order.quantity는 submitted_qty 그대로 유지 (원 주문 참조용).
            db.add(Execution(
                order_id=order.id, bot_id=bot.id, ticker=order.ticker,
                execution_type='BUY', quantity=delta, price=avg_price,
                fee=fee, tax=0, executed_at=now,
            ))
            _upsert_position(db, bot.id, order.ticker, delta, avg_price)
            if not skip_cash_adjust:
                bot.cash = float(bot.cash) - (avg_price * delta + fee)
            db.commit()
            logger.info(
                f"[bot_engine] bot_id={bot.id} BUY {order.ticker} "
                f"{fill_status} delta={delta} cum={new_cumulative}/{submitted_qty}주 "
                f"@{avg_price:,.0f} fee={fee} (skip_cash={skip_cash_adjust})"
            )
            if order.status == ORDER_PARTIAL:
                _push_alert(
                    bot.id, bot.name, 'PARTIAL_FILL',
                    f"{order.ticker} BUY 부분체결 {new_cumulative}/{submitted_qty} @{avg_price:,.0f}",
                )
        elif fill_status == FILL_PENDING or fill_status == FILL_UNKNOWN:
            order.status = ORDER_PENDING
            db.commit()
        elif fill_status in (FILL_REJECTED, FILL_CANCELLED):
            order.status = ORDER_REJECTED if fill_status == FILL_REJECTED else ORDER_CANCELLED
            db.commit()
            _push_alert(
                bot.id, bot.name, 'ORDER_' + order.status,
                f"{order.ticker} BUY {order.status} (order={order.order_number})",
            )
        else:
            order.status = ORDER_PENDING
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"[bot_engine] _finalize_buy DB 오류 order_id={order_id} "
            f"order_no={order.order_number if order else '?'} err={e!r}",
            exc_info=True,
        )
        _push_alert(
            bot.id, bot.name, 'DB_SYNC_FAIL',
            f"매수 주문 확정 DB 실패 order={order.order_number if order else '?'} — 수동확인",
        )


def _finalize_sell(db, bot: TradingBot, order_id: int,
                    submitted_qty: int, submitted_price: float,
                    fill_status: str, filled_qty: int, avg_price: float,
                    skip_cash_adjust: bool = False) -> None:
    """SELL 체결 확정. _finalize_buy와 동일한 delta/skip 규칙 적용."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.error(f"[bot_engine] _finalize_sell: Order id={order_id} 없음")
        return
    ticker = order.ticker

    try:
        if fill_status in (FILL_FILLED, FILL_PARTIAL):
            if filled_qty <= 0 or avg_price <= 0:
                logger.warning(
                    f"[bot_engine] {ticker} SELL 상태 {fill_status}인데 qty/price 비정상 → FAILED"
                )
                order.status = ORDER_FAILED
                db.commit()
                return

            prev_filled = _cumulative_filled(db, order.id)
            delta = filled_qty - prev_filled
            if delta <= 0:
                if fill_status == FILL_FILLED:
                    order.status = ORDER_FILLED
                    db.commit()
                return

            position = db.query(Position).filter(
                Position.bot_id == bot.id, Position.ticker == ticker
            ).first()
            if not position:
                order.status = ORDER_FILLED if fill_status == FILL_FILLED else ORDER_PARTIAL
                db.commit()
                _push_alert(
                    bot.id, bot.name, 'POSITION_MISSING',
                    f"{ticker} SELL 체결 but Position 없음 order={order.order_number} — 수동확인",
                )
                return

            fee = round(avg_price * delta * COMMISSION, 2)
            tax = round(avg_price * delta * TAX, 2)
            avg_cost = float(position.avg_price)
            profit_loss = round((avg_price - avg_cost) * delta - fee - tax, 2)
            cost_basis = avg_cost * delta
            pnl_pct = round(profit_loss / cost_basis * 100, 4) if cost_basis else 0.0
            now = datetime.now(tz=timezone.utc)

            new_cumulative = prev_filled + delta
            if fill_status == FILL_FILLED or new_cumulative >= submitted_qty:
                order.status = ORDER_FILLED
            else:
                order.status = ORDER_PARTIAL
            # order.quantity는 submitted_qty 유지.
            db.add(Execution(
                order_id=order.id, bot_id=bot.id, ticker=ticker,
                execution_type='SELL', quantity=delta, price=avg_price,
                fee=fee, tax=tax, profit_loss=profit_loss,
                profit_loss_pct=pnl_pct, executed_at=now,
            ))
            if not skip_cash_adjust:
                bot.cash = float(bot.cash) + (avg_price * delta - fee - tax)
            # Position 수량 감소. delta만큼만 차감 (partial 누적 대응).
            if int(position.quantity) <= delta:
                db.delete(position)
            else:
                position.quantity = int(position.quantity) - delta
            db.commit()
            logger.info(
                f"[bot_engine] bot_id={bot.id} SELL {ticker} "
                f"{fill_status} delta={delta} cum={new_cumulative}/{submitted_qty}주 "
                f"@{avg_price:,.0f} pnl={pnl_pct:.2f}% (skip_cash={skip_cash_adjust})"
            )
            if order.status == ORDER_PARTIAL:
                _push_alert(
                    bot.id, bot.name, 'PARTIAL_FILL',
                    f"{ticker} SELL 부분체결 {new_cumulative}/{submitted_qty}",
                )
        elif fill_status == FILL_PENDING or fill_status == FILL_UNKNOWN:
            order.status = ORDER_PENDING
            db.commit()
        elif fill_status in (FILL_REJECTED, FILL_CANCELLED):
            order.status = ORDER_REJECTED if fill_status == FILL_REJECTED else ORDER_CANCELLED
            db.commit()
            _push_alert(
                bot.id, bot.name, 'ORDER_' + order.status,
                f"{ticker} SELL {order.status} (order={order.order_number})",
            )
        else:
            order.status = ORDER_PENDING
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"[bot_engine] _finalize_sell DB 오류 order_id={order_id} err={e!r}",
            exc_info=True,
        )
        _push_alert(
            bot.id, bot.name, 'DB_SYNC_FAIL',
            f"매도 주문 확정 DB 실패 order={order.order_number if order else '?'} — 수동확인",
        )


def _reconcile_pending_orders(db, bot: TradingBot, broker) -> None:
    """사이클 시작 시 기존 SUBMITTED/PENDING/PARTIAL 주문 재조회해서 완결/타임아웃 처리.

    PARTIAL도 포함 — 나머지 수량이 뒤늦게 체결될 수 있으므로 계속 polling 대상.
    real/paper 모드에선 직전에 get_available_cash()로 cash가 동기화된 상태이므로
    finalize 내부의 cash 조정을 skip (이중 차감 방지).
    """
    pending = db.query(Order).filter(
        Order.bot_id == bot.id,
        Order.status.in_([ORDER_SUBMITTED, ORDER_PENDING, ORDER_PARTIAL]),
    ).all()
    if not pending:
        return

    bot_mode = getattr(bot, 'mode', 'mock')
    skip_cash = bot_mode in ('real', 'paper')

    now_utc = datetime.now(tz=timezone.utc)
    for po in pending:
        if not po.order_number:
            # mock 잔여 주문이면 order_number 없음 — 원래는 발생 안 해야 함
            continue
        try:
            fill = broker.check_order_fill(po.order_number, po.ticker)
        except Exception as e:
            logger.warning(
                f"[bot_engine] reconcile 실패 order={po.order_number} {po.ticker}: {e}"
            )
            continue

        created_utc = po.created_at if po.created_at.tzinfo else po.created_at.replace(tzinfo=timezone.utc)
        age_min = (now_utc - created_utc).total_seconds() / 60

        submitted_qty = int(po.quantity)
        submitted_price = float(po.price) if po.price else 0.0

        if fill.status in (FILL_FILLED, FILL_PARTIAL, FILL_REJECTED, FILL_CANCELLED):
            if po.order_type == 'BUY':
                _finalize_buy(db, bot, po.id, submitted_qty, submitted_price,
                              fill.status, fill.filled_quantity, fill.avg_price,
                              skip_cash_adjust=skip_cash)
            else:
                _finalize_sell(db, bot, po.id, submitted_qty, submitted_price,
                               fill.status, fill.filled_quantity, fill.avg_price,
                               skip_cash_adjust=skip_cash)
        elif fill.status in (FILL_PENDING, FILL_UNKNOWN) and age_min > PENDING_ORDER_TIMEOUT_MIN:
            po.status = ORDER_TIMEOUT
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            _push_alert(
                bot.id, bot.name, 'ORDER_TIMEOUT',
                f"{po.ticker} {po.order_type} {po.order_number} {PENDING_ORDER_TIMEOUT_MIN}분 미체결 — 수동확인",
            )
        # else: still pending, leave as is


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

    # 오늘 거래 수 — KST 자정(한국 시장일) 기준
    today_start = datetime.combine(now_kr.date(), time.min, tzinfo=SEOUL).astimezone(timezone.utc)
    today_count = db.query(Order).filter(
        Order.bot_id == bot.id,
        Order.created_at >= today_start,
    ).count()

    # ── 루프 전 일괄 로드 (N+1 → 4쿼리) ──────────────────────────────
    # 지표는 신규 매수 판정용 — 유니버스(bot.tickers) 기준만 로드.
    # 가격맵은 유니버스 + 보유 포지션 기준 (exit 평가용) — position_map 확보 이후 로드.
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

    max_daily = int(bot.max_daily_trades)
    max_pos = int(bot.max_positions)

    # 종목당 배분 예산: 초기자금 기준 고정 분배
    # total_portfolio(현재 평가액) 기준이면 수익 시 예산이 커져 비의도적 레버리지 발생
    per_pos_budget = float(bot.initial_cash) * float(bot.position_size_pct) / 100

    # 브로커 초기화 및 잔고 사이클 시작 전 1회 검증
    # real/paper: 실패 시 stale 잔고로 주문하는 것을 막기 위해 사이클 전체 skip
    bot_mode = getattr(bot, 'mode', 'mock')
    broker = get_broker(bot_mode)
    if bot_mode in ('real', 'paper'):
        try:
            verified_cash = broker.get_available_cash()
            bot.cash = verified_cash
            db.commit()  # 사이클 중 거래 0건이어도 sync 결과는 persist
        except Exception as e:
            db.rollback()
            logger.error(
                f"[bot_engine] bot_id={bot.id} 잔고 조회 실패 — 사이클 전체 skip "
                f"(mode={bot_mode}, error={e!r})"
            )
            return
        # 지난 사이클의 SUBMITTED/PENDING 주문 재조회 (체결됐으면 Position/Execution 기록)
        _reconcile_pending_orders(db, bot, broker)

    # Position 맵 (reconcile 결과 반영)
    position_map = {
        p.ticker: p
        for p in db.query(Position).filter(Position.bot_id == bot.id).all()
    }

    # 평가 대상 = 유니버스(신규 매수 후보) ∪ 보유 포지션(exit 평가).
    # 보유 종목이 이후 유니버스에서 제외(예: ML 리밸런스)돼도 손절/익절이 계속 평가되도록 포함.
    universe: set[str] = set(tickers)
    eval_tickers: list[str] = list(universe | set(position_map.keys()))
    price_map = _latest_prices_map(db, eval_tickers)

    # 현재 미체결 주문 티커 (중복 접수 방지용, 사이클 내 접수도 누적)
    pending_buy_tickers, pending_sell_tickers = _pending_order_sets(db, bot.id)

    # KIS 비동기 주문 — 사이클 종료 후 한번에 폴링하기 위해 누적
    post_cycle_polls: list[dict] = []

    for ticker in eval_tickers:
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
            if ticker in pending_buy_tickers:
                continue
            if today_count >= max_daily:
                continue
            # 미체결 매수도 슬롯 점유로 계산 (cycle 내 중복 접수 + 기존 PENDING 모두 포함)
            if len(position_map) + len(pending_buy_tickers) >= max_pos:
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
                est_fee = round(curr_price * qty * COMMISSION, 2)
                est_cost = curr_price * qty + est_fee
                if est_cost > float(bot.cash):
                    continue
                # 단일 주문 최대 금액 안전장치 (설정값과 per_pos_budget 중 작은 값)
                max_amt = float(bot.max_order_amount or 0)
                if max_amt > 0 and est_cost > min(max_amt, per_pos_budget * 1.1):
                    logger.warning(
                        f"[bot_engine] bot_id={bot.id} {ticker} 주문 금액 초과 "
                        f"({est_cost:,.0f} > budget:{per_pos_budget:,.0f})"
                    )
                    continue

                # ── 1단계: 브로커 접수 ────────────────────────────────
                try:
                    result = broker.place_buy(bot.id, ticker, qty, curr_price)
                except Exception as e:
                    logger.error(f"[bot_engine] BUY 접수 실패 {ticker}: {e!r}")
                    continue

                # ── 2단계: SUBMITTED Order 저장 (idempotent 복구 경로) ─
                try:
                    order_id = _save_submitted_order(
                        db, bot, ticker, 'BUY', qty, curr_price, result.order_number
                    )
                except Exception as db_exc:
                    db.rollback()
                    logger.error(
                        f"[bot_engine] SUBMITTED 저장 실패 — 브로커 접수됨! "
                        f"bot_id={bot.id} BUY {ticker} {qty}주 order={result.order_number} err={db_exc!r}",
                        exc_info=True,
                    )
                    _push_alert(
                        bot.id, bot.name, 'DB_SYNC_FAIL',
                        f"{ticker} 매수 접수됨(order={result.order_number}) but DB 기록 실패 — 수동확인",
                    )
                    continue

                today_count += 1
                pending_buy_tickers.add(ticker)
                try:
                    _redis_client.set(last_signal_key, today_str, ex=86400)
                except Exception as e:
                    logger.warning(f"[bot_engine] last_signal 기록 실패 {ticker}: {e}")

                # ── 3단계: 체결 확정 (mock 즉시 / KIS 사이클 끝 폴링) ──
                if result.immediate_fill is not None:
                    _finalize_buy(
                        db, bot, order_id, qty, curr_price,
                        result.immediate_fill.status,
                        result.immediate_fill.filled_quantity,
                        result.immediate_fill.avg_price,
                    )
                else:
                    post_cycle_polls.append({
                        'order_id': order_id, 'side': 'BUY',
                        'qty': qty, 'price': curr_price,
                        'order_number': result.order_number, 'ticker': ticker,
                    })
        else:
            # 손절/익절 체크
            if ticker in pending_sell_tickers:
                continue
            avg = float(position.avg_price)
            pnl_pct = (curr_price - avg) / avg * 100
            if pnl_pct <= -float(bot.stop_loss_pct) or pnl_pct >= float(bot.take_profit_pct):
                sell_qty = int(position.quantity)
                try:
                    result = broker.place_sell(bot.id, ticker, sell_qty, curr_price)
                except Exception as e:
                    logger.error(f"[bot_engine] SELL 접수 실패 {ticker}: {e!r}")
                    continue
                try:
                    order_id = _save_submitted_order(
                        db, bot, ticker, 'SELL', sell_qty, curr_price, result.order_number
                    )
                except Exception as db_exc:
                    db.rollback()
                    logger.error(
                        f"[bot_engine] SUBMITTED 저장 실패 — 브로커 접수됨! "
                        f"bot_id={bot.id} SELL {ticker} order={result.order_number} err={db_exc!r}",
                        exc_info=True,
                    )
                    _push_alert(
                        bot.id, bot.name, 'DB_SYNC_FAIL',
                        f"{ticker} 매도 접수됨(order={result.order_number}) but DB 기록 실패 — 수동확인",
                    )
                    continue
                today_count += 1
                pending_sell_tickers.add(ticker)
                if result.immediate_fill is not None:
                    _finalize_sell(
                        db, bot, order_id, sell_qty, curr_price,
                        result.immediate_fill.status,
                        result.immediate_fill.filled_quantity,
                        result.immediate_fill.avg_price,
                    )
                else:
                    post_cycle_polls.append({
                        'order_id': order_id, 'side': 'SELL',
                        'qty': sell_qty, 'price': curr_price,
                        'order_number': result.order_number, 'ticker': ticker,
                    })

    # ── 사이클 종료 후 KIS 주문 일괄 폴링 ─────────────────────────────
    # 대부분의 시장가 주문은 1~2초 내 체결. 3초 대기 후 일괄 조회.
    if post_cycle_polls:
        _time.sleep(FILL_POLL_DELAY_SEC)
        for p in post_cycle_polls:
            try:
                fill = broker.check_order_fill(p['order_number'], p['ticker'])
            except Exception as e:
                logger.warning(
                    f"[bot_engine] check_order_fill 실패 order={p['order_number']}: {e!r} "
                    f"— PENDING 유지, 다음 사이클에서 재조회"
                )
                continue
            if p['side'] == 'BUY':
                _finalize_buy(
                    db, bot, p['order_id'], p['qty'], p['price'],
                    fill.status, fill.filled_quantity, fill.avg_price,
                )
            else:
                _finalize_sell(
                    db, bot, p['order_id'], p['qty'], p['price'],
                    fill.status, fill.filled_quantity, fill.avg_price,
                )


def _execute_buy(db, bot, ticker, qty, price, fee, order_number=None):
    # Circuit Breaker: 포트폴리오 손실 -7%+ 시 신규 매수 차단
    from services.circuit_breaker import is_new_buy_blocked
    if is_new_buy_blocked():
        logger.warning(f"[bot_engine] _execute_buy 차단 (Circuit Breaker WARN+) bot={bot.id} ticker={ticker}")
        return

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
    _upsert_position(db, bot.id, ticker, qty, price)
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
    holdings = 0.0
    if positions:
        # 실시간가 우선(장중 MDD 즉시 감지), 없으면 전일 종가 fallback
        price_map = _latest_prices_map(db, [p.ticker for p in positions])
        for p in positions:
            rt = _redis_client.get(f"rt:price:{p.ticker}")
            if rt:
                price = float(rt)
            elif p.ticker in price_map:
                price = float(price_map[p.ticker].close_price)
            else:
                continue  # 가격 없으면 평가 제외
            holdings += price * p.quantity
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
