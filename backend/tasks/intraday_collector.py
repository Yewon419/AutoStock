"""
분봉 실시간 수집 & 지표 계산
- 장 시간 중 1분마다 실행
- RUNNING 상태 scalping 봇의 ticker 분봉을 KIS API로 수집
- 분봉 지표(RSI, MACD, BB, MA, 거래량비율, 시가대비등락) 계산 후 Redis 저장
"""
import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import redis

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot
from models.market import StockPrice

logger = logging.getLogger(__name__)

SEOUL = ZoneInfo("Asia/Seoul")
_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

CANDLE_TTL = 8 * 3600   # 8시간
MAX_CANDLES = 200        # 최대 보관 캔들 수


# ── Redis 키 헬퍼 ─────────────────────────────────────────────────────

def _candle_key(ticker: str, interval: int) -> str:
    return f"rt:candles:{ticker}:{interval}"


def _ind_key(ticker: str, interval: int) -> str:
    return f"rt:ind:{ticker}:{interval}"


# ── 캔들 데이터 수집 ──────────────────────────────────────────────────

def _fetch_candles(ticker: str, interval: int, mode: str, ref_price: float = None) -> list[dict]:
    """실제 KIS 또는 mock 캔들 반환"""
    if mode == "mock" or not settings.KIS_APP_KEY:
        return _mock_candles(ticker, interval, ref_price)

    try:
        from broker.kis_broker import KisBroker
        broker = KisBroker()
        return broker.get_minute_candles(ticker, interval)
    except Exception as e:
        logger.warning("[intraday_collector] KIS 분봉 수집 실패 %s: %s — mock으로 대체", ticker, e)
        return _mock_candles(ticker, interval, ref_price)


def _mock_candles(ticker: str, interval: int, ref_price: float = None) -> list[dict]:
    """실제 종가(ref_price) 기반 더미 캔들 생성.

    과매도 + 거래량 급증 패턴 (i=0 오래된 봉 → i=199 최신 봉):
      1) 횡보 (i=0~89):    ±0.3%, 중간 거래량 (800~2500)
      2) 하락 (i=90~197):  편향 하락, 거래량 감소 (100~400) → 20봉 평균 낮아짐
      3) 최신 2봉 (i=198~199): 50% 확률로 거래량 폭발 (5000~10000)
         → volume_ratio = 7500 / ~250(20봉평균) ≈ 30 >> 1.5
         → RSI는 90봉 하락으로 35 이하 유지

    매 분 새로 생성(mock 모드 merge 미사용)하므로 확률적으로 신호 발생.
    ref_price: DB 실제 종가 → 없으면 rt:price → 없으면 1000원 기본값
    """
    if ref_price is None:
        rt = _redis_client.get(f"rt:price:{ticker}")
        ref_price = float(rt) if rt else 1_000.0
    base_price = ref_price

    peak_price = round(base_price * random.uniform(1.08, 1.15), 0)

    candles = []
    price = peak_price
    total = MAX_CANDLES  # 200봉

    # 최신 2봉의 거래량 급등 여부 결정 (50% 확률)
    spike = random.random() < 0.5

    for i in range(total):
        if i < 90:
            chg = random.uniform(-0.003, 0.003)
            vol = random.randint(800, 2500)
        elif i < 198:
            # 하락 + 낮은 거래량 → 20봉 이동평균을 낮게 유지
            chg = random.uniform(-0.004, 0.0005)
            vol = random.randint(100, 400)
        else:
            # 최신 2봉: spike 시 거래량 폭발, 아닐 시 계속 낮음
            chg = random.uniform(-0.003, 0.001)
            vol = random.randint(5000, 10000) if spike else random.randint(100, 400)

        open_p = price
        close_p = round(price * (1 + chg), 0)
        high_p = round(max(open_p, close_p) * (1 + random.uniform(0, 0.002)), 0)
        low_p = round(min(open_p, close_p) * (1 - random.uniform(0, 0.002)), 0)
        candles.append({
            "t": f"{9 + i // 60:02d}:{i % 60:02d}",
            "o": open_p,
            "h": high_p,
            "l": low_p,
            "c": close_p,
            "v": vol,
        })
        price = close_p

    # 최신순 정렬
    candles.reverse()
    return candles


# ── 캔들 Redis 저장/로드 ──────────────────────────────────────────────

def _load_candles(ticker: str, interval: int) -> list[dict]:
    raw = _redis_client.get(_candle_key(ticker, interval))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _save_candles(ticker: str, interval: int, candles: list[dict]):
    trimmed = candles[:MAX_CANDLES]
    _redis_client.setex(_candle_key(ticker, interval), CANDLE_TTL, json.dumps(trimmed))


def _merge_candles(existing: list[dict], new_candles: list[dict]) -> list[dict]:
    """새 캔들을 기존 목록에 병합 (중복 시각 제거, 최신순 유지)"""
    seen = {c["t"] for c in existing}
    merged = list(existing)
    for c in new_candles:
        if c["t"] not in seen:
            merged.append(c)
            seen.add(c["t"])
    # 최신순 정렬
    merged.sort(key=lambda x: x["t"], reverse=True)
    return merged[:MAX_CANDLES]


# ── 지표 계산 ─────────────────────────────────────────────────────────

