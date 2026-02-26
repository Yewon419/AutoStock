import logging
from datetime import date, timedelta

from tasks.celery_app import celery_app
from core.database import SessionLocal
from models.market import Stock, StockPrice

logger = logging.getLogger(__name__)


def _safe_float(val):
    """NaN/None 안전 변환"""
    try:
        result = float(val)
        return None if result != result else result  # NaN 체크
    except (TypeError, ValueError):
        return None


def _upsert_stock(db, ticker: str, name: str, market: str):
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if stock:
        stock.company_name = name
        stock.market_type = market
        stock.is_active = True
    else:
        db.add(Stock(ticker=ticker, company_name=name, market_type=market))


def _get_recent_trading_date():
    """데이터가 있는 가장 최근 거래일 반환 (최대 10일 전까지 탐색)"""
    from pykrx import stock as krx
    for delta in range(0, 10):
        d = (date.today() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            tickers = krx.get_market_ticker_list(d, market="KOSPI")
            if tickers:
                return d
        except Exception:
            continue
    return None


@celery_app.task(name="tasks.collect.collect_missing_data")
def collect_missing_data():
    """
    가장 최근 거래일 데이터가 DB에 없으면 수집 트리거.
    매일 아침 9시 및 서비스 재시작 시 실행되어 누락된 날 자동 보완.
    """
    db = SessionLocal()
    try:
        trading_date = _get_recent_trading_date()
        if not trading_date:
            logger.warning("[collect_missing_data] 최근 거래일 확인 불가")
            return {"status": "no_trading_date"}

        target = date(int(trading_date[:4]), int(trading_date[4:6]), int(trading_date[6:]))
        count = db.query(StockPrice).filter(StockPrice.date == target).count()

        if count == 0:
            logger.info(f"[collect_missing_data] {trading_date} 누락 → 수집 시작")
            collect_all_stocks.delay()
            return {"status": "triggered", "date": trading_date}
        else:
            logger.info(f"[collect_missing_data] {trading_date} 이미 존재 ({count}건) → 스킵")
            return {"status": "ok", "date": trading_date, "count": count}
    finally:
        db.close()


@celery_app.task(name="tasks.collect.collect_all_stocks", bind=True, max_retries=3)
def collect_all_stocks(self):
    """
    전체 종목 목록 수집 후 각 종목의 가격 데이터 수집 트리거.
    평일 16:30에 celery-beat가 자동 실행.
    """
    try:
        from pykrx import stock as krx

        trading_date = _get_recent_trading_date()
        if not trading_date:
            logger.error("[collect_all_stocks] 최근 거래일 데이터를 찾을 수 없습니다")
            return {"status": "error", "message": "no trading date found"}
        logger.info(f"[collect_all_stocks] 시작: {trading_date}")

        db = SessionLocal()
        try:
            # KOSPI + KOSDAQ 종목 목록 수집
            all_tickers = []
            for market in ["KOSPI", "KOSDAQ"]:
                tickers = krx.get_market_ticker_list(trading_date, market=market)
                for ticker in tickers:
                    name = krx.get_market_ticker_name(ticker)
                    _upsert_stock(db, ticker, name, market)
                    all_tickers.append(ticker)
                logger.info(f"  {market}: {len(tickers)}개 종목")

            db.commit()
            logger.info(f"[collect_all_stocks] 종목 저장 완료: 총 {len(all_tickers)}개")
        finally:
            db.close()

        # 각 종목 가격 데이터 수집 (개별 태스크로 분산)
        for ticker in all_tickers:
            collect_stock_prices.delay(ticker)

        return {"status": "success", "ticker_count": len(all_tickers)}

    except Exception as exc:
        logger.error(f"[collect_all_stocks] 오류: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.collect.collect_stock_prices", bind=True, max_retries=3)
def collect_stock_prices(self, ticker: str, days: int = 365):
    """
    특정 종목의 OHLCV 데이터 수집 후 지표 계산 트리거.
    """
    try:
        from pykrx import stock as krx

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        df = krx.get_market_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            ticker,
        )

        if df is None or df.empty:
            logger.warning(f"[collect_stock_prices] 데이터 없음: {ticker}")
            return {"status": "no_data", "ticker": ticker}

        db = SessionLocal()
        try:
            saved = 0
            for idx, row in df.iterrows():
                price_date = idx.date() if hasattr(idx, "date") else idx
                existing = (
                    db.query(StockPrice)
                    .filter(StockPrice.ticker == ticker, StockPrice.date == price_date)
                    .first()
                )
                values = {
                    "open_price": _safe_float(row.get("시가", row.get("Open"))),
                    "high_price": _safe_float(row.get("고가", row.get("High"))),
                    "low_price": _safe_float(row.get("저가", row.get("Low"))),
                    "close_price": _safe_float(row.get("종가", row.get("Close"))),
                    "volume": int(row.get("거래량", row.get("Volume", 0)) or 0),
                }
                if values["close_price"] is None:
                    continue

                if existing:
                    for k, v in values.items():
                        setattr(existing, k, v)
                else:
                    db.add(StockPrice(ticker=ticker, date=price_date, **values))
                saved += 1

            db.commit()
            logger.info(f"[collect_stock_prices] {ticker}: {saved}건 저장")
        finally:
            db.close()

        # 지표 계산 트리거
        from tasks.indicators import calculate_indicators
        calculate_indicators.delay(ticker)

        return {"status": "success", "ticker": ticker, "rows": saved}

    except Exception as exc:
        logger.error(f"[collect_stock_prices] {ticker} 오류: {exc}")
        raise self.retry(exc=exc, countdown=30)
