import math
from sqlalchemy.orm import Session
from models.trading import Account, TradingBot, Order, Execution, Position, BotReport
from core.security import get_encryption_service


# ── 계좌 ───────────────────────────────────────────────────────────

def get_accounts(db: Session, user_id: int):
    return db.query(Account).filter(Account.user_id == user_id, Account.is_active == True).all()


def create_account(db: Session, user_id: int, account_number: str, owner_name: str, broker: str = 'kiwoom', account_type: str = 'paper'):
    enc = get_encryption_service()
    account = Account(
        user_id=user_id,
        account_number_encrypted=enc.encrypt(account_number),
        owner_name=owner_name,
        broker=broker,
        account_type=account_type,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: int, user_id: int) -> bool:
    acc = db.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
    if not acc:
        return False
    acc.is_active = False
    db.commit()
    return True


# ── 봇 ────────────────────────────────────────────────────────────

def get_bots(db: Session, user_id: int):
    return db.query(TradingBot).filter(TradingBot.user_id == user_id).order_by(TradingBot.created_at.desc()).all()


def enrich_bot_assets(db: Session, bot: TradingBot) -> dict:
    """봇 ORM 객체 + 포지션 평가금액(total_assets, holdings_value) 계산 후 dict 반환"""
    import redis as _redis
    from core.config import settings

    cash = float(bot.cash or 0)
    positions = db.query(Position).filter(Position.bot_id == bot.id).all()

    holdings_value = 0.0
    if positions:
        r = _redis.from_url(settings.REDIS_URL)
        for p in positions:
            price_raw = r.get(f'rt:price:{p.ticker}')
            price = float(price_raw) if price_raw else float(p.avg_price or 0)
            holdings_value += price * p.quantity

    total_assets = cash + holdings_value

    d = {c.key: getattr(bot, c.key) for c in bot.__table__.columns}
    d['total_assets'] = round(total_assets, 2)
    d['holdings_value'] = round(holdings_value, 2)
    return d


def get_bot(db: Session, bot_id: int, user_id: int):
    return db.query(TradingBot).filter(TradingBot.id == bot_id, TradingBot.user_id == user_id).first()


