import logging
import pandas as pd
import ta

from tasks.celery_app import celery_app
from core.database import SessionLocal
from models.market import StockPrice, TechnicalIndicator

logger = logging.getLogger(__name__)

INDICATOR_COLS = [
    "rsi", "macd", "macd_signal", "macd_histogram",
    "stoch_k", "stoch_d",
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_20", "ma_50", "ma_200",
    "atr", "adx", "obv",
]


def _safe(val):
    """pandas NaN/inf → None 변환 (DB DECIMAL 오버플로우 방지)"""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f or f == float('inf') or f == float('-inf'):
            return None
        return f
    except (TypeError, ValueError):
        return None


@celery_app.task(name="tasks.indicators.calculate_indicators", bind=True, max_retries=3)
def calculate_indicators(self, ticker: str):
    """
    DB에 저장된 가격 데이터로 기술적 지표를 계산하고 저장.
    MA200 계산을 위해 최소 20일 이상 데이터 필요.
    """
    db = SessionLocal()
    try:
        prices = (
            db.query(StockPrice)
            .filter(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.asc())
            .all()
        )

        if len(prices) < 20:
            logger.warning(f"[calculate_indicators] {ticker}: 데이터 부족 ({len(prices)}건)")
            return {"status": "insufficient_data", "ticker": ticker}

        # DataFrame 변환
        df = pd.DataFrame([
            {
                "date": p.date,
                "open": float(p.open_price or 0),
                "high": float(p.high_price or 0),
                "low": float(p.low_price or 0),
                "close": float(p.close_price),
                "volume": float(p.volume or 0),
            }
            for p in prices
        ])
        df.set_index("date", inplace=True)

        # --- 지표 계산 (ta 라이브러리) ---
        # RSI
        df["rsi"] = ta.momentum.rsi(df["close"], window=14)

        # MACD
        df["macd"] = ta.trend.macd(df["close"], window_slow=26, window_fast=12)
        df["macd_signal"] = ta.trend.macd_signal(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_histogram"] = ta.trend.macd_diff(df["close"], window_slow=26, window_fast=12, window_sign=9)

        # Stochastic
        df["stoch_k"] = ta.momentum.stoch(df["high"], df["low"], df["close"], window=14, smooth_window=3)
        df["stoch_d"] = ta.momentum.stoch_signal(df["high"], df["low"], df["close"], window=14, smooth_window=3)

        # Bollinger Bands
        df["bollinger_upper"] = ta.volatility.bollinger_hband(df["close"], window=20, window_dev=2)
        df["bollinger_middle"] = ta.volatility.bollinger_mavg(df["close"], window=20)
        df["bollinger_lower"] = ta.volatility.bollinger_lband(df["close"], window=20, window_dev=2)

        # Moving Averages
        df["ma_20"] = ta.trend.sma_indicator(df["close"], window=20)
        df["ma_50"] = ta.trend.sma_indicator(df["close"], window=50)
        df["ma_200"] = ta.trend.sma_indicator(df["close"], window=200)

        # ATR
        df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)

        # ADX
        df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"], window=14)

        # OBV
        df["obv"] = ta.volume.on_balance_volume(df["close"], df["volume"])

        # --- DB 저장 ---
        saved = 0
        for date_idx, row in df.iterrows():
            values = {col: _safe(row.get(col)) for col in INDICATOR_COLS}

            existing = (
                db.query(TechnicalIndicator)
                .filter(
                    TechnicalIndicator.ticker == ticker,
                    TechnicalIndicator.date == date_idx,
                )
                .first()
            )

            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                db.add(TechnicalIndicator(ticker=ticker, date=date_idx, **values))
            saved += 1

        db.commit()
        logger.info(f"[calculate_indicators] {ticker}: {saved}건 저장")
        return {"status": "success", "ticker": ticker, "rows": saved}

    except Exception as exc:
        logger.error(f"[calculate_indicators] {ticker} 오류: {exc}")
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
