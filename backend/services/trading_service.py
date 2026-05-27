import math
from datetime import time, date as _date
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
    2) strategy.risk_params (캔버스 AI가 결정한 봇 단위 값)
    3) bot_type 프로필 디폴트 (SCALPING_PROFILE / SWING_PROFILE) — 폴백

    봇 1:1 모델: 봇 생성 직후엔 strategy.risk_params가 비어있어 (3)으로 폴백.
    이후 캔버스에서 AI 생성·튜닝 시 (2)로 끌어올려짐.
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
    """봇 ORM 객체 + 포지션 평가금액(total_assets, holdings_value) 계산 후 dict 반환.

    평가 fallback: rt:price(실시간) → StockPrice 최신 close(휴장·오프타임) → avg_price.
    StockPrice fallback이 없으면 휴장 시 book value만 보여 평가손익이 항상 0으로 표시되던 버그가 있었음.
    """
    import redis as _redis
    from core.config import settings
    from models.market import StockPrice

    cash = float(bot.cash or 0)
    positions = db.query(Position).filter(Position.bot_id == bot.id).all()

    holdings_value = 0.0
    if positions:
        r = _redis.from_url(settings.REDIS_URL)
        for p in positions:
            price_raw = r.get(f'rt:price:{p.ticker}')
            if price_raw:
                price = float(price_raw)
            else:
                lp = (
                    db.query(StockPrice)
                    .filter(StockPrice.ticker == p.ticker)
                    .order_by(StockPrice.date.desc())
                    .first()
                )
                if lp and lp.close_price is not None:
                    price = float(lp.close_price)
                else:
                    price = float(p.avg_price or 0)
            holdings_value += price * p.quantity

    total_assets = cash + holdings_value

    # 당일 평가손익 (전일대비). 어제 BotReport 없으면 initial_cash baseline (첫날 처리).
    prev_report = (
        db.query(BotReport)
        .filter(BotReport.bot_id == bot.id, BotReport.date < _date.today())
        .order_by(BotReport.date.desc())
        .first()
    )
    if prev_report and prev_report.total_assets:
        prev_assets = float(prev_report.total_assets)
    else:
        prev_assets = float(bot.initial_cash or 0)
    today_pnl = total_assets - prev_assets
    today_pnl_pct = (today_pnl / prev_assets * 100) if prev_assets > 0 else 0.0

    d = {c.key: getattr(bot, c.key) for c in bot.__table__.columns}
    d['total_assets'] = round(total_assets, 2)
    d['holdings_value'] = round(holdings_value, 2)
    d['today_pnl'] = round(today_pnl, 2)
    d['today_pnl_pct'] = round(today_pnl_pct, 2)
    return d


def get_bot(db: Session, bot_id: int, user_id: int):
    return db.query(TradingBot).filter(TradingBot.id == bot_id, TradingBot.user_id == user_id).first()


