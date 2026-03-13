"""
LLM 기반 전략 생성기
- Claude API를 사용해 시장 컨텍스트 + 기술 지표 요약을 분석
- 전략 조건(JSON) 자동 생성 → strategies 테이블에 저장

실행: 매일 08:30 (celery beat) + 수동(API)
"""
import json
import logging
import math
from datetime import date, timedelta
from typing import Optional

from tasks.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from models.strategy import Strategy
from models.market import TechnicalIndicator, StockPrice

ML_FEATURE_IMPORTANCE_KEY = "autostock:ml_feature_importance"
ML_TOP_PROFILES_KEY = "autostock:ml_top_profiles"
ML_SCORES_KEY = "autostock:ml_scores"

logger = logging.getLogger(__name__)

# ── 사용 가능한 지표 목록 (프롬프트용) ───────────────────────────────
AVAILABLE_INDICATORS = [
    "rsi",           # RSI(14) — 30 이하 과매도, 70 이상 과매수
    "macd",          # MACD 라인
    "macd_signal",   # MACD 시그널
    "macd_histogram",# MACD 히스토그램 (양수=상승 모멘텀)
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_5", "ma_10", "ma_20",   # 이동평균
    "stoch_k", "stoch_d",       # 스토캐스틱
    "adx",           # 추세 강도 (25 이상이면 추세장)
    "volume_ratio",  # 거래량비율 = 현재/20일평균 (2 이상이면 급증)
    "opening_gap",   # 시가 대비 등락률(%)
    # 단타 전용
    "vwap",          # VWAP
    "price_vs_vwap", # (현재가 - VWAP) / VWAP * 100
    "atr",           # ATR(14) — 변동성
    "ma5_minus_ma20",# MA5 - MA20 (골든/데드크로스 감지)
]

AVAILABLE_CONDITIONS = ["above", "below", "between", "golden_cross", "dead_cross"]

SYSTEM_PROMPT = """당신은 한국 주식시장 전문 퀀트 애널리스트입니다.
기술적 분석(모멘텀, 추세, 거래량)과 머신러닝 예측 데이터를 결합하여 매매 전략을 수립합니다.

주어진 시장 데이터와 ML 분석 결과를 종합하여 현재 시장에 최적화된 전략 조건을 생성하세요.

ML 예측 모델 데이터가 제공되는 경우 반드시 다음을 반영하세요:
1. Feature Importance 상위 지표를 조건에 우선 포함 (예측력이 입증된 지표)
2. ML 상위 종목의 공통 기술적 특성에 부합하는 조건 값 설정
3. ML이 선호하는 종목 패턴(RSI 수준, ADX, 볼린저 위치 등)을 조건에 녹여내기

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{
  "strategy_name": "전략명 (15자 이내)",
  "strategy_type": "swing 또는 scalping",
  "analysis": "ML 데이터 반영 근거 및 시장 분석 (200자 이내)",
  "conditions": [
    {"indicator": "지표명", "condition": "조건", "value": 숫자, "value2": null또는숫자}
  ],
  "confidence": 신뢰도(0~100 정수),
  "risk_level": "low | medium | high"
}

조건 생성 규칙:
- conditions는 2~4개 (AND 조건, 모두 충족 시 매수 신호)
- between 조건은 value(하한) < value2(상한) 형식
- golden_cross/dead_cross는 value=0 (기준선 돌파 감지)
- 지표명은 반드시 제공된 목록에서만 선택"""


# ── 기술 지표 요약 빌더 ──────────────────────────────────────────────

