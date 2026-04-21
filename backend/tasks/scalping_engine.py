"""
단타(Scalping) 봇 실행 엔진
- 1분마다 실행 (celery beat)
- bot_type='scalping' AND status='RUNNING' 봇 처리
- 분봉 지표(Redis)로 매수 신호 평가

개선 사항:
- VWAP / ATR / MA 크로스 차이값 지표 지원
- 트레일링 스탑 (Redis peak 추적)
- 연속 봉 확인 (confirm_bars)
- 당일 강제 청산 처리
"""
import json
import logging
import math
import time as _time
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

import redis

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Order, Execution, Position, BotReport
from models.strategy import Strategy
from broker.factory import get_broker
from broker.base import FILL_FILLED, FILL_PARTIAL, FILL_PENDING, FILL_UNKNOWN
from tasks.bot_engine import (
    _push_alert, _exceeds_max_drawdown,
    _save_submitted_order, _finalize_buy, _finalize_sell,
    _reconcile_pending_orders, _pending_order_sets,
    FILL_POLL_DELAY_SEC,
    COMMISSION, TAX, ALERTS_KEY,
)
from tasks.intraday_collector import _ind_key

logger = logging.getLogger(__name__)

SEOUL = ZoneInfo("Asia/Seoul")
_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

PEAK_KEY_TTL = 8 * 3600   # 8시간 — 당일 장 내내 유지
SIGNAL_KEY_TTL = 90        # 90초 — 1분봉 2개 커버, 신호 단절 시 자동 리셋


# ── 지표 로드 ─────────────────────────────────────────────────────────

def _load_indicators(ticker: str, interval: int) -> dict | None:
    raw = _redis_client.get(_ind_key(ticker, interval))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


# ── 지표값 추출 ───────────────────────────────────────────────────────

def _get_ind_val(indicators: dict, field: str):
    val = indicators.get(field)
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# ── 단타 조건 평가 ────────────────────────────────────────────────────

SCALPING_INDICATORS = {
    "rsi", "macd", "macd_signal", "macd_histogram",
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_5", "ma_10", "ma_20",
    "volume_ratio", "opening_gap",
    # 신규
    "vwap", "price_vs_vwap", "atr",
    "ma5_minus_ma10", "ma5_minus_ma20",
}


def _evaluate_scalping_condition(cond: dict, indicators: dict) -> bool:
    """분봉 지표 dict 기반 단타 조건 평가"""
    indicator = cond.get("indicator", "").lower()
    ctype = cond.get("condition", "").lower()
    value = cond.get("value")
    value2 = cond.get("value2")

    if indicator not in SCALPING_INDICATORS:
        return False

    curr = _get_ind_val(indicators, indicator)
    if curr is None:
        return False

    if ctype == "above":
        return curr > float(value)
    elif ctype == "below":
        return curr < float(value)
    elif ctype == "between":
        if value is None or value2 is None:
            return False
        return float(value) < curr < float(value2)
    elif ctype in ("golden_cross", "dead_cross"):
        if value is None:
            return False
        prev = _get_ind_val(indicators, f"prev_{indicator}")
        if prev is None:
            return False
        threshold = float(value)
        if ctype == "golden_cross":
            return prev < threshold <= curr
        else:
            return prev >= threshold > curr
    return False


def _all_scalping_conditions_met(conditions: list, indicators: dict) -> bool:
    if not conditions:
        return False
    return all(_evaluate_scalping_condition(c, indicators) for c in conditions)


# ── 트레일링 스탑 헬퍼 ────────────────────────────────────────────────

def _peak_key(bot_id: int, ticker: str) -> str:
    return f"rt:peak:{bot_id}:{ticker}"


def _signal_key(bot_id: int, ticker: str) -> str:
    return f"rt:sig:{bot_id}:{ticker}"


