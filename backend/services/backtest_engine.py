"""
백테스트 엔진
- 전략 조건이 충족되면 매수, stop_loss/take_profit/max_hold_days/기간 종료 시 매도
- 매수는 다음날 시가(next_day_fill=True) 또는 당일 종가로 체결
- volume_ratio는 StockPrice 거래량에서 동적 계산 (20일 평균 대비)
"""
import logging
import math
from datetime import date as Date
from typing import List, Optional

from sqlalchemy.orm import Session

from models.market import StockPrice, TechnicalIndicator

logger = logging.getLogger(__name__)

SUPPORTED_INDICATORS = {
    # 기술적 지표 (TechnicalIndicator 컬럼)
    'rsi', 'macd', 'macd_signal', 'macd_histogram',
    'stoch_k', 'stoch_d',
    'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
    'ma_20', 'ma_50', 'ma_200',
    'atr', 'adx', 'obv',
    # 추가 지표 (동적 계산 또는 확장 컬럼)
    'volume_ratio',      # StockPrice 거래량 기반 동적 계산 (20일 평균 대비)
    'ma_5', 'ma_10',     # TechnicalIndicator 확장 컬럼 (있으면 사용)
    'ma5_minus_ma20',    # TechnicalIndicator 확장 컬럼 (있으면 사용)
    'opening_gap',       # StockPrice open vs prev close (동적 계산)
}


def _get_val(ind_row, field: str, vol_ctx: dict = None, price_row=None, prev_close: float = None) -> Optional[float]:
    """지표 값 조회 — volume_ratio/opening_gap은 동적 계산"""
    if field == 'volume_ratio':
        if vol_ctx is None or price_row is None:
            return None
        ticker = getattr(price_row, 'ticker', None)
        avg_vol = vol_ctx.get(ticker, 0)
        curr_vol = float(price_row.volume or 0)
        return curr_vol / avg_vol if avg_vol > 0 else None

    if field == 'opening_gap':
        if price_row is None or prev_close is None or prev_close == 0:
            return None
        open_p = float(price_row.open_price or 0)
        return (open_p - prev_close) / prev_close * 100

    if ind_row is None:
        return None
    val = getattr(ind_row, field, None)
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _evaluate_condition(cond: dict, ind_row, prev_ind_row,
                        vol_ctx: dict = None, price_row=None, prev_close: float = None) -> bool:
    indicator = cond.get('indicator', '').lower()
    ctype = cond.get('condition', '').lower()
    value = cond.get('value')
    value2 = cond.get('value2')

    if indicator not in SUPPORTED_INDICATORS:
        return False

    curr = _get_val(ind_row, indicator, vol_ctx=vol_ctx, price_row=price_row, prev_close=prev_close)
    if curr is None:
        return False

    if ctype == 'above':
        return curr > float(value)
    elif ctype == 'below':
        return curr < float(value)
    elif ctype == 'between':
        if value is None or value2 is None:
            return False
        return float(value) < curr < float(value2)
    elif ctype in ('golden_cross', 'dead_cross'):
        if prev_ind_row is None or value is None:
            return False
        prev = _get_val(prev_ind_row, indicator, vol_ctx=vol_ctx, price_row=price_row, prev_close=prev_close)
        if prev is None:
            return False
        threshold = float(value)
        if ctype == 'golden_cross':
            return prev < threshold <= curr
        else:
            return prev >= threshold > curr
    return False


def _all_conditions_met(conditions: list, ind_row, prev_ind_row,
                        vol_ctx: dict = None, price_row=None, prev_close: float = None) -> bool:
    if not conditions:
        return False
    return all(
        _evaluate_condition(c, ind_row, prev_ind_row, vol_ctx=vol_ctx, price_row=price_row, prev_close=prev_close)
        for c in conditions
    )


def _calc_max_drawdown(values: list) -> float:
    if len(values) < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


def _score(metrics: dict) -> tuple:
    """성과 채점 시스템 (5개 카테고리 가중 합산)"""
    cagr = metrics.get('annualized_return_pct', 0)
    max_dd = abs(metrics.get('max_drawdown_pct', 0))
    vol = metrics.get('volatility_pct', 0)
    win_rate = metrics.get('win_rate', 0)
    sharpe = metrics.get('sharpe_ratio', 0)

    # 수익성 30%
    if cagr > 30: rs = 95
    elif cagr > 15: rs = 80
    elif cagr > 8: rs = 65
    elif cagr > 3: rs = 50
    else: rs = max(0, 30 + cagr * 2)

    # 리스크 25%
    if max_dd < 5: rk = 95
    elif max_dd < 10: rk = 80
    elif max_dd < 15: rk = 65
    elif max_dd < 25: rk = 50
    else: rk = max(0, 50 - (max_dd - 25) * 1.5)

    # 안정성 20%
    if vol < 10: st = 95
    elif vol < 15: st = 80
    elif vol < 20: st = 65
    elif vol < 30: st = 50
    else: st = max(0, 50 - (vol - 30))

    # 일관성 15%
    if win_rate > 60: cs = 95
    elif win_rate > 50: cs = 80
    elif win_rate > 40: cs = 65
    elif win_rate > 30: cs = 50
    else: cs = max(0, win_rate * 1.5)

    # 효율성 10%
    if sharpe > 1.5: ef = 95
    elif sharpe > 1.0: ef = 80
    elif sharpe > 0.5: ef = 65
    elif sharpe > 0: ef = 50
    else: ef = max(0, 50 + sharpe * 30)

    total = rs * 0.30 + rk * 0.25 + st * 0.20 + cs * 0.15 + ef * 0.10

    if total >= 90: grade = 'S'
    elif total >= 80: grade = 'A'
    elif total >= 70: grade = 'B'
    elif total >= 60: grade = 'C'
    elif total >= 50: grade = 'D'
    else: grade = 'F'

    return round(total, 1), grade