def _build_technical_summary(db) -> str:
    """DB 기술 지표에서 시장 전체 현황 요약 (ML 상위 종목 기준)"""
    try:
        # 최신 날짜
        latest = (
            db.query(TechnicalIndicator.date)
            .order_by(TechnicalIndicator.date.desc())
            .first()
        )
        if not latest:
            return "기술 지표 데이터 없음"
        latest_date = latest[0]

        # 최신 날짜 지표 전체 로드
        inds = (
            db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.date == latest_date)
            .limit(200)
            .all()
        )
        if not inds:
            return "기술 지표 없음"

        def sf(v, d=0.0):
            if v is None:
                return d
            try:
                f = float(v)
                return d if math.isnan(f) or math.isinf(f) else f
            except Exception:
                return d

        rsi_vals   = [sf(i.rsi) for i in inds if i.rsi is not None]
        adx_vals   = [sf(i.adx) for i in inds if i.adx is not None]
        macd_hists = [sf(i.macd_histogram) for i in inds if i.macd_histogram is not None]

        # MA20 대비 현재가 확인 (가격 데이터 활용)
        prices = (
            db.query(StockPrice.ticker, StockPrice.close_price)
            .filter(StockPrice.date == latest_date)
            .all()
        )
        price_map = {p.ticker: float(p.close_price) for p in prices}

        above_ma20 = sum(
            1 for i in inds
            if i.ma_20 and price_map.get(i.ticker, 0) > float(i.ma_20)
        )
        total = len(inds)

        avg_rsi  = round(sum(rsi_vals) / len(rsi_vals), 1) if rsi_vals else 0
        avg_adx  = round(sum(adx_vals) / len(adx_vals), 1) if adx_vals else 0
        pos_macd = sum(1 for v in macd_hists if v > 0)

        return (
            f"기준일: {latest_date}\n"
            f"분석 종목 수: {total}개\n"
            f"평균 RSI: {avg_rsi} ({'과매도 근접' if avg_rsi < 40 else '과매수 근접' if avg_rsi > 60 else '중립'})\n"
            f"평균 ADX: {avg_adx} ({'추세장' if avg_adx > 25 else '횡보장'})\n"
            f"MACD 히스토그램 양수 종목: {pos_macd}/{total} ({round(pos_macd/total*100)}%)\n"
            f"MA20 상회 종목: {above_ma20}/{total} ({round(above_ma20/total*100)}%)"
        )
    except Exception as e:
        logger.warning("[llm_strategy] 기술 요약 실패: %s", e)
        return "기술 지표 요약 불가"


def _build_market_context_text(ctx: dict) -> str:
    """수집된 시장 컨텍스트 dict → 프롬프트용 텍스트"""
    lines = []

    indices = ctx.get("indices", {})
    if indices:
        # 국내 지수
        domestic = {k: v for k, v in indices.items() if k in ("KOSPI", "KOSDAQ")}
        if domestic:
            lines.append("=== 국내 지수 ===")
            for name, data in domestic.items():
                sign = "+" if data["change_pct"] >= 0 else ""
                lines.append(f"{name}: {data['close']:,.2f} ({sign}{data['change_pct']}%)")

        # 글로벌
        global_ = {k: v for k, v in indices.items() if k not in ("KOSPI", "KOSDAQ")}
        if global_:
            lines.append("")
            lines.append("=== 글로벌 시장 ===")
            for name, data in global_.items():
                sign = "+" if data["change_pct"] >= 0 else ""
                if name == "VIX":
                    vix = data["close"]
                    mood = "극공포" if vix > 30 else "공포" if vix > 20 else "중립" if vix > 15 else "탐욕"
                    lines.append(f"VIX(공포지수): {vix} ({sign}{data['change_pct']}%) — {mood}")
                elif name == "USDKRW":
                    lines.append(f"달러/원: {data['close']:,.0f}원 ({sign}{data['change_pct']}%)")
                else:
                    lines.append(f"{name}: {data['close']:,.2f} ({sign}{data['change_pct']}%)")

    # 시장 심리
    sentiment = ctx.get("sentiment")
    if sentiment:
        lines.append(f"\n=== 시장 심리 ===\n{sentiment}")

    # 투자자 동향
    inv = ctx.get("investor_trend", {})
    if inv:
        lines.append("\n=== 투자자별 순매수(KOSPI) ===")
        for key, label in [("foreign", "외국인"), ("institution", "기관"), ("retail", "개인")]:
            if key in inv:
                val = inv[key] // 100_000_000
                sign = "+" if val >= 0 else ""
                lines.append(f"{label}: {sign}{val:,}억원")

    # 뉴스
    news = ctx.get("news", [])
    if news:
        lines.append("\n=== 주요 뉴스 헤드라인 ===")
        for i, n in enumerate(news[:8], 1):
            lines.append(f"{i}. {n}")

    return "\n".join(lines)


