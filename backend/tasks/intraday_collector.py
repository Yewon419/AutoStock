"""
분봉 실시간 수집 & 지표 계산
- 장 시간 중 1분마다 실행
- RUNNING 상태 scalping 봇의 ticker 분봉을 KIS API로 수집
- 분봉 지표(RSI, MACD, BB, MA, 거래량비율, 시가대비등락) 계산 후 Redis 저장
"""
import json
import logging
import random
import time as _time
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


# ── mock 시나리오 패턴 매트릭스 ─────────────────────────────────────
# scalping 전략 strategy.pattern과 1:1 매핑. (ticker, 분봉_시각) 쌍 결정론 분기 →
# 같은 분 내 같은 ticker는 항상 같은 패턴, 매분 패턴 순환. KIS 활성 종목이 소수여도
# 시간이 흐르면 각 봇의 패턴에 매핑되는 분이 도래해 모든 봇 시뮬 가능.
_MOCK_PATTERNS: tuple[str, ...] = ("scalping_mean_reversion", "scalping_breakout")


def _pick_mock_pattern(ticker: str) -> str:
    """(ticker, 현재 분봉_시각) → mock 시나리오 패턴 결정.

    `int(time.time() // 60)`으로 분 단위 인덱스. 매분 +1 → 패턴 순환.
    같은 분 내에서는 같은 ticker가 같은 패턴 = 디버깅 시 (ticker, 분)으로 reproduce 가능.
    """
    minute_idx = int(_time.time() // 60)
    return _MOCK_PATTERNS[(sum(ord(c) for c in ticker) + minute_idx) % len(_MOCK_PATTERNS)]


def _make_candle(i: int, open_p: float, chg: float, vol: int) -> dict:
    """OHLCV 봉 1개 dict 생성 (high/low는 ±0.2% 위크 추가)."""
    close_p = round(open_p * (1 + chg), 0)
    high_p = round(max(open_p, close_p) * (1 + random.uniform(0, 0.002)), 0)
    low_p = round(min(open_p, close_p) * (1 - random.uniform(0, 0.002)), 0)
    return {
        "t": f"{9 + i // 60:02d}:{i % 60:02d}",
        "o": open_p, "h": high_p, "l": low_p, "c": close_p, "v": vol,
    }


def _mock_scenario_mean_reversion(base_price: float) -> list[dict]:
    """과매도 + 거래량 급증 시나리오 (bot_21 류 scalping_mean_reversion).
      i=0~89:    횡보 ±0.3%, vol 800~2500
      i=90~197:  하락 편향 (-0.4%~+0.05%), vol 100~400 (20봉 평균 낮아짐)
      i=198~199: 50% 확률 vol 폭발 5000~10000
    목표 지표: RSI<35, volume_ratio>1.3, price_vs_vwap<-0.5
    """
    peak_price = round(base_price * random.uniform(1.08, 1.15), 0)
    candles: list[dict] = []
    price = peak_price
    spike = random.random() < 0.5
    for i in range(MAX_CANDLES):
        if i < 90:
            chg = random.uniform(-0.003, 0.003)
            vol = random.randint(800, 2500)
        elif i < 198:
            chg = random.uniform(-0.004, 0.0005)
            vol = random.randint(100, 400)
        else:
            chg = random.uniform(-0.003, 0.001)
            vol = random.randint(5000, 10000) if spike else random.randint(100, 400)
        c = _make_candle(i, price, chg, vol)
        candles.append(c)
        price = c["c"]
    candles.reverse()
    return candles


def _mock_scenario_breakout(base_price: float) -> list[dict]:
    """추세 돌파 시나리오 (bot_22 류 scalping_breakout).
      i=0~49:    박스권 ±0.3%, vol 800~2500
      i=50~140:  완만한 상승 (+0.03%~+0.15%), vol 800~2500 (누적 ~+5~13%)
      i=141~180: 변동 (-0.08%~+0.12%), vol 800~2500 (RSI 70대로 식음)
      i=181~197: 조정 (-0.2%~+0.08%), vol 800~2500 (RSI 50~65로 식음)
      i=198~199: 50% 확률 vol 폭발 5000~10000
    목표 지표: RSI 50~65, volume_ratio>2, price_vs_vwap>0.3, ATR>0.5
    base_price 기준 −10~−14%에서 출발해 누적 상승 → 후반 가격이 VWAP 위.
    """
    start_price = round(base_price * random.uniform(0.86, 0.90), 0)
    candles: list[dict] = []
    price = start_price
    spike = random.random() < 0.5
    for i in range(MAX_CANDLES):
        if i < 50:
            chg = random.uniform(-0.003, 0.003)
            vol = random.randint(800, 2500)
        elif i < 150:
            # 누적 상승 — VWAP 대비 가격 +5~12% 형성
            chg = random.uniform(0.0005, 0.0018)
            vol = random.randint(800, 2500)
        elif i < 165:
            # 약한 조정 — RSI를 70대 이하로 끌어내림
            chg = random.uniform(-0.0012, 0.0006)
            vol = random.randint(800, 2500)
        elif i < 198:
            # 약한 양봉 우세 박스권 — RSI 50~65 영역 안정 유지 (마지막 14봉이 RSI 결정)
            chg = random.uniform(-0.0012, 0.0014)
            vol = random.randint(800, 2500)
        else:
            chg = random.uniform(-0.0005, 0.002)
            vol = random.randint(5000, 10000) if spike else random.randint(800, 2500)
        c = _make_candle(i, price, chg, vol)
        candles.append(c)
        price = c["c"]
    candles.reverse()
    return candles


_MOCK_SCENARIOS = {
    "scalping_mean_reversion": _mock_scenario_mean_reversion,
    "scalping_breakout": _mock_scenario_breakout,
}


def _mock_candles(ticker: str, interval: int, ref_price: float | None = None) -> list[dict]:
    """ticker → 패턴 매핑 후 시나리오별 더미 캔들 생성.

    ref_price: DB 실제 종가 → 없으면 rt:price → 없으면 1000원 기본값.
    매 분 새로 생성(mock 모드 merge 미사용)하므로 확률적으로 신호 발생.
    """
    if ref_price is None:
        rt = _redis_client.get(f"rt:price:{ticker}")
        ref_price = float(rt) if rt else 1_000.0
    pattern = _pick_mock_pattern(ticker)
    return _MOCK_SCENARIOS[pattern](ref_price)


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

        # VWAP (세션 누적: 첫 봉부터 현재까지)
        typical_price = (high + low + close) / 3
        cum_vol = volume.cumsum()
        vwap_series = (typical_price * volume).cumsum() / cum_vol.replace(0, float("nan"))

        # ATR(14) — 분봉 변동성
        atr_series = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

        # MA 크로스 차이값 — golden_cross/dead_cross value=0 으로 MA↔MA 크로스 표현
        # 예: {"indicator": "ma5_minus_ma20", "condition": "golden_cross", "value": 0} → MA5가 MA20 위로 돌파
        ma5_minus_ma10_series = ma5 - ma10
        ma5_minus_ma20_series = ma5 - ma20

        def _last(series):
            return round(float(series.iloc[-1]), 4) if not series.empty else None

        def _prev(series):
            return round(float(series.iloc[-2]), 4) if len(series) >= 2 else None

        last_vwap = _last(vwap_series)
        price_vs_vwap = round((curr_price - last_vwap) / last_vwap * 100, 4) if last_vwap else 0.0

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
            # ── 신규 지표 ──────────────────────────────────────────────
            "vwap": last_vwap,
            "prev_vwap": _prev(vwap_series),
            "price_vs_vwap": price_vs_vwap,          # (close-vwap)/vwap*100, above 0 = 가격>VWAP
            "atr": _last(atr_series),
            "prev_atr": _prev(atr_series),
            "ma5_minus_ma10": _last(ma5_minus_ma10_series),
            "prev_ma5_minus_ma10": _prev(ma5_minus_ma10_series),
            "ma5_minus_ma20": _last(ma5_minus_ma20_series),
            "prev_ma5_minus_ma20": _prev(ma5_minus_ma20_series),
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
