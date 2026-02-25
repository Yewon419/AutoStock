from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.market import Stock, StockPrice, TechnicalIndicator


def get_stocks(
    db: Session,
    search: Optional[str] = None,
    market: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
):
    query = db.query(Stock).filter(Stock.is_active == True)
    if search:
        query = query.filter(
            or_(
                Stock.ticker.ilike(f"%{search}%"),
                Stock.company_name.ilike(f"%{search}%"),
            )
        )
    if market:
        query = query.filter(Stock.market_type == market.upper())

    total = query.count()
    items = query.order_by(Stock.company_name).offset((page - 1) * limit).limit(limit).all()
    return items, total


def get_stock(db: Session, ticker: str) -> Optional[Stock]:
    return db.query(Stock).filter(Stock.ticker == ticker).first()


def get_stock_prices(
    db: Session,
    ticker: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=180)

    return (
        db.query(StockPrice)
        .filter(
            StockPrice.ticker == ticker,
            StockPrice.date >= start_date,
            StockPrice.date <= end_date,
        )
        .order_by(StockPrice.date.asc())
        .all()
    )


def get_stock_indicators(
    db: Session,
    ticker: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=180)

    return (
        db.query(TechnicalIndicator)
        .filter(
            TechnicalIndicator.ticker == ticker,
            TechnicalIndicator.date >= start_date,
            TechnicalIndicator.date <= end_date,
        )
        .order_by(TechnicalIndicator.date.asc())
        .all()
    )