# ── ML 컨텍스트 로더 ─────────────────────────────────────────────────

def _load_ml_context() -> str:
    """Redis에서 ML feature importance + 상위 종목 프로필을 읽어 LLM 프롬프트용 텍스트 생성"""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL)
        fi_json = r.get(ML_FEATURE_IMPORTANCE_KEY)
        profiles_json = r.get(ML_TOP_PROFILES_KEY)

        if not fi_json or not profiles_json:
            logger.info("[llm_strategy] ML 데이터 없음 (ML 학습 미실행)")
            return ""

        fi = json.loads(fi_json)
        profiles = json.loads(profiles_json)
        if not fi or not profiles:
            return ""

        # Feature importance 텍스트 (상위 6개)
        fi_text = "\n".join(
            f"  {i+1}. {item['indicator']}: {item['importance_pct']}%"
            for i, item in enumerate(fi[:6])
        )

        # 상위 20개 종목 평균 기술적 특성
        top20 = list(profiles.values())[:20]
        if not top20:
            return ""

        avg_rsi = round(sum(p["rsi"] for p in top20) / len(top20), 1)
        avg_adx = round(sum(p["adx"] for p in top20) / len(top20), 1)
        avg_boll = round(sum(p["boll_pos"] for p in top20) / len(top20), 2)
        avg_ma_ratio = round(sum(p["ma_ratio"] for p in top20) / len(top20), 3)
        macd_pos_pct = round(sum(1 for p in top20 if p["macd_hist_pos"]) / len(top20) * 100)

        rsi_state = "과매도권" if avg_rsi < 35 else "과매수권" if avg_rsi > 65 else "중립"
        adx_state = "추세장" if avg_adx > 25 else "횡보장"
        boll_state = "하단 근접(반등 가능)" if avg_boll < 0.3 else "상단 근접(과매수)" if avg_boll > 0.7 else "중간 구간"
        ma_state = "상승 추세" if avg_ma_ratio > 1.02 else "하락 추세" if avg_ma_ratio < 0.98 else "횡보"

        # OOS 정확도 로드
        meta_json = r.get("autostock:ml_scores_meta")
        oos_line = ""
        if meta_json:
            meta = json.loads(meta_json)
            oos_acc = meta.get("oos_accuracy")
            feat_cnt = meta.get("feature_count", 8)
            if oos_acc:
                edge = round(oos_acc - 50, 1)
                oos_line = f"모델 OOS 정확도: {oos_acc}% (랜덤 대비 +{edge}%p, 피처 {feat_cnt}개)\n"

        return (
            f"\n=== ML 예측 모델 분석 (RandomForest) ===\n"
            f"ML 상위 종목: {len(profiles)}개\n"
            f"{oos_line}"
            f"\n[지표 예측력 순위 - Feature Importance]\n{fi_text}\n\n"
            f"[ML 상위 20개 종목 공통 기술적 특성]\n"
            f"- RSI 평균: {avg_rsi} ({rsi_state})\n"
            f"- ADX 평균: {avg_adx} ({adx_state})\n"
            f"- 볼린저밴드 위치: {avg_boll} ({boll_state})\n"
            f"- MA20/MA50 비율: {avg_ma_ratio} ({ma_state})\n"
            f"- MACD 히스토그램 양수 비율: {macd_pos_pct}%\n\n"
            f"→ Feature Importance 상위 지표를 조건에 우선 사용하고,\n"
            f"  상위 종목의 공통 특성(RSI {avg_rsi}, ADX {avg_adx})에 부합하는 조건 값을 설정하세요.\n"
        )
    except Exception as e:
        logger.warning("[llm_strategy] ML 컨텍스트 로드 실패: %s", e)
        return ""