def _get_or_init_peak(bot_id: int, ticker: str, fallback: float, position=None) -> float:
    """peak 조회 우선순위: Redis → DB(position.trailing_peak) → fallback(매수가)."""
    raw = _redis_client.get(_peak_key(bot_id, ticker))
    if raw is not None:
        return float(raw)
    # Redis 없으면 DB에서 복구
    db_peak = float(position.trailing_peak) if (position and position.trailing_peak) else fallback
    _redis_client.setex(_peak_key(bot_id, ticker), PEAK_KEY_TTL, db_peak)
    return db_peak


def _update_peak(bot_id: int, ticker: str, curr_price: float, position=None) -> float:
    """현재가가 peak 초과 시 Redis + DB 동시 갱신. 현재 peak 반환."""
    peak = _get_or_init_peak(bot_id, ticker, curr_price, position)
    if curr_price > peak:
        _redis_client.setex(_peak_key(bot_id, ticker), PEAK_KEY_TTL, curr_price)
        if position is not None:
            position.trailing_peak = curr_price
        return curr_price
    return peak


# ── 단타 봇 사이클 ────────────────────────────────────────────────────

def _run_scalping_cycle(db, bot: TradingBot):
    # ── 중복 실행 방지 ──────────────────────────────────────────────────
    lock_key = f"autostock:bot_cycle_lock:{bot.id}"
    acquired = _redis_client.set(lock_key, "1", nx=True, ex=120)  # 2분 TTL (단타 사이클은 짧음)
    if not acquired:
        logger.info("[scalping_engine] bot_id=%d 이전 사이클 실행 중 — 스킵", bot.id)
        return

    try:
        _run_scalping_cycle_inner(db, bot)
    finally:
        _redis_client.delete(lock_key)


def _submit_and_track(db, bot, broker_obj, side: str, ticker: str, qty: int,
                       curr_price: float, post_cycle_polls: list) -> int | None:
    """브로커 접수 → SUBMITTED Order 저장 → immediate_fill이면 finalize, 아니면 post_cycle_polls에 누적.

    반환: 생성된 order_id (성공) 또는 None (실패). 실패 시 로그/알림 처리.
    side는 'BUY' | 'SELL'. in-cycle 신규 주문이므로 skip_cash_adjust=False로 finalize.
    """
    try:
        if side == 'BUY':
            result = broker_obj.place_buy(bot.id, ticker, qty, curr_price)
        else:
            result = broker_obj.place_sell(bot.id, ticker, qty, curr_price)
    except Exception as e:
        logger.error("[scalping_engine] %s 접수 실패 %s: %s", side, ticker, e, exc_info=True)
        return None

    try:
        order_id = _save_submitted_order(db, bot, ticker, side, qty, curr_price, result.order_number)
    except Exception as db_exc:
        db.rollback()
        logger.error(
            "[scalping_engine] SUBMITTED 저장 실패 — 브로커 접수됨! "
            "bot_id=%d %s %s qty=%d order=%s err=%r",
            bot.id, side, ticker, qty, result.order_number, db_exc,
            exc_info=True,
        )
        _push_alert(
            bot.id, bot.name, 'DB_SYNC_FAIL',
            f"{ticker} {side} 접수됨(order={result.order_number}) but DB 기록 실패 — 수동확인",
        )
        return None

    if result.immediate_fill is not None:
        # Mock 즉시 체결. finalize 내부에서 commit.
        if side == 'BUY':
            _finalize_buy(db, bot, order_id, qty, curr_price,
                          result.immediate_fill.status,
                          result.immediate_fill.filled_quantity,
                          result.immediate_fill.avg_price)
            # peak는 체결가 확정 후 초기화
            if result.immediate_fill.status in (FILL_FILLED, FILL_PARTIAL) and result.immediate_fill.filled_quantity > 0:
                _redis_client.setex(_peak_key(bot.id, ticker), PEAK_KEY_TTL,
                                    result.immediate_fill.avg_price)
        else:
            _finalize_sell(db, bot, order_id, qty, curr_price,
                           result.immediate_fill.status,
                           result.immediate_fill.filled_quantity,
                           result.immediate_fill.avg_price)
            # SELL 완결 후 Position 사라졌으면 peak/signal key 제거
            still_held = db.query(Position).filter(
                Position.bot_id == bot.id, Position.ticker == ticker
            ).first()
            if still_held is None:
                _redis_client.delete(_peak_key(bot.id, ticker))
                _redis_client.delete(_signal_key(bot.id, ticker))
    else:
        # KIS 접수만 됨 → 사이클 끝에 폴링
        post_cycle_polls.append({
            'order_id': order_id, 'side': side,
            'qty': qty, 'price': curr_price,
            'order_number': result.order_number, 'ticker': ticker,
        })
    return order_id