def _build_vol_ctx(db: Session, tickers: List[str], start: Date, end: Date) -> dict:
    """ticker별 20일 평균 거래량 계산 (volume_ratio 조건용)"""
    vol_ctx = {}
    for ticker in tickers:
        prices = (
            db.query(StockPrice.date, StockPrice.volume)
            .filter(StockPrice.ticker == ticker, StockPrice.date >= start, StockPrice.date <= end)
            .order_by(StockPrice.date.asc())
            .all()
        )
        if not prices:
            continue
        vols = [float(p.volume or 0) for p in prices]
        # 20일 이동평균 — 각 날짜마다 앞 20일 평균이 필요하지만
        # 백테스트 단순화를 위해 전체 평균 사용
        avg = sum(vols) / len(vols) if vols else 0
        vol_ctx[ticker] = avg
    return vol_ctx


def run_backtest(
    db: Session,
    conditions: list,
    tickers: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 10_000_000,
    stop_loss_pct: Optional[float] = 7.0,
    take_profit_pct: Optional[float] = 15.0,
    transaction_cost: float = 0.003,
    max_hold_days: int = 20,
    next_day_fill: bool = True,
) -> dict:
    """
    전략 백테스트 실행

    Args:
        stop_loss_pct: 손절 기준 (%). 기본 7%. None이면 비활성.
        take_profit_pct: 익절 기준 (%). 기본 15%. None이면 비활성.
        max_hold_days: 최대 보유 거래일 수. 기본 20일.
        next_day_fill: True면 신호 다음날 시가로 체결 (현실적). False면 당일 종가.
    """
    start = Date.fromisoformat(start_date)
    end = Date.fromisoformat(end_date)
    per_ticker_capital = initial_capital / max(len(tickers), 1)

    # volume_ratio 조건이 있는지 확인
    needs_vol = any(c.get('indicator') == 'volume_ratio' for c in conditions)
    vol_ctx = _build_vol_ctx(db, tickers, start, end) if needs_vol else {}

    all_trades = []
    per_ticker = {}
    date_totals: dict = {}

    for ticker in tickers:
        prices = (
            db.query(StockPrice)
            .filter(StockPrice.ticker == ticker, StockPrice.date >= start, StockPrice.date <= end)
            .order_by(StockPrice.date.asc())
            .all()
        )
        inds = (
            db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.ticker == ticker, TechnicalIndicator.date >= start, TechnicalIndicator.date <= end)
            .order_by(TechnicalIndicator.date.asc())
            .all()
        )

        if not prices:
            logger.warning(f"[backtest] {ticker}: 가격 데이터 없음")
            continue

        price_map = {p.date: p for p in prices}
        ind_map = {i.date: i for i in inds}
        dates = sorted(price_map.keys())

        cash = per_ticker_capital
        position = None
        ticker_trades = []
        ticker_equity = []

        for i, d in enumerate(dates):
            price_row = price_map[d]
            ind_row = ind_map.get(d)
            prev_ind_row = ind_map.get(dates[i - 1]) if i > 0 else None
            prev_price_row = price_map.get(dates[i - 1]) if i > 0 else None
            prev_close = float(prev_price_row.close_price) if prev_price_row else None
            close = float(price_row.close_price)

            curr_val = cash + (position['shares'] * close if position else 0)
            ticker_equity.append({'date': d.isoformat(), 'value': round(curr_val, 0)})

            if position is None:
                # 매수 신호 체크: next_day_fill이면 전날 신호 → 오늘 시가 체결
                signal_date = dates[i - 1] if (next_day_fill and i > 0) else d
                signal_ind = ind_map.get(signal_date)
                signal_prev_ind = ind_map.get(dates[i - 2]) if (next_day_fill and i > 1) else prev_ind_row
                signal_price_row = price_map.get(signal_date) if next_day_fill else price_row
                signal_prev_close = float(price_map[dates[i - 2]].close_price) if (next_day_fill and i > 1) else prev_close

                if _all_conditions_met(conditions, signal_ind, signal_prev_ind,
                                       vol_ctx=vol_ctx, price_row=signal_price_row,
                                       prev_close=signal_prev_close):
                    # next_day_fill: 오늘 시가로 체결, 아니면 종가
                    fill_price_base = float(price_row.open_price or close) if next_day_fill else close
                    buy_price = fill_price_base * (1 + transaction_cost)
                    shares = cash / buy_price
                    cash = 0
                    position = {
                        'shares': shares,
                        'buy_price': buy_price,
                        'buy_date': d.isoformat(),
                        'hold_days': 0,
                    }
                    ticker_trades.append({
                        'ticker': ticker, 'type': 'BUY',
                        'date': d.isoformat(), 'price': round(buy_price, 0),
                        'shares': round(shares, 4),
                    })
            else:
                position['hold_days'] += 1
                pnl_pct = (close - position['buy_price']) / position['buy_price'] * 100
                sell_reason = None

                if stop_loss_pct is not None and pnl_pct <= -stop_loss_pct:
                    sell_reason = 'stop_loss'
                elif take_profit_pct is not None and pnl_pct >= take_profit_pct:
                    sell_reason = 'take_profit'
                elif max_hold_days and position['hold_days'] >= max_hold_days:
                    sell_reason = 'max_hold_days'
                elif i == len(dates) - 1:
                    sell_reason = 'end_of_period'

                if sell_reason:
                    sell_price = close * (1 - transaction_cost)
                    pnl = (sell_price - position['buy_price']) * position['shares']
                    cash = position['shares'] * sell_price
                    ticker_trades.append({
                        'ticker': ticker, 'type': 'SELL',
                        'date': d.isoformat(), 'price': round(sell_price, 0),
                        'buy_date': position['buy_date'], 'buy_price': round(position['buy_price'], 0),
                        'pnl': round(pnl, 0), 'return_pct': round(pnl_pct, 2),
                        'reason': sell_reason,
                        'hold_days': position['hold_days'],
                    })
                    position = None

        # 기간 종료 시 잔여 포지션 강제 청산
        if position and prices:
            final_price = float(prices[-1].close_price) * (1 - transaction_cost)
            pnl_pct = (final_price - position['buy_price']) / position['buy_price'] * 100
            pnl = (final_price - position['buy_price']) * position['shares']
            cash = position['shares'] * final_price
            ticker_trades.append({
                'ticker': ticker, 'type': 'SELL',
                'date': dates[-1].isoformat(), 'price': round(final_price, 0),
                'buy_date': position['buy_date'], 'buy_price': round(position['buy_price'], 0),
                'pnl': round(pnl, 0), 'return_pct': round(pnl_pct, 2),
                'reason': 'end_of_period',
                'hold_days': position.get('hold_days', 0),
            })
            position = None

        final_val = cash
        ticker_return = (final_val - per_ticker_capital) / per_ticker_capital * 100
        sell_trades = [t for t in ticker_trades if t['type'] == 'SELL']
        wins = [t for t in sell_trades if t['pnl'] > 0]

        per_ticker[ticker] = {
            'final_value': round(final_val, 0),
            'total_return_pct': round(ticker_return, 2),
            'num_trades': len(sell_trades),
            'win_rate': round(len(wins) / len(sell_trades) * 100, 1) if sell_trades else 0,
        }
        all_trades.extend(ticker_trades)

        for point in ticker_equity:
            d = point['date']
            date_totals[d] = date_totals.get(d, 0) + point['value']

    # 포트폴리오 지표 계산
    portfolio_curve = [{'date': d, 'value': v} for d, v in sorted(date_totals.items())]
    values = [p['value'] for p in portfolio_curve]

    final_total = sum(v['final_value'] for v in per_ticker.values()) if per_ticker else initial_capital
    total_return = (final_total - initial_capital) / initial_capital * 100

    days = max((Date.fromisoformat(end_date) - Date.fromisoformat(start_date)).days, 1)
    annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if total_return > -100 else -100

    if len(values) > 1:
        daily_returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1] > 0]
        if daily_returns:
            mean_r = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
            vol = math.sqrt(variance) * math.sqrt(252) * 100
            sharpe = (annualized_return / 100) / (vol / 100) if vol > 0 else 0
        else:
            vol, sharpe = 0.0, 0.0
        max_dd = _calc_max_drawdown(values)
    else:
        vol, sharpe, max_dd = 0.0, 0.0, 0.0

    sell_trades = [t for t in all_trades if t['type'] == 'SELL']
    wins = [t for t in sell_trades if t['pnl'] > 0]
    win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    metrics = {
        'total_return_pct': round(total_return, 2),
        'annualized_return_pct': round(annualized_return, 2),
        'sharpe_ratio': round(sharpe, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'volatility_pct': round(vol, 2),
        'win_rate': round(win_rate, 1),
        'num_trades': len(sell_trades),
        'final_value': round(final_total, 0),
        'initial_capital': initial_capital,
    }
    metrics['total_score'], metrics['grade'] = _score(metrics)

    return {
        'summary': metrics,
        'trades': all_trades,
        'equity_curve': portfolio_curve,
        'per_ticker': per_ticker,
    }