def _auto_backtest(db, conditions: list, strategy_type: str) -> dict:
    """생성된 전략을 ML 상위 종목으로 자동 백테스트 (swing만)"""
    if strategy_type == "scalping":
        return {}  # 분봉 백테스트는 별도 처리 필요
    try:
        import redis as redis_lib
        from services.backtest_engine import run_backtest
        from datetime import date, timedelta

        r = redis_lib.from_url(settings.REDIS_URL)
        scores_json = r.get(ML_SCORES_KEY)
        if not scores_json:
            return {}

        ml_tickers = list(json.loads(scores_json).keys())[:30]
        if not ml_tickers:
            return {}

        start_date = str(date.today() - timedelta(days=180))
        end_date = str(date.today())

        bt = run_backtest(
            db=db,
            conditions=conditions,
            tickers=ml_tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=10_000_000,
        )
        s = bt.get("summary", {})
        result = {
            "tickers_tested": len(ml_tickers),
            "total_return_pct": round(s.get("total_return_pct", 0), 2),
            "win_rate": round(s.get("win_rate", 0), 1),
            "num_trades": s.get("num_trades", 0),
            "sharpe_ratio": round(s.get("sharpe_ratio", 0), 2),
        }
        logger.info(
            "[llm_strategy] 자동 백테스트: 수익률=%.1f%%, 거래수=%d, 승률=%.1f%%",
            result["total_return_pct"], result["num_trades"], result["win_rate"],
        )
        return result
    except Exception as e:
        logger.warning("[llm_strategy] 자동 백테스트 실패 (무시): %s", e)
        return {}


# ── Claude API 호출 ──────────────────────────────────────────────────

def _call_claude(user_message: str) -> Optional[dict]:
    """Claude API 호출 → JSON 파싱된 응답 반환"""
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다")

    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()
    logger.debug("[llm_strategy] Claude 응답: %s", raw[:300])

    # JSON 파싱 (```json ... ``` 감싸진 경우 처리)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── 전략 저장 ────────────────────────────────────────────────────────

# Claude가 간혹 다른 표현을 쓸 때 정규화
_CONDITION_ALIASES = {
    "greater_than": "above", "greater than": "above", "over": "above", "exceeds": "above",
    "less_than": "below", "less than": "below", "under": "below",
    "cross_above": "golden_cross", "cross_below": "dead_cross",
}


def _normalize_conditions(conditions: list) -> list:
    normalized = []
    for c in conditions:
        cond = c.get("condition", "").lower().strip()
        cond = _CONDITION_ALIASES.get(cond, cond)
        ind = c.get("indicator", "").lower().strip()
        if ind not in AVAILABLE_INDICATORS:
            logger.warning("[llm_strategy] 알 수 없는 지표 skip: %s", ind)
            continue
        if cond not in AVAILABLE_CONDITIONS:
            logger.warning("[llm_strategy] 알 수 없는 조건 skip: %s", cond)
            continue
        normalized.append({
            "indicator": ind,
            "condition": cond,
            "value": c.get("value"),
            "value2": c.get("value2"),
        })
    return normalized


def _gate_strategy(backtest: dict) -> tuple:
    """백테스트 결과 기반 전략 품질 게이팅 → (통과 여부, 거부 사유)"""
    if not backtest:
        return True, ""  # 백테스트 실패 시 통과 (데이터 부족 상황)

    trades = backtest.get("num_trades", 0)
    ret = backtest.get("total_return_pct", 0)
    win_rate = backtest.get("win_rate", 0)

    if trades < 3:
        return False, f"거래 횟수 부족 ({trades}회) — 신호 조건이 너무 엄격함"
    if ret < -15:
        return False, f"수익률 미달 ({ret:.1f}%) — 명백한 손실 전략"
    if trades >= 3 and win_rate < 25:
        return False, f"승률 미달 ({win_rate:.1f}%) — 방향성 없음"

    return True, ""