def _run_scalping_cycle_inner(db, bot: TradingBot):
    now_kr = datetime.now(tz=SEOUL)
    now_t = now_kr.time().replace(tzinfo=None)

    # 장 시작 전이면 전체 스킵 (강제청산도 사전시장엔 의미 없음)
    start_t = bot.trading_start_time
    end_t = bot.trading_end_time
    if start_t and now_t < start_t:
        return

    strategy = db.query(Strategy).filter(Strategy.id == bot.strategy_id).first()
    if not strategy:
        return

    tickers = bot.tickers or []
    if not tickers:
        return

    # 최대 낙폭 체크
    if _exceeds_max_drawdown(db, bot):
        bot.status = "ERROR"
        logger.warning("[scalping_engine] bot_id=%d 최대 낙폭 초과 → ERROR", bot.id)
        db.commit()
        _push_alert(bot.id, bot.name, "MAX_DRAWDOWN", "최대 낙폭 초과로 봇이 정지되었습니다")
        return

    interval = int(bot.candle_interval or 1)
    confirm_bars = int(getattr(bot, "confirm_bars", None) or 1)
    trailing_stop_pct = float(getattr(bot, "trailing_stop_pct", None) or 0)
    bot_mode = getattr(bot, "mode", "mock")
    broker_obj = get_broker(bot_mode)  # 사이클 1회 생성 후 재사용

    # real/paper 모드: 사이클 전 잔고 동기화 + 미체결 주문 reconcile
    if bot_mode in ("real", "paper"):
        try:
            verified_cash = broker_obj.get_available_cash()
            bot.cash = verified_cash
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                "[scalping_engine] bot_id=%d 잔고 조회 실패 — 사이클 skip (mode=%s, err=%r)",
                bot.id, bot_mode, e,
            )
            return
        _reconcile_pending_orders(db, bot, broker_obj)

    # 당일 강제 청산 체크 — trading_end_time 이후에도 실행되어야 하므로 end gate 앞에 배치
    if bot.intraday_close and bot.intraday_close_time:
        close_t = bot.intraday_close_time
        if isinstance(close_t, time) and now_t >= close_t:
            positions = db.query(Position).filter(Position.bot_id == bot.id).all()
            if positions:
                logger.info("[scalping_engine] bot_id=%d 당일 강제 청산 시작 (%d 포지션)",
                            bot.id, len(positions))
                liq_polls: list[dict] = []
                for pos in positions:
                    rt = _redis_client.get(f"rt:price:{pos.ticker}")
                    if rt:
                        curr_price = float(rt)
                    else:
                        curr_price = float(pos.avg_price)
                        if bot_mode in ("real", "paper"):
                            logger.warning(
                                "[scalping_engine] bot_id=%d 강제청산 %s 실시간가 없음 — avg_price 사용",
                                bot.id, pos.ticker,
                            )
                    _submit_and_track(db, bot, broker_obj, 'SELL', pos.ticker,
                                      int(pos.quantity), curr_price, liq_polls)
                # KIS 강제청산: 폴링으로 체결 확정
                if liq_polls:
                    _time.sleep(FILL_POLL_DELAY_SEC)
                    for p in liq_polls:
                        try:
                            fill = broker_obj.check_order_fill(p['order_number'], p['ticker'])
                        except Exception as e:
                            logger.warning(
                                "[scalping_engine] 강제청산 체결조회 실패 order=%s: %r",
                                p['order_number'], e,
                            )
                            continue
                        _finalize_sell(db, bot, p['order_id'], p['qty'], p['price'],
                                       fill.status, fill.filled_quantity, fill.avg_price)
                        still_held = db.query(Position).filter(
                            Position.bot_id == bot.id, Position.ticker == p['ticker']
                        ).first()
                        if still_held is None:
                            _redis_client.delete(_peak_key(bot.id, p['ticker']))
                            _redis_client.delete(_signal_key(bot.id, p['ticker']))
            return

    # 장 마감 이후면 신규 거래/정상 청산 불가 (강제청산은 위에서 처리됨)
    if end_t and now_t > end_t:
        return

    # 오늘 매수 건수 — KST 자정(한국 시장일) 기준
    today_start = datetime.combine(now_kr.date(), time.min, tzinfo=SEOUL).astimezone(timezone.utc)
    today_count = db.query(Order).filter(
        Order.bot_id == bot.id,
        Order.order_type == "BUY",
        Order.created_at >= today_start,
    ).count()

    # 평가 대상 = 유니버스 ∪ 보유 포지션 (유니버스 이탈 포지션도 exit 평가)
    position_map = {
        p.ticker: p for p in db.query(Position).filter(Position.bot_id == bot.id).all()
    }
    universe: set[str] = set(tickers)
    eval_tickers: list[str] = list(universe | set(position_map.keys()))
    # 미체결 주문 티커 (reconcile 이후 상태 반영). 중복 접수 차단용.
    pending_buy_tickers, pending_sell_tickers = _pending_order_sets(db, bot.id)
    bought_this_cycle: set[str] = set()
    post_cycle_polls: list[dict] = []

    for ticker in eval_tickers:
        # 실시간가 없으면 skip — 지표값을 가격 대용으로 쓰면 손절/익절 오염.
        rt = _redis_client.get(f"rt:price:{ticker}")
        if not rt:
            continue
        curr_price = float(rt)

        position = position_map.get(ticker)

        if position is None:
            # ── 매수 조건 체크 (eval_tickers 구성상 universe 멤버임이 보장) ─
            if ticker in pending_buy_tickers:
                continue
            if today_count >= int(bot.max_daily_trades):
                continue
            # 이번 사이클 내 신규 매수 + 기존 미체결도 슬롯 점유로 계산
            if len(position_map) + len(pending_buy_tickers) + len(bought_this_cycle) >= int(bot.max_positions):
                continue

            indicators = _load_indicators(ticker, interval)
            if indicators is None:
                continue

            signal_met = _all_scalping_conditions_met(strategy.conditions, indicators)
            sig_key = _signal_key(bot.id, ticker)

            if signal_met:
                # 연속 봉 카운터 증가
                count = int(_redis_client.get(sig_key) or 0) + 1
                _redis_client.setex(sig_key, SIGNAL_KEY_TTL, count)
            else:
                # 신호 단절 → 카운터 리셋
                _redis_client.delete(sig_key)
                count = 0

            if not signal_met or count < confirm_bars:
                continue

            # 진입 수량 / 금액 계산 (초기자금 기준 고정 분배 — 수익 시 레버리지 방지)
            qty = int(float(bot.initial_cash) * float(bot.position_size_pct) / 100 / curr_price)
            if qty <= 0:
                continue
            est_fee = round(curr_price * qty * COMMISSION, 2)
            est_cost = curr_price * qty + est_fee
            if est_cost > float(bot.cash):
                continue
            max_amt = float(bot.max_order_amount or 0)
            if max_amt > 0 and est_cost > max_amt:
                logger.warning("[scalping_engine] bot_id=%d %s 주문 금액 초과 (%.0f > %.0f)",
                               bot.id, ticker, est_cost, max_amt)
                continue

            order_id = _submit_and_track(db, bot, broker_obj, 'BUY', ticker, qty,
                                         curr_price, post_cycle_polls)
            if order_id is None:
                continue
            today_count += 1
            bought_this_cycle.add(ticker)
            # 신호 카운터 초기화
            _redis_client.delete(sig_key)

        else:
            # ── 청산 조건 체크 (universe 이탈 종목도 평가) ─────────────
            if ticker in pending_sell_tickers:
                continue
            avg = float(position.avg_price)
            pnl_pct = (curr_price - avg) / avg * 100
            sell_reason = None

            # 1) 트레일링 스탑 (설정된 경우 우선 체크)
            if trailing_stop_pct > 0:
                peak = _update_peak(bot.id, ticker, curr_price, position)
                trail_price = peak * (1 - trailing_stop_pct / 100)
                if curr_price <= trail_price:
                    sell_reason = "trailing_stop"
                    logger.debug("[scalping_engine] bot_id=%d %s 트레일링스탑 peak=%.0f curr=%.0f",
                                 bot.id, ticker, peak, curr_price)

            # 2) 고정 손절 / 익절
            if sell_reason is None:
                if pnl_pct <= -float(bot.stop_loss_pct):
                    sell_reason = "stop_loss"
                elif pnl_pct >= float(bot.take_profit_pct):
                    sell_reason = "take_profit"

            if sell_reason:
                _submit_and_track(db, bot, broker_obj, 'SELL', ticker,
                                  int(position.quantity), curr_price, post_cycle_polls)

    # ── 사이클 종료 후 KIS 주문 일괄 폴링 ─────────────────────────────
    if post_cycle_polls:
        _time.sleep(FILL_POLL_DELAY_SEC)
        for p in post_cycle_polls:
            try:
                fill = broker_obj.check_order_fill(p['order_number'], p['ticker'])
            except Exception as e:
                logger.warning(
                    "[scalping_engine] check_order_fill 실패 order=%s: %r — PENDING 유지",
                    p['order_number'], e,
                )
                continue
            if p['side'] == 'BUY':
                _finalize_buy(db, bot, p['order_id'], p['qty'], p['price'],
                              fill.status, fill.filled_quantity, fill.avg_price)
                if fill.status in (FILL_FILLED, FILL_PARTIAL) and fill.filled_quantity > 0:
                    _redis_client.setex(_peak_key(bot.id, p['ticker']), PEAK_KEY_TTL, fill.avg_price)
            else:
                _finalize_sell(db, bot, p['order_id'], p['qty'], p['price'],
                               fill.status, fill.filled_quantity, fill.avg_price)
                still_held = db.query(Position).filter(
                    Position.bot_id == bot.id, Position.ticker == p['ticker']
                ).first()
                if still_held is None:
                    _redis_client.delete(_peak_key(bot.id, p['ticker']))
                    _redis_client.delete(_signal_key(bot.id, p['ticker']))

    db.commit()


# ── Celery 태스크 ─────────────────────────────────────────────────────

@celery_app.task(name="tasks.scalping_engine.run_scalping_bots")
def run_scalping_bots():
    """1분마다 실행 — bot_type='scalping' AND status='RUNNING' 봇 처리"""
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(
            TradingBot.status == "RUNNING",
            TradingBot.bot_type == "scalping",
        ).all()

        if not bots:
            return

        logger.info("[scalping_engine] 단타 봇 실행: %d개", len(bots))
        for bot in bots:
            try:
                _run_scalping_cycle(db, bot)
            except Exception as e:
                logger.error("[scalping_engine] bot_id=%d 오류: %s", bot.id, e, exc_info=True)
                bot.status = "ERROR"
                db.commit()
                _push_alert(bot.id, bot.name, "ERROR", str(e))
    finally:
        db.close()