def create_bot(db: Session, user_id: int, data: dict):
    initial_cash = data.get('initial_cash', 10_000_000)
    bot = TradingBot(
        user_id=user_id,
        name=data['name'],
        mode=data.get('mode', 'mock'),
        strategy_id=data.get('strategy_id'),
        account_id=data.get('account_id'),
        tickers=data.get('tickers', []),
        initial_cash=initial_cash,
        cash=initial_cash,
        stop_loss_pct=data.get('stop_loss_pct', 5.0),
        take_profit_pct=data.get('take_profit_pct', 10.0),
        max_drawdown_pct=data.get('max_drawdown_pct', 15.0),
        position_size_pct=data.get('position_size_pct', 10.0),
        max_positions=data.get('max_positions', 5),
        max_daily_trades=data.get('max_daily_trades', 20),
        max_order_amount=data.get('max_order_amount', 1_000_000),
        trading_start_time=data.get('trading_start_time'),
        trading_end_time=data.get('trading_end_time'),
        bot_type=data.get('bot_type', 'swing'),
        candle_interval=data.get('candle_interval', 5),
        intraday_close=data.get('intraday_close', False),
        intraday_close_time=data.get('intraday_close_time'),
        trailing_stop_pct=data.get('trailing_stop_pct'),
        confirm_bars=data.get('confirm_bars', 1),
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


def update_bot(db: Session, bot_id: int, user_id: int, data: dict):
    bot = get_bot(db, bot_id, user_id)
    if not bot or bot.status == 'RUNNING':
        return None
    for k, v in data.items():
        setattr(bot, k, v)
    db.commit()
    db.refresh(bot)
    return bot


def delete_bot(db: Session, bot_id: int, user_id: int) -> bool:
    bot = get_bot(db, bot_id, user_id)
    if not bot or bot.status == 'RUNNING':
        return False
    db.delete(bot)
    db.commit()
    return True


def start_bot(db: Session, bot_id: int, user_id: int):
    bot = get_bot(db, bot_id, user_id)
    if not bot or bot.status == 'RUNNING':
        return None
    bot.status = 'RUNNING'
    db.commit()
    db.refresh(bot)
    return bot


def stop_bot(db: Session, bot_id: int, user_id: int):
    bot = get_bot(db, bot_id, user_id)
    if not bot or bot.status not in ('RUNNING', 'ERROR'):
        return None
    bot.status = 'STOPPED'
    db.commit()
    db.refresh(bot)
    return bot


# ── 포지션 / 주문 / 보고서 ─────────────────────────────────────────

def get_positions(db: Session, bot_id: int):
    from models.market import StockPrice
    from sqlalchemy import func
    positions = db.query(Position).filter(Position.bot_id == bot_id).all()
    if not positions:
        return []
    tickers = [p.ticker for p in positions]
    # 최신 날짜 1회 조회 후 해당 날짜 가격 일괄 로드 (N+1 → 2쿼리)
    latest_date = (
        db.query(func.max(StockPrice.date))
        .filter(StockPrice.ticker.in_(tickers))
        .scalar()
    )
    price_map = {}
    if latest_date:
        price_map = {
            sp.ticker: sp
            for sp in db.query(StockPrice)
            .filter(StockPrice.ticker.in_(tickers), StockPrice.date == latest_date)
            .all()
        }
    result = []
    for pos in positions:
        latest = price_map.get(pos.ticker)
        current_price = float(latest.close_price) if latest else float(pos.avg_price)
        avg = float(pos.avg_price)
        unrealized_pnl = (current_price - avg) * pos.quantity
        unrealized_pct = (current_price - avg) / avg * 100 if avg else 0
        result.append({
            'id': pos.id,
            'ticker': pos.ticker,
            'quantity': pos.quantity,
            'avg_price': avg,
            'current_price': current_price,
            'unrealized_pnl': round(unrealized_pnl, 0),
            'unrealized_pct': round(unrealized_pct, 2),
            'market_value': round(current_price * pos.quantity, 0),
            'updated_at': pos.updated_at,
        })
    return result


def get_orders(db: Session, bot_id: int, limit: int = 100):
    return (
        db.query(Order)
        .filter(Order.bot_id == bot_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )


def get_reports(db: Session, bot_id: int, limit: int = 30):
    return (
        db.query(BotReport)
        .filter(BotReport.bot_id == bot_id)
        .order_by(BotReport.date.desc())
        .limit(limit)
        .all()
    )


def get_performance_stats(db: Session, bot: TradingBot) -> dict:
    """봇 종합 성과 통계 계산 (전체 누적 기준)"""
    initial = float(bot.initial_cash or 0)
    cash = float(bot.cash or 0)

    # 전체 매도 체결
    sells = db.query(Execution).filter(
        Execution.bot_id == bot.id,
        Execution.execution_type == 'SELL',
    ).all()

    total_trades = len(sells)
    wins = [e for e in sells if float(e.profit_loss or 0) > 0]
    losses = [e for e in sells if float(e.profit_loss or 0) < 0]

    total_pnl = sum(float(e.profit_loss or 0) for e in sells)
    win_rate = len(wins) / total_trades * 100 if total_trades else 0
    total_return_pct = total_pnl / initial * 100 if initial else 0

    avg_win = sum(float(e.profit_loss) for e in wins) / len(wins) if wins else 0
    avg_loss = sum(float(e.profit_loss) for e in losses) / len(losses) if losses else 0
    best_trade = max((float(e.profit_loss or 0) for e in sells), default=0)
    worst_trade = min((float(e.profit_loss or 0) for e in sells), default=0)
    total_fee = sum(float(e.fee or 0) + float(e.tax or 0) for e in sells)

    total_gain = sum(float(e.profit_loss) for e in wins)
    total_loss_amt = sum(abs(float(e.profit_loss)) for e in losses)
    profit_factor = round(total_gain / total_loss_amt, 4) if total_loss_amt > 0 else (
        round(total_gain, 4) if total_gain > 0 else 0.0
    )

    # MDD / 샤프: 보고서 이력 기반
    from tasks.bot_engine import _calc_mdd, _calc_sharpe
    reports = db.query(BotReport).filter(BotReport.bot_id == bot.id).order_by(BotReport.date).all()
    assets = [float(r.total_assets or 0) for r in reports]
    max_dd = _calc_mdd(assets, initial)

    daily_returns = []
    prev_a = initial
    for r in reports:
        ta = float(r.total_assets or 0)
        if prev_a > 0:
            daily_returns.append((ta - prev_a) / prev_a * 100)
        prev_a = ta
    sharpe = _calc_sharpe(daily_returns)

    return {
        'total_pnl': round(total_pnl, 2),
        'total_return_pct': round(total_return_pct, 2),
        'win_rate': round(win_rate, 2),
        'total_trades': total_trades,
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'best_trade': round(best_trade, 2),
        'worst_trade': round(worst_trade, 2),
        'profit_factor': profit_factor,
        'max_drawdown': round(max_dd, 4),
        'sharpe_ratio': sharpe,
        'total_fee': round(total_fee, 2),
        'current_cash': round(cash, 2),
        'initial_cash': round(initial, 2),
    }