def create_bot(db: Session, user_id: int, data: dict):
    # 봇 1:1 모델: 봇 생성 시 빈 strategy 동반 생성. strategy_id 인자는 무시.
    # bot_type 프로필 디폴트 적용 (생성 직후 strategy.risk_params는 비어있음).
    from models.strategy import Strategy

    data.pop('strategy_id', None)
    merged = _apply_profile_defaults(data, db=db)
    initial_cash = merged.get('initial_cash', 10_000_000)
    bot_type = merged.get('bot_type', 'swing')

    bot = TradingBot(
        user_id=user_id,
        name=merged['name'],
        mode=merged.get('mode', 'mock'),
        strategy_id=None,  # flush 후 동반 strategy 생성한 뒤 채움
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
        bot_type=bot_type,
        candle_interval=merged.get('candle_interval'),
        intraday_close=merged.get('intraday_close'),
        intraday_close_time=merged.get('intraday_close_time'),
        trailing_stop_pct=merged.get('trailing_stop_pct'),
        confirm_bars=merged.get('confirm_bars'),
    )
    db.add(bot)
    db.flush()  # bot.id 확보 (commit 아님)

    strategy = Strategy(
        user_id=user_id,
        bot_id=bot.id,
        name=f"{bot.name} 전략",
        conditions=[],
        strategy_type=bot_type,
        source='manual',
    )
    db.add(strategy)
    db.flush()

    bot.strategy_id = strategy.id
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
    """포지션 목록 + 한국 증권사 baseline 필드 확장.

    현재가: rt:price(실시간) → StockPrice 최신 close(휴장·오프타임) → avg_price 3단 fallback
    (enrich_bot_assets와 동일 정책).
    """
    import redis as _redis
    from core.config import settings
    from models.market import StockPrice, Stock

    positions = db.query(Position).filter(Position.bot_id == bot_id).all()
    if not positions:
        return []
    tickers = [p.ticker for p in positions]

    # 최신 2개 거래일 일괄 로드 — 전일대비 계산
    distinct_dates = [
        d for (d,) in (
            db.query(StockPrice.date)
            .filter(StockPrice.ticker.in_(tickers))
            .distinct()
            .order_by(StockPrice.date.desc())
            .limit(2)
            .all()
        )
    ]
    price_map: dict[str, dict] = {}
    if distinct_dates:
        for sp in (
            db.query(StockPrice)
            .filter(StockPrice.ticker.in_(tickers), StockPrice.date.in_(distinct_dates))
            .all()
        ):
            price_map.setdefault(sp.ticker, {})[sp.date] = float(sp.close_price)
    latest_date = distinct_dates[0] if distinct_dates else None
    prev_date = distinct_dates[1] if len(distinct_dates) > 1 else None

    # 회사명 일괄 로드
    name_map = {
        s.ticker: s.company_name
        for s in db.query(Stock).filter(Stock.ticker.in_(tickers)).all()
    }

    # 실시간가 일괄 로드 (Redis pipeline)
    r = _redis.from_url(settings.REDIS_URL)
    rt_raw = r.mget([f'rt:price:{t}' for t in tickers])
    rt_map = {
        t: float(raw) for t, raw in zip(tickers, rt_raw) if raw is not None
    }

    # 1차 패스: 현재가 결정 + market_value 합산 (비중 분모)
    enriched = []
    total_market_value = 0.0
    for pos in positions:
        ticker_prices = price_map.get(pos.ticker, {})
        sp_close = ticker_prices.get(latest_date) if latest_date else None
        current_price = (
            rt_map.get(pos.ticker)
            or sp_close
            or float(pos.avg_price)
        )
        prev_close = ticker_prices.get(prev_date) if prev_date else None
        avg = float(pos.avg_price)
        market_value = current_price * pos.quantity
        total_market_value += market_value
        enriched.append((pos, current_price, prev_close, avg, market_value))

    # 2차 패스: 응답 생성 (비중 계산)
    result = []
    for pos, current_price, prev_close, avg, market_value in enriched:
        unrealized_pnl = (current_price - avg) * pos.quantity
        unrealized_pct = (current_price - avg) / avg * 100 if avg else 0
        if prev_close is not None and prev_close > 0:
            day_change = current_price - prev_close
            day_change_pct = (current_price - prev_close) / prev_close * 100
        else:
            day_change = None
            day_change_pct = None
        weight_pct = (market_value / total_market_value * 100) if total_market_value > 0 else 0
        result.append({
            'id': pos.id,
            'ticker': pos.ticker,
            'company_name': name_map.get(pos.ticker, pos.ticker),
            'quantity': pos.quantity,
            'avg_price': avg,
            'current_price': current_price,
            'prev_close': prev_close,
            'day_change': round(day_change, 2) if day_change is not None else None,
            'day_change_pct': round(day_change_pct, 2) if day_change_pct is not None else None,
            'buy_amount': round(avg * pos.quantity, 0),
            'unrealized_pnl': round(unrealized_pnl, 0),
            'unrealized_pct': round(unrealized_pct, 2),
            'market_value': round(market_value, 0),
            'weight_pct': round(weight_pct, 2),
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
