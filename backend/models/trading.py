from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Time, DECIMAL, Text, ForeignKey, Numeric, Index, JSON
from sqlalchemy.sql import func
from core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_number_encrypted = Column(String(500), nullable=False)
    owner_name = Column(String(100), nullable=False)
    broker = Column(String(20), default="kiwoom")
    account_type = Column(String(10), default="paper")  # paper=모의투자 | real=실계좌
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TradingBot(Base):
    __tablename__ = "trading_bots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="STOPPED")   # RUNNING | STOPPED | ERROR
    mode = Column(String(10), default="mock")          # mock | paper | real
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"))
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"))

    # 리스크 설정
    stop_loss_pct = Column(DECIMAL(5, 2), default=5.00)
    take_profit_pct = Column(DECIMAL(5, 2), default=10.00)
    max_drawdown_pct = Column(DECIMAL(5, 2), default=15.00)
    position_size_pct = Column(DECIMAL(5, 2), default=10.00)
    max_positions = Column(Integer, default=10)
    max_daily_trades = Column(Integer, default=20)

    # 거래 시간
    trading_start_time = Column(Time, default=func.cast("09:00:00", Time))
    trading_end_time = Column(Time, default=func.cast("15:20:00", Time))

    # 단타 설정
    bot_type = Column(String(10), default='swing')          # swing | scalping
    candle_interval = Column(Integer, default=5)             # 분봉 단위 (1,3,5,10,15)
    intraday_close = Column(Boolean, default=False)          # 당일 강제 청산 여부
    intraday_close_time = Column(Time, default=func.cast("14:50:00", Time))
    trailing_stop_pct = Column(DECIMAL(5, 2), default=None)  # 트레일링 스탑 % (None=비활성화)
    confirm_bars = Column(Integer, default=1)                 # 연속 신호 확인 봉 수 (1=즉시 진입)

    # 가상 자금 (mock/paper 모드)
    tickers = Column(JSON, default=list)
    initial_cash = Column(Numeric(15, 2), default=10_000_000)
    cash = Column(Numeric(15, 2), default=10_000_000)
    max_order_amount = Column(Numeric(15, 2), default=1_000_000)  # 단일 주문 최대 금액

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_trading_bots_user_id", "user_id"),
        Index("idx_trading_bots_status", "status"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("trading_bots.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(10), nullable=False)
    order_type = Column(String(10), nullable=False)  # BUY | SELL
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), default=0)  # 0 = 시장가
    status = Column(String(20), default="PENDING")  # PENDING | FILLED | CANCELLED | FAILED
    order_number = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    bot_id = Column(Integer, ForeignKey("trading_bots.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(10), nullable=False)
    execution_type = Column(String(10), nullable=False)  # BUY | SELL
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    fee = Column(DECIMAL(10, 2), default=0)
    tax = Column(DECIMAL(10, 2), default=0)
    profit_loss = Column(DECIMAL(12, 2))
    profit_loss_pct = Column(DECIMAL(7, 4))   # 손익률 (%) — 매도 시 기록
    executed_at = Column(DateTime(timezone=True), nullable=False)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("trading_bots.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(DECIMAL(10, 2), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_positions_bot_id", "bot_id"),
    )


class BotReport(Base):
    __tablename__ = "bot_reports"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("trading_bots.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    total_assets = Column(DECIMAL(15, 2))
    cash = Column(DECIMAL(15, 2))
    holdings_value = Column(DECIMAL(15, 2))
    daily_pnl = Column(DECIMAL(12, 2))
    total_pnl = Column(DECIMAL(12, 2))
    win_rate = Column(DECIMAL(5, 2))
    total_trades = Column(Integer, default=0)
    max_drawdown = Column(DECIMAL(8, 4))    # 최대 낙폭 (%) — 초기 자금 대비 최저점
    sharpe_ratio = Column(DECIMAL(8, 4))    # 샤프 비율 (일별 수익률 기반)
    profit_factor = Column(DECIMAL(8, 4))   # 손익비 (총수익 / 총손실)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
