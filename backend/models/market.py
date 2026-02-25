from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, DECIMAL
from sqlalchemy.sql import func
from core.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    ticker = Column(String(10), primary_key=True, index=True)
    company_name = Column(String(200), nullable=False)
    market_type = Column(String(10), nullable=False)  # KOSPI | KOSDAQ
    sector = Column(String(100))
    industry = Column(String(100))
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class StockPrice(Base):
    __tablename__ = "stock_prices"

    ticker = Column(String(10), primary_key=True)
    date = Column(Date, primary_key=True)
    open_price = Column(DECIMAL(10, 2))
    high_price = Column(DECIMAL(10, 2))
    low_price = Column(DECIMAL(10, 2))
    close_price = Column(DECIMAL(10, 2), nullable=False)
    volume = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    ticker = Column(String(10), primary_key=True)
    date = Column(Date, primary_key=True)
    rsi = Column(DECIMAL(6, 2))
    macd = Column(DECIMAL(10, 4))
    macd_signal = Column(DECIMAL(10, 4))
    macd_histogram = Column(DECIMAL(10, 4))
    stoch_k = Column(DECIMAL(6, 2))
    stoch_d = Column(DECIMAL(6, 2))
    bollinger_upper = Column(DECIMAL(10, 2))
    bollinger_middle = Column(DECIMAL(10, 2))
    bollinger_lower = Column(DECIMAL(10, 2))
    ma_20 = Column(DECIMAL(10, 2))
    ma_50 = Column(DECIMAL(10, 2))
    ma_200 = Column(DECIMAL(10, 2))
    atr = Column(DECIMAL(10, 4))
    adx = Column(DECIMAL(6, 2))
    obv = Column(DECIMAL(15, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
