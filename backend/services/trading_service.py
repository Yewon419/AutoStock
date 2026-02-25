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
    positions = db.query(Position).filter(Position.bot_id == bot_id).all()
    result = []
    for pos in positions:
        latest = (
            db.query(StockPrice)
            .filter(StockPrice.ticker == pos.ticker)
            .order_by(StockPrice.date.desc())
            .first()
        )
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