def _save_strategy(db, user_id: int, result: dict, backtest: dict = None) -> Strategy:
    """LLM 결과 → Strategy 레코드 생성"""
    conditions = _normalize_conditions(result.get("conditions", []))
    if not conditions:
        raise ValueError("유효한 조건이 없습니다")

    # 샤프비율 기반 신뢰도 (백테스트 있으면 대체, 없으면 Claude 자기평가)
    if backtest and backtest.get("sharpe_ratio") is not None:
        sharpe = backtest.get("sharpe_ratio", 0)
        confidence = min(100, max(0, int(50 + sharpe * 20)))
    else:
        confidence = result.get("confidence", 0)

    name = f"[AI] {result.get('strategy_name', '자동생성')} ({date.today()})"
    strategy = Strategy(
        user_id=user_id,
        name=name,
        description=result.get("analysis", ""),
        conditions=conditions,
        strategy_type=result.get("strategy_type", "swing"),
        source="ai_generated",
        ai_analysis=result.get("analysis", ""),
        ai_confidence=confidence,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    logger.info("[llm_strategy] 전략 저장 완료: id=%d, 조건=%d개, 신뢰도=%d", strategy.id, len(conditions), confidence)
    return strategy


# ── Celery 태스크 ─────────────────────────────────────────────────────

@celery_app.task(name="tasks.llm_strategy.generate_strategy")
def generate_strategy(user_id: int = 1):
    """
    시장 컨텍스트 수집 → Claude 분석 → 전략 조건 생성 → DB 저장
    매일 08:30 자동 실행 + 수동 트리거 가능
    """
    db = SessionLocal()
    try:
        from tasks.news_crawler import collect_market_context

        logger.info("[llm_strategy] 전략 생성 시작 (user_id=%d)", user_id)

        # 1. 시장 컨텍스트 수집
        ctx = collect_market_context()

        # 2. 기술 지표 요약
        tech_summary = _build_technical_summary(db)

        # 3. ML 컨텍스트 로드 (feature importance + 상위 종목 프로필)
        ml_context = _load_ml_context()
        if ml_context:
            logger.info("[llm_strategy] ML 컨텍스트 로드 완료")
        else:
            logger.info("[llm_strategy] ML 컨텍스트 없음 — 시장 데이터만 사용")

        # 4. 프롬프트 조합
        market_text = _build_market_context_text(ctx)
        indicator_list = "\n".join(f"- {ind}" for ind in AVAILABLE_INDICATORS)

        user_message = f"""{market_text}
{ml_context}
=== 기술적 지표 요약 (DB 전체 종목) ===
{tech_summary}

=== 사용 가능한 지표 목록 ===
{indicator_list}

위 시장 데이터와 ML 분석 결과를 종합하여 현재 시장에 최적화된 매매 전략 조건을 생성해주세요."""

        # 5. Claude API 호출
        result = _call_claude(user_message)
        logger.info("[llm_strategy] Claude 응답: 전략=%s, 신뢰도=%s",
                    result.get("strategy_name"), result.get("confidence"))

        # 6. 임시 조건 정규화 → 자동 백테스트 (저장 전 품질 검증)
        from tasks.llm_strategy import _normalize_conditions
        temp_conditions = _normalize_conditions(result.get("conditions", []))
        backtest = _auto_backtest(db, temp_conditions, result.get("strategy_type", "swing"))

        # 7. 게이팅: 백테스트 기준 미달 시 저장 거부
        passed, gate_reason = _gate_strategy(backtest)
        if not passed:
            logger.warning("[llm_strategy] 전략 게이팅 거부: %s", gate_reason)
            return {
                "status": "gated",
                "gate_reason": gate_reason,
                "analysis": result.get("analysis"),
                "conditions": temp_conditions,
                "risk_level": result.get("risk_level"),
                "ml_enhanced": bool(ml_context),
                "backtest": backtest,
            }

        # 8. 전략 저장 (게이팅 통과한 경우만)
        strategy = _save_strategy(db, user_id, result, backtest=backtest)

        return {
            "status": "ok",
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "conditions": strategy.conditions,
            "analysis": result.get("analysis"),
            "confidence": strategy.ai_confidence,
            "risk_level": result.get("risk_level"),
            "trading_day": ctx.get("trading_day"),
            "ml_enhanced": bool(ml_context),
            "backtest": backtest,
        }

    except Exception as e:
        logger.error("[llm_strategy] 오류: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
