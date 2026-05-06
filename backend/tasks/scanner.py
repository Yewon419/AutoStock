"""
전략 스캐너
- 매일 17:00 (데이터 수집 완료 후) 실행
- RUNNING 상태 봇의 전략 조건을 전체 종목에 적용해 tickers 자동 갱신
- 조건 충족 종목이 많으면 거래량 상위 순으로 최대 MAX_TICKERS개만 선택

스윙 봇: 일봉 DB 지표로 전체 조건 평가
단타 봇: 일봉 DB로 평가 가능한 조건만 선(先)스크리닝 → 거래량 상위 필터
         (volume_ratio, opening_gap 등 인트라데이 전용 조건은 실행 엔진에서 실시간 최종 판단)
"""
import logging

import redis as _redis_sync

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.trading import TradingBot
from models.market import TechnicalIndicator, StockPrice
from models.strategy import Strategy
from services.backtest_engine import _all_conditions_met, SUPPORTED_INDICATORS, build_vol_ctx

logger = logging.getLogger(__name__)

MAX_TICKERS = 30  # 봇당 최대 종목 수
# stream 자동 동기화 신호 — universe 갱신 후 SET하면 stream task가 다음 30s 안에 정상 종료,
# watchdog이 다음 분 stale 감지하고 새 universe로 재기동.
_STREAM_UNIVERSE_DIRTY_KEY = "autostock:price_stream:universe_dirty"
_STREAM_DIRTY_TTL = 86400

# 일봉 DB에 없는 인트라데이 전용 지표 — 단타 스캐너에서 건너뜀
_INTRADAY_ONLY = {'volume_ratio', 'opening_gap', 'bb_upper', 'bb_middle', 'bb_lower',
                  'ma_5', 'ma_10', 'macd_histogram'}


def _daily_conditions(conditions: list) -> list:
    """단타 전략 조건 중 일봉 DB(TechnicalIndicator)로 평가 가능한 것만 반환"""
    return [c for c in conditions
            if c.get('indicator', '').lower() in SUPPORTED_INDICATORS
            and c.get('indicator', '').lower() not in _INTRADAY_ONLY]


@celery_app.task(name="tasks.scanner.scan_bot_tickers")
def scan_bot_tickers():
    """
    전략 조건을 전체 종목에 적용해 RUNNING 봇의 tickers를 매일 자동 갱신.
    """
    db = SessionLocal()
    try:
        # 최신 지표 날짜
        latest = (
            db.query(TechnicalIndicator.date)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        if not latest:
            logger.warning("[scanner] 지표 데이터 없음")
            return {"status": "no_data"}
        latest_date = latest[0]

        # 이전 거래일 (골든크로스/데드크로스 조건용)
        prev = (
            db.query(TechnicalIndicator.date)
            .filter(TechnicalIndicator.date < latest_date)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        prev_date = prev[0] if prev else None

        # 전략이 있는 RUNNING 봇만 조회
        bots = (
            db.query(TradingBot)
            .filter(TradingBot.status == "RUNNING", TradingBot.strategy_id.isnot(None))
            .all()
        )
        if not bots:
            logger.info("[scanner] 실행 중인 봇 없음")
            return {"status": "no_bots"}

        # 전체 종목 최신 지표 한 번만 로드
        ind_map = {
            i.ticker: i
            for i in db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.date == latest_date)
            .all()
        }
        prev_map = {}
        if prev_date:
            prev_map = {
                i.ticker: i
                for i in db.query(TechnicalIndicator)
                .filter(TechnicalIndicator.date == prev_date)
                .all()
            }

        # 가격 row 맵 (latest_date 기준) — vol_map + volume_ratio 평가의 price_row 둘 다 사용
        price_rows = (
            db.query(StockPrice).filter(StockPrice.date == latest_date).all()
        )
        price_row_map = {p.ticker: p for p in price_rows}
        vol_map = {ticker: int(p.volume or 0) for ticker, p in price_row_map.items()}

        # 인트라데이 indicator(volume_ratio) 평가용 vol_ctx — 전체 종목 한 번 계산
        vol_ctx = build_vol_ctx(db, list(price_row_map.keys()), latest_date)

        results = []
        for bot in bots:
            strategy = db.query(Strategy).filter(Strategy.id == bot.strategy_id).first()
            if not strategy or not strategy.conditions:
                continue

            is_scalping = getattr(bot, 'bot_type', 'swing') == 'scalping'

            if is_scalping:
                # 단타 봇: 일봉으로 평가 가능한 조건만 선스크리닝
                daily_conds = _daily_conditions(strategy.conditions)
                if daily_conds:
                    # 일봉 조건이 하나라도 있으면 적용
                    matched = [
                        ticker
                        for ticker, ind in ind_map.items()
                        if _all_conditions_met(daily_conds, ind, prev_map.get(ticker))
                    ]
                else:
                    # 전략 조건이 전부 인트라데이 전용인 경우 → 전 종목 거래량 필터만 적용
                    matched = list(ind_map.keys())
                    logger.info(
                        f"[scanner] bot_id={bot.id} 단타 봇 — 일봉 조건 없음, 거래량 상위 {MAX_TICKERS}개 선택"
                    )
            else:
                # 스윙 봇: 전체 조건 일봉 평가 (volume_ratio 등 동적 지표는 vol_ctx + price_row로 평가)
                matched = [
                    ticker
                    for ticker, ind in ind_map.items()
                    if _all_conditions_met(
                        strategy.conditions, ind, prev_map.get(ticker),
                        vol_ctx=vol_ctx, price_row=price_row_map.get(ticker),
                    )
                ]

            # 공통: 거래량 많은 순 정렬 후 상위 MAX_TICKERS개
            matched.sort(key=lambda t: vol_map.get(t, 0), reverse=True)
            matched = matched[:MAX_TICKERS]

            old_count = len(bot.tickers or [])
            bot.tickers = matched
            mode_label = "단타" if is_scalping else "스윙"
            logger.info(
                f"[scanner] bot_id={bot.id} ({bot.name}) [{mode_label}]: "
                f"{old_count}개 → {len(matched)}개 | 기준일: {latest_date}"
            )
            results.append({"bot_id": bot.id, "bot_type": mode_label, "ticker_count": len(matched)})

        db.commit()

        # universe가 실제로 바뀐 봇이 있으면 stream 재기동 신호 push.
        # stream task가 dirty 키를 polling으로 감지해 정상 종료 → watchdog이 새 universe로 재기동.
        if any(r["ticker_count"] > 0 for r in results):
            try:
                redis_client = _redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
                redis_client.set(_STREAM_UNIVERSE_DIRTY_KEY, "1", ex=_STREAM_DIRTY_TTL)
                logger.info("[scanner] universe 갱신 — stream 재기동 신호 push (dirty 키 SET)")
            except Exception as e:
                logger.warning("[scanner] dirty 키 SET 실패: %r", e)

        return {"status": "ok", "date": str(latest_date), "bots": results}

    except Exception as e:
        logger.error(f"[scanner] 오류: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
