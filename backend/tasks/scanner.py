"""
전략 스캐너
- 매일 17:00 (데이터 수집 완료 후) 실행
- RUNNING 상태 봇의 전략 조건을 전체 종목에 적용해 tickers 자동 갱신
- 조건 충족 종목이 많으면 거래량 상위 순으로 최대 MAX_TICKERS개만 선택
"""
import logging
from datetime import date

from tasks.celery_app import celery_app
from core.database import SessionLocal
from models.trading import TradingBot
from models.market import TechnicalIndicator, StockPrice
from models.strategy import Strategy
from services.backtest_engine import _all_conditions_met

logger = logging.getLogger(__name__)

MAX_TICKERS = 30  # 봇당 최대 종목 수


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

        # 거래량 맵 (많을수록 우선 선택)
        vol_map = {
            p.ticker: int(p.volume or 0)
            for p in db.query(StockPrice)
            .filter(StockPrice.date == latest_date)
            .all()
        }

        results = []
        for bot in bots:
            strategy = db.query(Strategy).filter(Strategy.id == bot.strategy_id).first()
            if not strategy or not strategy.conditions:
                continue

            matched = [
                ticker
                for ticker, ind in ind_map.items()
                if _all_conditions_met(strategy.conditions, ind, prev_map.get(ticker))
            ]

            # 거래량 많은 순으로 정렬 후 상위 MAX_TICKERS개 선택
            matched.sort(key=lambda t: vol_map.get(t, 0), reverse=True)
            matched = matched[:MAX_TICKERS]

            old_count = len(bot.tickers or [])
            bot.tickers = matched
            logger.info(
                f"[scanner] bot_id={bot.id} ({bot.name}): "
                f"{old_count}개 → {len(matched)}개 | 기준일: {latest_date}"
            )
            results.append({"bot_id": bot.id, "ticker_count": len(matched)})

        db.commit()
        return {"status": "ok", "date": str(latest_date), "bots": results}

    except Exception as e:
        logger.error(f"[scanner] 오류: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
