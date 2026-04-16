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
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo

import redis

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot, Order, Execution, Position, BotReport
from models.strategy import Strategy
from broker.factory import get_broker
from tasks.bot_engine import (
    _execute_buy, _execute_sell, _push_alert, _exceeds_max_drawdown,
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


def _get_or_init_peak(bot_id: int, ticker: str, fallback: float) -> float:
    """Redis에서 peak 조회. 없으면 fallback(매수가)으로 초기화."""
    raw = _redis_client.get(_peak_key(bot_id, ticker))
    if raw is None:
        _redis_client.setex(_peak_key(bot_id, ticker), PEAK_KEY_TTL, fallback)
        return fallback
    return float(raw)


def _update_peak(bot_id: int, ticker: str, curr_price: float) -> float:
    """현재가가 peak 초과 시 갱신. 현재 peak 반환."""
    peak = _get_or_init_peak(bot_id, ticker, curr_price)
    if curr_price > peak:
        _redis_client.setex(_peak_key(bot_id, ticker), PEAK_KEY_TTL, curr_price)
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


def _run_scalping_cycle_inner(db, bot: TradingBot):
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
        bot.status = "ERROR"
        logger.warning("[scalping_engine] bot_id=%d 최대 낙폭 초과 → ERROR", bot.id)
        db.commit()
        _push_alert(bot.id, bot.name, "MAX_DRAWDOWN", "최대 낙폭 초과로 봇이 정지되었습니다")
        return

    interval = int(bot.candle_interval or 1)
    confirm_bars = int(getattr(bot, "confirm_bars", None) or 1)
    trailing_stop_pct = float(getattr(bot, "trailing_stop_pct", None) or 0)

    # 당일 강제 청산 체크
    if bot.intraday_close and bot.intraday_close_time:
        close_t = bot.intraday_close_time
        if isinstance(close_t, time) and now_t >= close_t:
            positions = db.query(Position).filter(Position.bot_id == bot.id).all()
            if positions:
                logger.info("[scalping_engine] bot_id=%d 당일 강제 청산 시작 (%d 포지션)",
                            bot.id, len(positions))
                for pos in positions:
                    rt = _redis_client.get(f"rt:price:{pos.ticker}")
                    curr_price = float(rt) if rt else float(pos.avg_price)
                    try:
                        broker_obj = get_broker(getattr(bot, "mode", "mock"))
                        result = broker_obj.place_sell(bot.id, pos.ticker, pos.quantity, curr_price)
                        _execute_sell(db, bot, pos, result.filled_price, result.order_number)
                        _redis_client.delete(_peak_key(bot.id, pos.ticker))
                        _redis_client.delete(_signal_key(bot.id, pos.ticker))
                        logger.info("[scalping_engine] bot_id=%d 강제청산 SELL %s %d주 @%.0f",
                                    bot.id, pos.ticker, pos.quantity, result.filled_price)
                    except Exception as e:
                        logger.error("[scalping_engine] 강제청산 실패 %s: %s", pos.ticker, e)
                db.commit()
            return

    # 오늘 매수 건수 (max_daily_trades 기준: 매수만 카운트)
    today_start = datetime.combine(now_kr.date(), time.min, tzinfo=timezone.utc)
    today_count = db.query(Order).filter(
        Order.bot_id == bot.id,
        Order.order_type == "BUY",
        Order.created_at >= today_start,
    ).count()

    for ticker in tickers:
        rt = _redis_client.get(f"rt:price:{ticker}")
        indicators = _load_indicators(ticker, interval)

        if indicators is None:
            logger.debug("[scalping_engine] 분봉 지표 없음 — %s:%d", ticker, interval)
            continue

        curr_price_raw = rt or indicators.get("bollinger_middle") or indicators.get("ma_20")
        if curr_price_raw is None:
            continue
        curr_price = float(curr_price_raw)

        position = db.query(Position).filter(
            Position.bot_id == bot.id,
            Position.ticker == ticker,
        ).first()

        if position is None:
            # ── 매수 조건 체크 ─────────────────────────────────────────
            if today_count >= int(bot.max_daily_trades):
                continue
            pos_count = db.query(Position).filter(Position.bot_id == bot.id).count()
            if pos_count >= int(bot.max_positions):
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
            fee = round(curr_price * qty * COMMISSION, 2)
            cost = curr_price * qty + fee
            if cost > float(bot.cash):
                continue
            max_amt = float(bot.max_order_amount or 0)
            if max_amt > 0 and cost > max_amt:
                logger.warning("[scalping_engine] bot_id=%d %s 주문 금액 초과 (%.0f > %.0f)",
                               bot.id, ticker, cost, max_amt)
                continue

            try:
                broker_obj = get_broker(getattr(bot, "mode", "mock"))
                result = broker_obj.place_buy(bot.id, ticker, qty, curr_price)
                _execute_buy(db, bot, ticker, qty, result.filled_price, fee, result.order_number)
                # peak 초기화 (매수가 기준)
                _redis_client.setex(_peak_key(bot.id, ticker), PEAK_KEY_TTL, result.filled_price)
                # 신호 카운터 초기화
                _redis_client.delete(sig_key)
                today_count += 1
                logger.info("[scalping_engine] bot_id=%d BUY %s %d주 @%.0f (confirm=%d)",
                            bot.id, ticker, qty, result.filled_price, count)
            except Exception as e:
                logger.error("[scalping_engine] BUY 실패 %s: %s", ticker, e)

        else:
            # ── 청산 조건 체크 ─────────────────────────────────────────
            avg = float(position.avg_price)
            pnl_pct = (curr_price - avg) / avg * 100
            sell_reason = None

            # 1) 트레일링 스탑 (설정된 경우 우선 체크)
            if trailing_stop_pct > 0:
                peak = _update_peak(bot.id, ticker, curr_price)
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
                try:
                    broker_obj = get_broker(getattr(bot, "mode", "mock"))
                    result = broker_obj.place_sell(bot.id, ticker, position.quantity, curr_price)
                    _execute_sell(db, bot, position, result.filled_price, result.order_number)
                    _redis_client.delete(_peak_key(bot.id, ticker))
                    _redis_client.delete(_signal_key(bot.id, ticker))
                    logger.info("[scalping_engine] bot_id=%d %s SELL %s pnl=%.1f%%",
                                bot.id, sell_reason, ticker, pnl_pct)
                except Exception as e:
                    logger.error("[scalping_engine] SELL 실패 %s: %s", ticker, e)

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
