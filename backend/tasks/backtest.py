import logging
from tasks.celery_app import celery_app
from core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.backtest.run_backtest_task", bind=True, max_retries=0)
def run_backtest_task(
    self,
    strategy_id: int,
    conditions: list,
    tickers: list,
    start_date: str,
    end_date: str,
    initial_capital: float,
    stop_loss_pct,
    take_profit_pct,
    transaction_cost: float,
):
    db = SessionLocal()
    try:
        from services.backtest_engine import run_backtest
        logger.info(f"[backtest] strategy_id={strategy_id}, tickers={len(tickers)}, {start_date}~{end_date}")
        result = run_backtest(
            db=db,
            conditions=conditions,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            transaction_cost=transaction_cost,
        )
        grade = result['summary']['grade']
        score = result['summary']['total_score']
        logger.info(f"[backtest] strategy_id={strategy_id} 완료: {grade}({score}점)")
        return result
    except Exception as exc:
        logger.error(f"[backtest] strategy_id={strategy_id} 오류: {exc}", exc_info=True)
        raise
    finally:
        db.close()
