"""
백테스트 엔진
- 전략 조건이 충족되면 매수, stop_loss/take_profit/기간 종료 시 매도
- happystocklife의 성과 지표 및 채점 시스템 참고
"""
import logging
import math
from datetime import date as Date
from typing import List, Optional

from sqlalchemy.orm import Session

from models.market import StockPrice, TechnicalIndicator

logger = logging.getLogger(__name__)

SUPPORTED_INDICATORS = {
    'rsi', 'macd', 'macd_signal', 'macd_histogram',
    'stoch_k', 'stoch_d',
    'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
    'ma_20', 'ma_50', 'ma_200',
    'atr', 'adx', 'obv',
}


def _get_val(ind_row, field: str) -> Optional[float]:
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


def _evaluate_condition(cond: dict, ind_row, prev_ind_row) -> bool:
    indicator = cond.get('indicator', '').lower()
    ctype = cond.get('condition', '').lower()
    value = cond.get('value')
    value2 = cond.get('value2')

    if indicator not in SUPPORTED_INDICATORS:
        return False

    curr = _get_val(ind_row, indicator)
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
        prev = _get_val(prev_ind_row, indicator)
        if prev is None:
            return False
        threshold = float(value)
        if ctype == 'golden_cross':
            return prev < threshold <= curr
        else:
            return prev >= threshold > curr
    return False


def _all_conditions_met(conditions: list, ind_row, prev_ind_row) -> bool:
    if not conditions:
        return False
    return all(_evaluate_condition(c, ind_row, prev_ind_row) for c in conditions)


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
    """happystocklife 채점 시스템 (5개 카테고리 가중 합산)"""
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


def run_backtest(
    db: Session,
    conditions: list,
    tickers: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 10_000_000,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    transaction_cost: float = 0.003,
) -> dict:
    start = Date.fromisoformat(start_date)
    end = Date.fromisoformat(end_date)
    per_ticker_capital = initial_capital / max(len(tickers), 1)

    all_trades = []
    per_ticker = {}
    date_totals: dict = {}  # date → portfolio value

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
            close = float(price_row.close_price)

            curr_val = cash + (position['shares'] * close if position else 0)
            ticker_equity.append({'date': d.isoformat(), 'value': round(curr_val, 0)})

            if position is None:
                if ind_row and _all_conditions_met(conditions, ind_row, prev_ind_row):
                    buy_price = close * (1 + transaction_cost)
                    shares = cash / buy_price
                    cash = 0
                    position = {'shares': shares, 'buy_price': buy_price, 'buy_date': d.isoformat()}
                    ticker_trades.append({
                        'ticker': ticker, 'type': 'BUY',
                        'date': d.isoformat(), 'price': round(buy_price, 0),
                        'shares': round(shares, 4),
                    })
            else:
                pnl_pct = (close - position['buy_price']) / position['buy_price'] * 100
                sell_reason = None
                if stop_loss_pct and pnl_pct <= -stop_loss_pct:
                    sell_reason = 'stop_loss'
                elif take_profit_pct and pnl_pct >= take_profit_pct:
                    sell_reason = 'take_profit'
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
                    })
                    position = None

        # 기간 종료 시 포지션 남아있으면 강제 청산
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

        # 포트폴리오 날짜별 합산
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
