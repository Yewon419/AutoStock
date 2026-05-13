"""
AI 태스크
1. train_and_score: RandomForest로 ML 종목 스코어링
2. optimize_strategy: Grid Search로 전략 파라미터 최적화
"""
import json
import logging
import math
from datetime import date, timedelta
from typing import Optional

import numpy as np
import redis
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.market import StockPrice, TechnicalIndicator

logger = logging.getLogger(__name__)

ML_SCORES_KEY = "autostock:ml_scores"
ML_SCORES_META_KEY = "autostock:ml_scores_meta"
ML_TOP_N = 100  # ML 모델이 Redis에 저장하는 상위 종목 수



def _get_redis():
    return redis.from_url(settings.REDIS_URL)


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


@celery_app.task(name="tasks.ai_tasks.train_and_score")
def train_and_score():
    """
    최근 6개월 데이터로 RandomForest 학습 → 최신 날짜 종목별 매수 확률 계산 → Redis 저장
    """
    db = SessionLocal()
    try:
        today = date.today()
        lookback_start = today - timedelta(days=180)

        # 최신 지표 날짜
        latest = (
            db.query(TechnicalIndicator.date)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        if not latest:
            return {"status": "no_data"}
        latest_date = latest[0]

        logger.info(f"[ai] 데이터 로드 중... (기준일: {latest_date})")

        # 가격 데이터 로드
        prices = (
            db.query(StockPrice)
            .filter(StockPrice.date >= lookback_start)
            .order_by(StockPrice.ticker, StockPrice.date)
            .all()
        )
        # 지표 데이터 로드
        inds = (
            db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.date >= lookback_start)
            .order_by(TechnicalIndicator.ticker, TechnicalIndicator.date)
            .all()
        )

        # 가격 맵: {ticker: {date: close_price}}, 거래량 맵: {ticker: {date: volume}}
        price_map: dict = {}
        vol_map_full: dict = {}
        for p in prices:
            price_map.setdefault(p.ticker, {})[p.date] = float(p.close_price)
            vol_map_full.setdefault(p.ticker, {})[p.date] = int(p.volume or 0)

        # 지표 맵: {ticker: {date: indicator_row}}
        ind_map: dict = {}
        for i in inds:
            ind_map.setdefault(i.ticker, {})[i.date] = i

        # 거래량 맵 (최신일 기준, 순위 가중치용)
        vol_map = {
            p.ticker: int(p.volume or 0)
            for p in db.query(StockPrice)
            .filter(StockPrice.date == latest_date)
            .all()
        }

        logger.info(f"[ai] 피처 생성 중... (v2: 변화율 피처 + ATR 정규화 라벨)")

        # ── 피처명 정의 (8개 기존 + 5개 신규 = 13개) ──────────────────
        _FEATURE_NAMES = [
            # 기존 8개 (스냅샷)
            'RSI', 'MACD_hist_norm', 'Stoch_K', 'Stoch_D',
            'ADX', 'MA20_MA50', 'ATR_norm', 'Boll_pos',
            # 신규 5개 (변화율 / 구조)
            'RSI_3d_delta',      # RSI 3일 변화 → 모멘텀 방향
            'MACD_hist_slope',   # MACD 히스토그램 5일 기울기
            'Vol_ratio',         # 거래량 / 20일 평균 거래량
            'Price_vs_MA20',     # (종가 - MA20) / MA20 (%)
            'BB_squeeze',        # (BB상단 - BB하단) / BB중간 → 변동성 수축
        ]

        def _extract_features(ind, ind_map_ticker, ind_date, ind_dates_sorted, ticker_prices, ticker_vols):
            """단일 날짜의 피처 벡터 추출. 실패 시 None 반환."""
            ma_20 = _safe_float(ind.ma_20)
            ma_50 = _safe_float(ind.ma_50)
            close = ticker_prices.get(ind_date)
            if close is None or ma_20 == 0:
                return None

            boll_upper = _safe_float(ind.bollinger_upper)
            boll_middle = _safe_float(ind.bollinger_middle) or ma_20
            boll_lower = _safe_float(ind.bollinger_lower)
            boll_range = boll_upper - boll_lower
            boll_pos = (close - boll_lower) / boll_range if boll_range > 0 else 0.5

            # ── 기존 8개 ──
            rsi_curr = _safe_float(ind.rsi)
            macd_hist_norm = _safe_float(ind.macd_histogram) / ma_20 if ma_20 > 0 else 0
            stoch_k = _safe_float(ind.stoch_k)
            stoch_d = _safe_float(ind.stoch_d)
            adx = _safe_float(ind.adx)
            ma_ratio = (ma_20 / ma_50 - 1) if ma_50 > 0 else 0
            atr_norm = _safe_float(ind.atr) / ma_20 if ma_20 > 0 else 0

            # ── 신규 5개: 변화율 피처 ──
            # RSI 3일 변화
            idx = ind_dates_sorted.index(ind_date)
            rsi_3d_delta = 0.0
            if idx >= 3:
                past_ind = ind_map_ticker.get(ind_dates_sorted[idx - 3])
                if past_ind:
                    rsi_3d_delta = rsi_curr - _safe_float(past_ind.rsi)

            # MACD 히스토그램 5일 기울기
            macd_hist_slope = 0.0
            if idx >= 5:
                past_ind5 = ind_map_ticker.get(ind_dates_sorted[idx - 5])
                if past_ind5:
                    past_macd = _safe_float(past_ind5.macd_histogram) / ma_20 if ma_20 > 0 else 0
                    macd_hist_slope = macd_hist_norm - past_macd

            # 거래량 비율 (그 날 거래량 / 직전 20일 평균)
            vol_ratio = 1.0
            if idx >= 20:
                past_vols = [
                    ticker_vols.get(d, 0)
                    for d in ind_dates_sorted[idx - 20:idx]
                ]
                past_vols = [v for v in past_vols if v > 0]
                if past_vols:
                    avg_vol_20 = sum(past_vols) / len(past_vols)
                    today_vol = ticker_vols.get(ind_date, 0)
                    if avg_vol_20 > 0:
                        vol_ratio = today_vol / avg_vol_20

            # 현재가 vs MA20 (%)
            price_vs_ma20 = (close - ma_20) / ma_20 * 100

            # 볼린저밴드 수축도 (낮을수록 변동성 수축)
            bb_squeeze = boll_range / boll_middle if boll_middle > 0 else 0.1

            return [
                rsi_curr, macd_hist_norm, stoch_k, stoch_d,
                adx, ma_ratio, atr_norm, boll_pos,
                rsi_3d_delta, macd_hist_slope, vol_ratio, price_vs_ma20, bb_squeeze,
            ]

        train_X, train_y = [], []
        predict_tickers = []
        predict_X = []

        for ticker, ticker_inds in ind_map.items():
            ticker_prices_dict = price_map.get(ticker, {})
            ticker_vols_dict = vol_map_full.get(ticker, {})
            price_dates = sorted(ticker_prices_dict.keys())
            ind_dates = sorted(ticker_inds.keys())

            if len(ind_dates) < 21:  # vol_ratio 직전 20일 + 당일
                continue

            for ind_date in ind_dates:
                ind = ticker_inds[ind_date]
                features = _extract_features(
                    ind, ticker_inds, ind_date, ind_dates,
                    ticker_prices_dict, ticker_vols_dict,
                )
                if features is None:
                    continue

                close = ticker_prices_dict.get(ind_date)
                if close is None:
                    continue

                if ind_date == latest_date:
                    predict_tickers.append(ticker)
                    predict_X.append(features)
                elif ind_date < latest_date:
                    # ── 라벨 개선: ATR 정규화 수익률 ──────────────────
                    # 5거래일 후 수익을 ATR로 나눠 리스크 대비 수익 측정
                    future_dates = [d for d in price_dates if d > ind_date]
                    if len(future_dates) < 5:
                        continue
                    future_price = ticker_prices_dict.get(future_dates[4])
                    if future_price is None:
                        continue

                    raw_ret = (future_price - close) / close
                    atr = _safe_float(ind.atr)
                    if atr > 0 and close > 0:
                        # ATR 정규화 수익: 0.5 이상이면 양호한 리스크 대비 수익
                        atr_norm_ret = raw_ret / (atr / close)
                        label = 1 if atr_norm_ret > 0.5 else 0
                    else:
                        # ATR 없으면 기존 방식 fallback (5일 수익 > 1%)
                        label = 1 if raw_ret > 0.01 else 0

                    train_X.append(features)
                    train_y.append(label)

        if len(train_X) < 100 or not predict_X:
            logger.warning(f"[ai] 훈련 데이터 부족: {len(train_X)}개")
            return {"status": "insufficient_data", "train_samples": len(train_X)}

        logger.info(f"[ai] 훈련 시작: {len(train_X)}개 샘플, {len(predict_X)}개 예측, 피처={len(_FEATURE_NAMES)}개")

        X_all = np.array(train_X)
        y_all = np.array(train_y)
        X_pred = np.array(predict_X)

        # ── Walk-forward validation (OOS 정확도 측정) ─────────────────
        # 전체 데이터를 시간순 정렬 후 앞 75% 학습 / 뒤 25% OOS 검증
        oos_accuracy = None
        n_total = len(X_all)
        n_train_wf = int(n_total * 0.75)
        if n_train_wf >= 100 and (n_total - n_train_wf) >= 20:
            try:
                from sklearn.metrics import accuracy_score
                scaler_wf = StandardScaler()
                X_wf_train = scaler_wf.fit_transform(X_all[:n_train_wf])
                X_wf_test  = scaler_wf.transform(X_all[n_train_wf:])
                y_wf_train = y_all[:n_train_wf]
                y_wf_test  = y_all[n_train_wf:]

                clf_wf = RandomForestClassifier(
                    n_estimators=100, max_depth=6,
                    min_samples_leaf=20, random_state=42, n_jobs=-1,
                )
                clf_wf.fit(X_wf_train, y_wf_train)
                oos_preds = clf_wf.predict(X_wf_test)
                oos_accuracy = round(float(accuracy_score(y_wf_test, oos_preds)) * 100, 1)
                logger.info(f"[ai] Walk-forward OOS 정확도: {oos_accuracy}% (랜덤 기준 ~50%)")
            except Exception as e:
                logger.warning(f"[ai] Walk-forward 검증 실패 (무시): {e}")

        # ── 전체 데이터로 최종 모델 학습 ──────────────────────────────
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_all)
        X_pred_scaled  = scaler.transform(X_pred)

        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_leaf=20,
            random_state=42,
            n_jobs=-1,
        )
        clf.fit(X_train_scaled, y_all)

        # 매수 신호 확률 (class=1)
        probas = clf.predict_proba(X_pred_scaled)[:, 1]

        # 점수: 0~100
        scores = {
            ticker: round(float(proba) * 100, 1)
            for ticker, proba in zip(predict_tickers, probas)
        }

        # 상위 ML_TOP_N개 (점수 내림차순, 동점 시 거래량)
        top_tickers = sorted(
            scores.keys(),
            key=lambda t: (scores[t], vol_map.get(t, 0)),
            reverse=True,
        )[:ML_TOP_N]
        top_scores = {t: scores[t] for t in top_tickers}

        r = _get_redis()
        r.set(ML_SCORES_KEY, json.dumps(top_scores), ex=86400 * 2)
        r.set(ML_SCORES_META_KEY, json.dumps({
            "date": str(latest_date),
            "train_samples": len(train_X),
            "positive_rate": round(float(y_all.mean()) * 100, 1),
            "ticker_count": len(top_scores),
            "oos_accuracy": oos_accuracy,
            "feature_count": len(_FEATURE_NAMES),
        }), ex=86400 * 2)

        # ── Feature importance 저장 (LLM 연동용) ──────────────────────
        fi_sorted = sorted(
            zip(_FEATURE_NAMES, clf.feature_importances_),
            key=lambda x: -x[1],
        )
        r.set("autostock:ml_feature_importance", json.dumps([
            {"indicator": name, "importance_pct": round(float(imp) * 100, 1)}
            for name, imp in fi_sorted
        ]), ex=86400 * 2)

        # ── 상위 종목 기술적 프로필 저장 (LLM 연동용) ─────────────────
        profiles = {}
        for ticker in top_tickers:
            ind = ind_map.get(ticker, {}).get(latest_date)
            price = price_map.get(ticker, {}).get(latest_date)
            if not ind or not price:
                continue
            ma20 = _safe_float(ind.ma_20)
            ma50 = _safe_float(ind.ma_50)
            boll_u = _safe_float(ind.bollinger_upper)
            boll_l = _safe_float(ind.bollinger_lower)
            boll_range = boll_u - boll_l
            close = float(price)
            boll_pos = (close - boll_l) / boll_range if boll_range > 0 else 0.5
            profiles[ticker] = {
                "score": top_scores[ticker],
                "rsi": round(_safe_float(ind.rsi), 1),
                "adx": round(_safe_float(ind.adx), 1),
                "macd_hist_pos": bool(_safe_float(ind.macd_histogram) > 0),
                "boll_pos": round(boll_pos, 2),
                "ma_ratio": round(ma20 / ma50, 3) if ma50 > 0 else 1.0,
            }
        r.set("autostock:ml_top_profiles", json.dumps(profiles), ex=86400 * 2)

        oos_log = f", OOS정확도={oos_accuracy}%" if oos_accuracy else ""
        logger.info(f"[ai] 완료: {len(top_scores)}개 종목 스코어링, 피처={len(_FEATURE_NAMES)}개{oos_log}")
        return {
            "status": "ok",
            "date": str(latest_date),
            "train_samples": len(train_X),
            "top_tickers": len(top_scores),
            "tickers": top_tickers,
            "oos_accuracy": oos_accuracy,
            "feature_count": len(_FEATURE_NAMES),
        }

    except Exception as e:
        logger.error(f"[ai] train_and_score 오류: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.ai_tasks.optimize_strategy")
