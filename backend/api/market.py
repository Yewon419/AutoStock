from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User
from services import market_service

router = APIRouter(prefix="/market", tags=["market"])


# --- 응답 스키마 ---

class StockResponse(BaseModel):
    ticker: str
    company_name: str
    market_type: str
    sector: Optional[str] = None
    industry: Optional[str] = None

    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[StockResponse]


class PriceResponse(BaseModel):
    date: date
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: float
    volume: Optional[int] = None

    class Config:
        from_attributes = True


class IndicatorResponse(BaseModel):
    date: date
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    ma_200: Optional[float] = None
    atr: Optional[float] = None
    adx: Optional[float] = None
    obv: Optional[float] = None

    class Config:
        from_attributes = True


# --- 엔드포인트 ---

@router.get("/stocks", response_model=StockListResponse)
def list_stocks(
    search: Optional[str] = Query(None, description="종목명 또는 티커 검색"),
    market: Optional[str] = Query(None, description="KOSPI 또는 KOSDAQ"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = market_service.get_stocks(db, search, market, page, limit)
    return StockListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[StockResponse.model_validate(s) for s in items],
    )


@router.get("/stocks/{ticker}", response_model=StockResponse)
def get_stock(
    ticker: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stock = market_service.get_stock(db, ticker)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="종목을 찾을 수 없습니다")
    return StockResponse.model_validate(stock)


@router.get("/stocks/{ticker}/prices", response_model=list[PriceResponse])
def get_prices(
    ticker: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    prices = market_service.get_stock_prices(db, ticker, start_date, end_date)
    return [PriceResponse.model_validate(p) for p in prices]


@router.get("/stocks/{ticker}/indicators", response_model=list[IndicatorResponse])
def get_indicators(
    ticker: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    indicators = market_service.get_stock_indicators(db, ticker, start_date, end_date)
    return [IndicatorResponse.model_validate(i) for i in indicators]


@router.post("/collect")
def trigger_collect(
    ticker: Optional[str] = Query(None, description="특정 종목만 수집 (없으면 전체)"),
    _: User = Depends(get_current_user),
):
    """
    수동 데이터 수집 트리거.
    ticker 지정 시 해당 종목만, 미지정 시 전체 종목 수집.
    """
    from tasks.collect import collect_all_stocks, collect_stock_prices

    if ticker:
        task = collect_stock_prices.delay(ticker)
        return {"status": "queued", "task_id": str(task.id), "ticker": ticker}
    else:
        task = collect_all_stocks.delay()
        return {"status": "queued", "task_id": str(task.id), "message": "전체 종목 수집 시작"}
