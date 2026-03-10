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
워렌 버핏의 가치투자 철학(안전마진, 경제적 해자, 장기 관점)과
기술적 분석(모멘텀, 추세, 거래량 확인)을 결합하여 매매 전략을 수립합니다.

주어진 시장 데이터를 분석하고, 현재 시장 상황에 최적화된 매매 전략 조건을 생성하세요.

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{
  "strategy_name": "전략명 (15자 이내)",
  "strategy_type": "swing 또는 scalping",
  "analysis": "시장 분석 및 전략 선택 근거 (200자 이내)",
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


def _save_strategy(db, user_id: int, result: dict) -> Strategy:
    """LLM 결과 → Strategy 레코드 생성"""
    conditions = _normalize_conditions(result.get("conditions", []))
    if not conditions:
        raise ValueError("유효한 조건이 없습니다")

    name = f"[AI] {result.get('strategy_name', '자동생성')} ({date.today()})"
    strategy = Strategy(
        user_id=user_id,
        name=name,
        description=result.get("analysis", ""),
        conditions=conditions,
        strategy_type=result.get("strategy_type", "swing"),
        source="ai_generated",
        ai_analysis=result.get("analysis", ""),
        ai_confidence=result.get("confidence", 0),
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    logger.info("[llm_strategy] 전략 저장 완료: id=%d, 조건=%d개", strategy.id, len(conditions))
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

        # 3. 프롬프트 조합
        market_text = _build_market_context_text(ctx)
        indicator_list = "\n".join(f"- {ind}" for ind in AVAILABLE_INDICATORS)

        user_message = f"""{market_text}

=== 기술적 지표 요약 ===
{tech_summary}

=== 사용 가능한 지표 목록 ===
{indicator_list}

위 시장 데이터를 분석하여 현재 시장 상황에 최적화된 매매 전략 조건을 생성해주세요."""

        # 4. Claude API 호출
        result = _call_claude(user_message)
        logger.info("[llm_strategy] Claude 응답: 전략=%s, 신뢰도=%s",
                    result.get("strategy_name"), result.get("confidence"))

        # 5. 전략 저장
        strategy = _save_strategy(db, user_id, result)

        return {
            "status": "ok",
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "conditions": strategy.conditions,
            "analysis": result.get("analysis"),
            "confidence": result.get("confidence"),
            "risk_level": result.get("risk_level"),
            "trading_day": ctx.get("trading_day"),
        }

    except Exception as e:
        logger.error("[llm_strategy] 오류: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