def _calc_indicators(candles: list[dict], ticker: str) -> dict:
    """ta 라이브러리로 분봉 지표 계산. 실패 시 빈 dict 반환."""
    if len(candles) < 26:
        return {}

    try:
        import pandas as pd
        import ta

        # 최신순 → 시간순 정렬
        df = pd.DataFrame(reversed(candles))
        df["c"] = df["c"].astype(float)
        df["h"] = df["h"].astype(float)
        df["l"] = df["l"].astype(float)
        df["o"] = df["o"].astype(float)
        df["v"] = df["v"].astype(float)

        close = df["c"]
        high = df["h"]
        low = df["l"]
        volume = df["v"]

        # RSI(14)
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()

        # MACD(12,26,9)
        macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_series = macd_obj.macd()
        macd_signal_series = macd_obj.macd_signal()
        macd_hist_series = macd_obj.macd_diff()

        # Bollinger Bands(20,2)
        bb_obj = ta.volatility.BollingerBands(close, window=20, window_dev=2)

        # MA(5,10,20)
        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()

        # 거래량 비율 (현재/20봉평균)
        vol_ma20 = volume.rolling(20).mean()
        vol_ratio = volume / vol_ma20.replace(0, float("nan"))

        # 시가 대비 등락률 (가장 오래된 봉 기준 시가)
        open_price = float(df["o"].iloc[0])
        curr_price = float(close.iloc[-1])
        opening_gap = round((curr_price - open_price) / open_price * 100, 4) if open_price else 0.0

        def _last(series):
            return round(float(series.iloc[-1]), 4) if not series.empty else None

        def _prev(series):
            return round(float(series.iloc[-2]), 4) if len(series) >= 2 else None

        return {
            "rsi": _last(rsi_series),
            "prev_rsi": _prev(rsi_series),
            "macd": _last(macd_series),
            "prev_macd": _prev(macd_series),
            "macd_signal": _last(macd_signal_series),
            "prev_macd_signal": _prev(macd_signal_series),
            "macd_histogram": _last(macd_hist_series),
            "prev_macd_histogram": _prev(macd_hist_series),
            "bollinger_upper": _last(bb_obj.bollinger_hband()),
            "bollinger_middle": _last(bb_obj.bollinger_mavg()),
            "bollinger_lower": _last(bb_obj.bollinger_lband()),
            "prev_bollinger_upper": _prev(bb_obj.bollinger_hband()),
            "prev_bollinger_lower": _prev(bb_obj.bollinger_lband()),
            "ma_5": _last(ma5),
            "prev_ma_5": _prev(ma5),
            "ma_10": _last(ma10),
            "prev_ma_10": _prev(ma10),
            "ma_20": _last(ma20),
            "prev_ma_20": _prev(ma20),
            "volume_ratio": _last(vol_ratio),
            "opening_gap": opening_gap,
        }

    except ImportError:
        logger.warning("[intraday_collector] ta 라이브러리 없음 — 지표 계산 생략")
        return {}
    except Exception as e:
        logger.error("[intraday_collector] 지표 계산 오류 %s: %s", ticker, e, exc_info=True)
        return {}


# ── Celery 태스크 ─────────────────────────────────────────────────────

@celery_app.task(name="tasks.intraday_collector.collect_intraday_data")
def collect_intraday_data():
    """장 시간 중 1분마다 실행 — RUNNING scalping 봇의 ticker 분봉 수집 & 지표 계산"""
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(
            TradingBot.status == "RUNNING",
            TradingBot.bot_type == "scalping",
        ).all()

        if not bots:
            return

        # ticker별 고유 수집 (여러 봇이 같은 ticker를 가질 수 있음)
        ticker_intervals: dict[tuple, str] = {}
        for bot in bots:
            interval = int(bot.candle_interval or 1)
            mode = getattr(bot, "mode", "mock")
            for ticker in (bot.tickers or []):
                key = (ticker, interval)
                if key not in ticker_intervals:
                    ticker_intervals[key] = mode

        # mock 모드용: DB 실제 종가 일괄 조회 (가격 괴리 방지)
        all_tickers = [t for (t, _) in ticker_intervals.keys()]
        db_prices: dict[str, float] = {}
        if any(m == "mock" for m in ticker_intervals.values()):
            rows = (
                db.query(StockPrice.ticker, StockPrice.close_price)
                .distinct(StockPrice.ticker)
                .filter(StockPrice.ticker.in_(all_tickers))
                .order_by(StockPrice.ticker, StockPrice.date.desc())
                .all()
            )
            db_prices = {r.ticker: float(r.close_price) for r in rows}

        logger.info("[intraday_collector] 분봉 수집 시작 — %d 종목", len(ticker_intervals))

        for (ticker, interval), mode in ticker_intervals.items():
            try:
                ref_price = db_prices.get(ticker) if mode == "mock" else None
                new_candles = _fetch_candles(ticker, interval, mode, ref_price)
                if not new_candles:
                    continue

                # mock 모드: 매 분 새 패턴 생성 (merge 불필요)
                if mode == "mock":
                    merged = new_candles
                else:
                    existing = _load_candles(ticker, interval)
                    merged = _merge_candles(existing, new_candles)
                _save_candles(ticker, interval, merged)

                indicators = _calc_indicators(merged, ticker)
                if indicators:
                    _redis_client.setex(
                        _ind_key(ticker, interval),
                        CANDLE_TTL,
                        json.dumps(indicators),
                    )
                    logger.debug("[intraday_collector] 지표 저장 %s:%d rsi=%.1f",
                                 ticker, interval, indicators.get("rsi") or 0)

            except Exception as e:
                logger.error("[intraday_collector] %s:%d 오류: %s", ticker, interval, e, exc_info=True)

    finally:
        db.close()
