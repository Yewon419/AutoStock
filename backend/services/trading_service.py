import math
from datetime import time
from sqlalchemy.orm import Session
from models.trading import Account, TradingBot, Order, Execution, Position, BotReport
from core.security import get_encryption_service


# ── bot_type별 프로필 기본값 ───────────────────────────────────────
# Canvas/API에서 값을 명시하지 않으면 아래 프로필이 적용됨.
# 단일 진실원: "bot_type='scalping'이면 단타에 맞는 리스크/타이밍/신호 파라미터 자동 적용".
# 호출자가 명시(None 아님)한 값은 존중 — 프로필로 덮어쓰지 않음.

SCALPING_PROFILE: dict = {
    'stop_loss_pct': 2.0,
    'take_profit_pct': 4.0,
    'max_drawdown_pct': 8.0,
    'position_size_pct': 10.0,
    'max_positions': 5,
    'max_daily_trades': 40,
    'max_order_amount': 1_000_000,
    'trading_start_time': time(9, 0),
    'trading_end_time': time(15, 20),
    'candle_interval': 3,
    'intraday_close': True,
    'intraday_close_time': time(15, 10),
    'trailing_stop_pct': 1.5,
    'confirm_bars': 2,
}

SWING_PROFILE: dict = {
    'stop_loss_pct': 5.0,
    'take_profit_pct': 10.0,
    'max_drawdown_pct': 15.0,
    'position_size_pct': 10.0,
    'max_positions': 5,
    'max_daily_trades': 20,
    'max_order_amount': 1_000_000,
    'trading_start_time': time(9, 0),
    'trading_end_time': time(15, 20),
    'candle_interval': 5,
    'intraday_close': False,
    'intraday_close_time': time(14, 50),
    'trailing_stop_pct': None,
    'confirm_bars': 1,
}


def _apply_profile_defaults(data: dict, db: Session = None) -> dict:
    """bot_type 프로필 기본값을 data에 병합. 우선순위:
    1) 호출자가 명시한 값 (None 아님) — 최우선
    2) strategy.risk_params (AI 팔레트가 전략별 결정)
    3) bot_type 프로필 디폴트 (SCALPING_PROFILE / SWING_PROFILE) — 폴백

    Canvas/API에서 strategy_id만 보내도 AI 팔레트가 정한 SL/TP/MDD 등이 자동 적용됨.
    """
    from models.strategy import Strategy

    bot_type = data.get('bot_type') or 'swing'
    profile = SCALPING_PROFILE if bot_type == 'scalping' else SWING_PROFILE
    merged = dict(data)

    # Strategy.risk_params 로드 (AI 팔레트 결정값) — db가 제공된 경우만
    strategy_rp: dict = {}
    sid = merged.get('strategy_id')
    if db is not None and sid:
        strat = db.query(Strategy).filter(Strategy.id == sid).first()
        if strat and isinstance(strat.risk_params, dict):
            strategy_rp = strat.risk_params

    # 우선순위 적용: 호출자 명시 > strategy.risk_params > 프로필 디폴트
    for key, default_val in profile.items():
        if merged.get(key) is None:
            if key in strategy_rp and strategy_rp[key] is not None:
                merged[key] = strategy_rp[key]
            else:
                merged[key] = default_val

    return merged


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
    # bot_type 프로필 + strategy.risk_params로 미지정 필드 자동 채움.
    # Canvas/API에서 strategy_id만 보내도 AI 팔레트가 결정한 SL/TP/MDD 등이 자동 적용됨.
    merged = _apply_profile_defaults(data, db=db)
    initial_cash = merged.get('initial_cash', 10_000_000)
    bot = TradingBot(
        user_id=user_id,
        name=merged['name'],
        mode=merged.get('mode', 'mock'),
        strategy_id=merged.get('strategy_id'),
        account_id=merged.get('account_id'),
        tickers=merged.get('tickers', []),
        initial_cash=initial_cash,
        cash=initial_cash,
        stop_loss_pct=merged.get('stop_loss_pct'),
        take_profit_pct=merged.get('take_profit_pct'),
        max_drawdown_pct=merged.get('max_drawdown_pct'),
        position_size_pct=merged.get('position_size_pct'),
        max_positions=merged.get('max_positions'),
        max_daily_trades=merged.get('max_daily_trades'),
        max_order_amount=merged.get('max_order_amount'),
        trading_start_time=merged.get('trading_start_time'),
        trading_end_time=merged.get('trading_end_time'),
        bot_type=merged.get('bot_type', 'swing'),
        candle_interval=merged.get('candle_interval'),
        intraday_close=merged.get('intraday_close'),
        intraday_close_time=merged.get('intraday_close_time'),
        trailing_stop_pct=merged.get('trailing_stop_pct'),
        confirm_bars=merged.get('confirm_bars'),
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


def rebaseline_bot(db: Session, bot_id: int, user_id: int):
    """initial_cash를 '현재 현금 + 보유 평가금액'으로 재설정.

    입금/출금 후 position_size_pct, max_drawdown_pct의 기준점을 현재로 스냅.
    RUNNING 중에는 cycle race 위험으로 거부 — 먼저 정지 후 호출.
    """
    bot = get_bot(db, bot_id, user_id)
    if not bot:
        return None
    if bot.status == 'RUNNING':
        return None  # 호출자가 STOPPED 아님을 알 수 있도록 None 반환

    enriched = enrich_bot_assets(db, bot)
    total = float(enriched.get('total_assets') or 0)
    if total <= 0:
        return None
    bot.initial_cash = total
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