def optimize_strategy(
    strategy_id: int,
    indicator: str,
    condition: str,
    value_min: float,
    value_max: float,
    value_step: float,
    value2_fixed: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    전략 파라미터 Grid Search 최적화
    - 지정한 indicator/condition의 value를 value_min~value_max 범위로 스캔
    - 고거래량 100개 종목 샘플 백테스트
    - 결과: [{value, sharpe, score, win_rate, total_return, num_trades}]
    """
    db = SessionLocal()
    try:
        from models.strategy import Strategy
        from services.backtest_engine import run_backtest

        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"status": "error", "message": "전략을 찾을 수 없습니다"}

        today = date.today()
        if not end_date:
            end_date = str(today)
        if not start_date:
            start_date = str(today - timedelta(days=365))

        # 고거래량 종목 100개 샘플
        latest_price = (
            db.query(StockPrice.date)
            .order_by(StockPrice.date.desc())
            .first()
        )
        if not latest_price:
            return {"status": "error", "message": "가격 데이터 없음"}

        top_stocks = (
            db.query(StockPrice.ticker)
            .filter(StockPrice.date == latest_price[0])
            .order_by(StockPrice.volume.desc())
            .limit(100)
            .all()
        )
        tickers = [t[0] for t in top_stocks]
        if not tickers:
            return {"status": "error", "message": "종목 없음"}

        # 스텝 수 상한: 최대 30단계
        raw_steps = round((value_max - value_min) / value_step) + 1
        if raw_steps > 30:
            value_step = (value_max - value_min) / 29

        base_conditions = list(strategy.conditions) if strategy.conditions else []
        results = []
        value = value_min

        while value <= value_max + 1e-9:
            v = round(value, 4)
            new_conditions = []
            replaced = False

            for cond in base_conditions:
                if cond.get('indicator') == indicator and cond.get('condition') == condition:
                    new_cond = {**cond, 'value': v}
                    if value2_fixed is not None:
                        new_cond['value2'] = value2_fixed
                    new_conditions.append(new_cond)
                    replaced = True
                else:
                    new_conditions.append(cond)

            if not replaced:
                new_cond = {'indicator': indicator, 'condition': condition, 'value': v}
                if value2_fixed is not None:
                    new_cond['value2'] = value2_fixed
                new_conditions.append(new_cond)

            try:
                bt = run_backtest(
                    db=db,
                    conditions=new_conditions,
                    tickers=tickers,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=10_000_000,
                )
                s = bt['summary']
                results.append({
                    'value': v,
                    'sharpe': s.get('sharpe_ratio', 0),
                    'score': s.get('total_score', 0),
                    'win_rate': s.get('win_rate', 0),
                    'total_return': s.get('total_return_pct', 0),
                    'num_trades': s.get('num_trades', 0),
                })
            except Exception as e:
                logger.warning(f"[ai] optimize v={v} 오류: {e}")
                results.append({
                    'value': v, 'sharpe': 0, 'score': 0,
                    'win_rate': 0, 'total_return': 0, 'num_trades': 0,
                })

            value += value_step

        best = max(results, key=lambda r: r['sharpe']) if results else None

        return {
            "status": "ok",
            "strategy_id": strategy_id,
            "indicator": indicator,
            "condition": condition,
            "results": results,
            "best": best,
        }

    except Exception as e:
        logger.error(f"[ai] optimize_strategy 오류: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.ai_tasks.backtest_on_ml_top")
def backtest_on_ml_top(
    strategy_id: int,
    tickers_source: str = "ml_top",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    ML 상위 종목에 대한 전략 백테스트
    - tickers_source: "ml_top" (ML 상위 ML_TOP_N개) | "high_volume" (고거래량 100개)
    """
    db = SessionLocal()
    try:
        from models.strategy import Strategy
        from services.backtest_engine import run_backtest

        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"status": "error", "message": "전략을 찾을 수 없습니다"}

        today = date.today()
        if not end_date:
            end_date = str(today)
        if not start_date:
            start_date = str(today - timedelta(days=365))

        # 종목 선택
        if tickers_source == "ml_top":
            r = _get_redis()
            scores_json = r.get(ML_SCORES_KEY)
            if scores_json:
                scores = json.loads(scores_json)
                tickers = list(scores.keys())[:ML_TOP_N]
            else:
                tickers_source = "high_volume"  # fallback

        if tickers_source != "ml_top" or not tickers:
            latest_price = (
                db.query(StockPrice.date)
                .order_by(StockPrice.date.desc())
                .first()
            )
            if not latest_price:
                return {"status": "error", "message": "가격 데이터 없음"}
            top_stocks = (
                db.query(StockPrice.ticker)
                .filter(StockPrice.date == latest_price[0])
                .order_by(StockPrice.volume.desc())
                .limit(100)
                .all()
            )
            tickers = [t[0] for t in top_stocks]

        if not tickers:
            return {"status": "error", "message": "종목 없음"}

        logger.info(f"[ai] backtest_on_ml_top: strategy={strategy_id}, tickers={len(tickers)}, source={tickers_source}")

        bt = run_backtest(
            db=db,
            conditions=list(strategy.conditions) if strategy.conditions else [],
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=10_000_000,
        )
        s = bt["summary"]
        return {
            "status": "ok",
            "strategy_id": strategy_id,
            "tickers_source": tickers_source,
            "tickers": tickers,
            "tickers_count": len(tickers),
            "start_date": start_date,
            "end_date": end_date,
            "total_return_pct": s.get("total_return_pct", 0),
            "win_rate": s.get("win_rate", 0),
            "num_trades": s.get("num_trades", 0),
            "sharpe_ratio": s.get("sharpe_ratio", 0),
            "max_drawdown": s.get("max_drawdown_pct", 0),
        }

    except Exception as e:
        logger.error(f"[ai] backtest_on_ml_top 오류: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ── 최적화 공통 헬퍼 ──────────────────────────────────────────────────

def _resolve_tickers(db, tickers_source: str) -> list[str]:
    """tickers_source 문자열 → 티커 목록 반환 (ml_top or high_volume fallback)"""
    r = _get_redis()
    if tickers_source == "ml_top":
        scores_json = r.get(ML_SCORES_KEY)
        if scores_json:
            return list(json.loads(scores_json).keys())[:ML_TOP_N]

    # fallback: 거래량 상위 100개
    latest_price = (
        db.query(StockPrice.date)
        .order_by(StockPrice.date.desc())
        .first()
    )
    if not latest_price:
        return []
    rows = (
        db.query(StockPrice.ticker)
        .filter(StockPrice.date == latest_price[0])
        .order_by(StockPrice.volume.desc())
        .limit(100)
        .all()
    )
    return [t[0] for t in rows]


def _auto_range(value: float, n_steps: int = 11) -> list[float]:
    """현재값 ±30% 범위의 n_steps개 후보값 생성"""
    lo = value * 0.70
    hi = value * 1.30
    step = (hi - lo) / max(n_steps - 1, 1)
    return [round(lo + i * step, 2) for i in range(n_steps)]


@celery_app.task(name="tasks.ai_tasks.optimize_and_update_strategy", bind=True, max_retries=0)
def optimize_and_update_strategy(
    self,
    strategy_id: int,
    tickers_source: str = "ml_top",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    전략 파라미터 자동 최적화 + DB 업데이트
    1. 각 조건의 value를 ±30% 범위로 Grid Search (11단계)
    2. 샤프비율이 가장 높은 value로 Strategy.conditions 업데이트
    3. 최적화 전/후 백테스트 비교 반환
    """
    db = SessionLocal()
    try:
        from services.backtest_engine import run_backtest
        from models.strategy import Strategy

        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"status": "error", "message": f"전략 {strategy_id}를 찾을 수 없습니다"}

        today = date.today()
        if not end_date:
            end_date = str(today)
        if not start_date:
            start_date = str(today - timedelta(days=365))

        tickers = _resolve_tickers(db, tickers_source)
        if not tickers:
            return {"status": "error", "message": "종목 없음 — ML 모델을 먼저 실행하거나 tickers_source를 변경하세요"}

        original_conditions: list[dict] = [dict(c) for c in (strategy.conditions or [])]
        if not original_conditions:
            return {"status": "error", "message": "전략 조건이 없습니다"}

        logger.info(
            "[ai] optimize_and_update: strategy=%d, tickers=%d, conditions=%d, period=%s~%s",
            strategy_id, len(tickers), len(original_conditions), start_date, end_date,
        )

        # ── 베이스라인 백테스트 ────────────────────────────────────────
        baseline_bt = run_backtest(
            db=db, conditions=original_conditions, tickers=tickers,
            start_date=start_date, end_date=end_date, initial_capital=10_000_000,
        )
        baseline = baseline_bt["summary"]
        baseline_sharpe = float(baseline.get("sharpe_ratio", 0))

        # ── 조건별 Grid Search ────────────────────────────────────────
        optimized_conditions: list[dict] = [dict(c) for c in original_conditions]
        improvements: list[dict] = []

        for i, cond in enumerate(original_conditions):
            ctype = cond.get("condition", "")
            original_value = cond.get("value")

            # golden_cross / dead_cross 는 value=0 고정 — 최적화 불필요
            if ctype in ("golden_cross", "dead_cross") or original_value is None:
                improvements.append({
                    "indicator": cond.get("indicator"),
                    "condition": ctype,
                    "original": original_value,
                    "optimized": original_value,
                    "improved": False,
                    "skipped": True,
                })
                continue

            candidates = _auto_range(float(original_value))
            best_value: float = float(original_value)
            best_sharpe: float = baseline_sharpe

            for candidate in candidates:
                test_conditions = [dict(c) for c in original_conditions]
                test_conditions[i] = {**dict(cond), "value": candidate}
                try:
                    bt = run_backtest(
                        db=db, conditions=test_conditions, tickers=tickers,
                        start_date=start_date, end_date=end_date, initial_capital=10_000_000,
                    )
                    s = bt["summary"]
                    # 최소 거래 3회 이상이어야 샤프 의미 있음
                    if s.get("num_trades", 0) >= 3 and float(s.get("sharpe_ratio", 0)) > best_sharpe:
                        best_sharpe = float(s["sharpe_ratio"])
                        best_value = candidate
                except Exception as e:
                    logger.debug("[ai] optimize candidate=%.2f 건너뜀: %s", candidate, e)
                    continue

            optimized_conditions[i] = {**dict(cond), "value": best_value}
            improvements.append({
                "indicator": cond.get("indicator"),
                "condition": ctype,
                "original": original_value,
                "optimized": best_value,
                "improved": best_value != float(original_value),
                "skipped": False,
            })

        # ── DB 업데이트 ───────────────────────────────────────────────
        strategy.conditions = optimized_conditions
        db.commit()
        db.refresh(strategy)

        # ── 최종 백테스트 (최적화 후) ─────────────────────────────────
        final_bt = run_backtest(
            db=db, conditions=optimized_conditions, tickers=tickers,
            start_date=start_date, end_date=end_date, initial_capital=10_000_000,
        )
        final = final_bt["summary"]

        logger.info(
            "[ai] optimize_and_update 완료: strategy=%d, sharpe %.2f→%.2f, return %.1f%%→%.1f%%",
            strategy_id,
            baseline_sharpe, float(final.get("sharpe_ratio", 0)),
            float(baseline.get("total_return_pct", 0)), float(final.get("total_return_pct", 0)),
        )

        return {
            "status": "ok",
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "conditions": optimized_conditions,
            "tickers": tickers,
            "improvements": improvements,
            "before": {
                "sharpe_ratio": baseline["sharpe_ratio"],
                "total_return_pct": baseline["total_return_pct"],
                "win_rate": baseline["win_rate"],
                "num_trades": baseline["num_trades"],
            },
            "after": {
                "sharpe_ratio": final["sharpe_ratio"],
                "total_return_pct": final["total_return_pct"],
                "win_rate": final["win_rate"],
                "num_trades": final["num_trades"],
            },
        }

    except Exception as e:
        logger.error("[ai] optimize_and_update_strategy 오류: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
