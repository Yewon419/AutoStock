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
ML_TOP_N = 100  # ML 모델이 Redis에 저장하는 상위 종목 수


logger = logging.getLogger(__name__)

# ── 사용 가능한 지표 목록 (프롬프트용) ───────────────────────────────
AVAILABLE_INDICATORS = [
    "rsi",           # RSI(14) — <30 과매도(눌림목 매수권), 30~50 매수권, 50~65 추세 진입권, >65 과매수(매수 진입 금지)
    "macd",          # MACD 라인
    "macd_signal",   # MACD 시그널
    "macd_histogram",# MACD 히스토그램 (양수=상승 모멘텀, 추세 추종 매수의 핵심 확인 지표)
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_5", "ma_10", "ma_20",   # 이동평균 (price > ma_20 = 상승 추세)
    "stoch_k", "stoch_d",       # 스토캐스틱 — <20 과매도, >70 과매수(매수 진입 금지). 과매수 영역 진입은 추세 막바지 추격
    "adx",           # 추세 강도 (>25=추세장, <20=횡보장). 추세 추종 전략은 adx > 20~25 필요
    "volume_ratio",  # 거래량비율 = 현재/20일평균 (>1.3 평균 이상, >2 급증)
    "opening_gap",   # 시가 대비 등락률(%)
    # 단타 전용
    "vwap",          # VWAP — 가격이 VWAP 위면 강세, 아래면 약세
    "price_vs_vwap", # (현재가 - VWAP) / VWAP * 100 — 양수=강세
    "atr",           # ATR(14) — 변동성
    "ma5_minus_ma20",# MA5 - MA20 (양수=정배열 추세, 골든/데드크로스 감지)
]

AVAILABLE_CONDITIONS = ["above", "below", "between", "golden_cross", "dead_cross"]

SYSTEM_PROMPT = """당신은 한국 주식시장 전문 퀀트 애널리스트입니다.
기술적 분석(모멘텀, 추세, 거래량)과 머신러닝 예측 데이터를 결합하여 매매 전략을 수립합니다.

주어진 시장 데이터와 ML 분석 결과를 종합하여 현재 시장에 최적화된 전략 조건을 생성하세요.

ML 예측 모델 데이터가 제공되는 경우 반드시 다음을 반영하세요:
1. Feature Importance 상위 지표를 조건에 우선 포함 (예측력이 입증된 지표)
2. ML 상위 종목의 공통 기술적 특성에 부합하는 조건 값 설정
3. ML이 선호하는 종목 패턴(RSI 수준, ADX, 볼린저 위치 등)을 조건에 녹여내기

⚠ 매우 중요 — 진입 영역 가드레일 (위반 시 전략 거부됨):
[swing 전략]
- 추세 추종/모멘텀 진입은 "추세 초입~중반"에서 매수합니다. RSI > 65, stoch_k/stoch_d > 70 영역은 과매수 추격이므로 매수 진입 금지.
- 추세 진입은 다음 패턴 중 하나로 표현: ① RSI between 45~60 + macd_histogram above 0  ② ma_5 vs ma_20 golden_cross + adx above 20  ③ price > ma_20 + macd_histogram above 0 + volume_ratio above 1.2
- 역추세/눌림목 진입은 RSI between 30~50 + 거래량/추세 필터 조합으로 표현.
- between 조건의 하한이 65 이상인 RSI, 70 이상인 stoch_k/stoch_d는 절대 사용하지 않습니다.

[scalping 전략]
- 단타는 통상 과매도 반등(RSI < 35) + volume_ratio > 1.3 또는 vwap 회귀 패턴.
- swing과 마찬가지로 RSI > 65 영역 매수 진입은 금지.

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
- 지표명은 반드시 제공된 목록에서만 선택
- 진입 영역 가드레일을 반드시 준수 (위반 시 자동 거부)"""


# ── 타입 정규화 ────────────────────────────────────────────────────

def _normalize_strategy_type(raw) -> str:
    """LLM 출력의 strategy_type을 허용 값(swing|scalping)으로 정규화.

    LLM이 'day_trading', 'intraday' 등 규격 외 별칭을 반환해도
    단타 계열이면 scalping에 매핑. 그 외는 전부 swing.
    """
    if not raw:
        return "swing"
    r = str(raw).lower().strip()
    if r in ("scalping", "day_trading", "day-trading", "daytrade", "intraday", "scalp"):
        return "scalping"
    return "swing"


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

        # 상위 20개 종목 지표 분포 계산
        top20 = list(profiles.values())[:20]
        if not top20:
            return ""

        def _pct(vals: list, p: int) -> float:
            if not vals:
                return 0.0
            s = sorted(vals)
            idx = max(0, min(len(s) - 1, int(len(s) * p / 100)))
            return round(s[idx], 1)

        rsi_vals_ml  = [p["rsi"] for p in top20]
        adx_vals_ml  = [p["adx"] for p in top20]
        boll_vals_ml = [p["boll_pos"] for p in top20]

        avg_rsi    = round(sum(rsi_vals_ml) / len(rsi_vals_ml), 1)
        avg_adx    = round(sum(adx_vals_ml) / len(adx_vals_ml), 1)
        avg_boll   = round(sum(boll_vals_ml) / len(boll_vals_ml), 2)
        avg_ma_ratio = round(sum(p["ma_ratio"] for p in top20) / len(top20), 3)
        macd_pos_pct = round(sum(1 for p in top20 if p["macd_hist_pos"]) / len(top20) * 100)

        rsi_state = "과매도권" if avg_rsi < 35 else "과매수권" if avg_rsi > 65 else "중립"
        adx_state = "추세장" if avg_adx > 25 else "횡보장"
        ma_state  = "상승 추세" if avg_ma_ratio > 1.02 else "하락 추세" if avg_ma_ratio < 0.98 else "횡보"

        # 분포 범위: P25~P75가 전략 조건 범위의 기준
        rsi_p25, rsi_p75   = _pct(rsi_vals_ml, 25), _pct(rsi_vals_ml, 75)
        adx_p25, adx_p75   = _pct(adx_vals_ml, 25), _pct(adx_vals_ml, 75)
        rsi_min, rsi_max   = _pct(rsi_vals_ml, 0),  _pct(rsi_vals_ml, 100)

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
            f"[ML 상위 20개 종목 지표 분포 — 참고용 통계]\n"
            f"- RSI: 평균 {avg_rsi} ({rsi_state}) / 범위 {rsi_min}~{rsi_max} / 중간 50% 구간 {rsi_p25}~{rsi_p75}\n"
            f"- ADX: 평균 {avg_adx} ({adx_state}) / 중간 50% 구간 {adx_p25}~{adx_p75}\n"
            f"- 볼린저밴드 위치(0=하단,1=상단): 평균 {avg_boll}\n"
            f"- MA20/MA50 비율: {avg_ma_ratio} ({ma_state})\n"
            f"- MACD 히스토그램 양수 비율: {macd_pos_pct}%\n\n"
            f"[ML 분포 해석 규칙 — 반드시 준수]\n"
            f"⚠ 위 분포는 *ML 상위 종목의 현재 상태 통계*이지 *매수 진입 트리거 값*이 아닙니다.\n"
            f"⚠ 'ML 상위 종목의 RSI가 {avg_rsi}이니까 RSI {rsi_p25}~{rsi_p75}에서 매수' 같은 추론은 명백한 오류입니다.\n"
            f"   (이는 '강세 종목 = 과매수 = 매수' 인과 혼동으로 고점 추격 매수를 유발합니다)\n"
            f"→ ML 분포는 *유니버스 적합성 검증*에만 사용하세요. 진입 트리거 값은 SYSTEM_PROMPT의 '진입 영역 가드레일'을 따르세요.\n"
            f"→ Feature Importance 상위 지표를 우선 사용하되, 진입 영역은 가드레일에 명시된 추세 초입/눌림목 영역에서만 설정합니다.\n"
            f"→ ADX 조건은 above {adx_p25} 형태(하위 25% 제외)가 적절합니다.\n"
            f"→ 조건은 2~3개를 넘지 마세요.\n"
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

        ml_tickers = list(json.loads(scores_json).keys())[:ML_TOP_N]
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
            "tickers": ml_tickers,
            "total_return_pct": round(s.get("total_return_pct", 0), 2),
            "win_rate": round(s.get("win_rate", 0), 1),
            "num_trades": s.get("num_trades", 0),
            "sharpe_ratio": round(s.get("sharpe_ratio", 0), 2),
            "avg_daily_signals": s.get("avg_daily_signals", 0),
            "signal_ticker_pct": s.get("signal_ticker_pct", 0),
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


# ── 전략 자기검토 (LLM 리뷰어) ─────────────────────────────────────────

REVIEWER_SYSTEM_PROMPT = """당신은 한국 주식 자동매매 전략을 최종 검토하는 시니어 리스크 매니저입니다.
다른 LLM이 생성한 매매 전략을 받아 *실전 배포 가능성*을 냉정하게 평가합니다.

검토 관점 (모두 점검):
1. 진입 영역 정합성: 전략 의도(추세 추종/눌림목/역추세)와 진입 조건의 영역(과매도/중립/과매수)이 일치하는가?
   - swing 추세 추종에서 RSI > 65, stoch > 70 매수 진입은 명백한 결함(고점 추격)
   - 단타 전략에 take_profit > 5% 같은 RR 비대칭은 회전율 저하 결함
2. 조건 간 논리 정합성: 2~4개 AND 조건이 서로 모순되거나 동시 충족 가능성이 0에 가깝지 않은가?
3. 백테스트 결과 신뢰도: num_trades, win_rate, total_return_pct가 일반화 가능한 수준인가?
   - 거래 수가 적으면(< 10) 통계적 신뢰 부족
   - 수익률은 좋은데 거래 수가 1~2건이면 핏 가능성 큼
4. 시장 국면 정합성: 시장 컨텍스트(지수, ML 분포)와 전략 방향이 정합적인가?
5. 리스크 구조: 조건이 한 종목 군에만 편중되지 않았는가? signal_ticker_pct가 적절한가?

검토 결과는 다음 JSON으로만 응답하세요 (다른 텍스트 없이):
{
  "verdict": "pass | warn | reject",
  "score": 0~100 정수 (실전 배포 적합도),
  "issues": ["발견된 결함 1", "결함 2", ...],
  "reasoning": "검토 근거 (200자 이내)"
}

판정 기준:
- reject: 진입 영역 결함, 의도-조건 불일치, 통계적으로 무의미한 백테스트, 명백한 손실 구조
- warn: 경미한 결함이나 리스크가 있으나 배포는 가능 (issues에 명시)
- pass: 결함 없음, 즉시 배포 가능"""


def _review_strategy(result: dict, conditions: list, backtest: dict, strategy_type: str, market_summary: str = "") -> dict:
    """LLM 자기검토 — 생성된 전략을 별도 LLM 호출로 최종 평가.

    룰 기반 `_gate_strategy`로 못 잡는 의미적 결함(의도-조건 불일치,
    조건 간 논리 모순, 백테스트 신뢰도 등)을 LLM 시각으로 한 번 더 검증한다.

    실패해도(API 오류, 파싱 실패) 전체 파이프라인을 막지 않도록 빈 dict 반환 → 룰 게이트만 적용.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("[llm_strategy] ANTHROPIC_API_KEY 없음 — 자기검토 스킵")
        return {}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # 검토 입력: 전략 + 조건 + 백테스트 + 시장 요약
        review_input = (
            f"=== 검토 대상 전략 ===\n"
            f"전략명: {result.get('strategy_name', 'N/A')}\n"
            f"전략 타입: {strategy_type}\n"
            f"의도/분석: {result.get('analysis', 'N/A')}\n"
            f"리스크 레벨: {result.get('risk_level', 'N/A')}\n"
            f"자기 신뢰도: {result.get('confidence', 'N/A')}\n\n"
            f"=== 진입 조건 (AND 결합) ===\n"
            f"{json.dumps(conditions, ensure_ascii=False, indent=2)}\n\n"
            f"=== 자동 백테스트 결과 (최근 180일, ML 상위 종목) ===\n"
            f"{json.dumps(backtest, ensure_ascii=False, indent=2) if backtest else '(백테스트 데이터 없음)'}\n\n"
            f"=== 시장 요약 (생성 시점) ===\n"
            f"{market_summary[:800] if market_summary else '(요약 없음)'}\n\n"
            f"위 전략을 실전 배포 가능성 관점에서 검토하고 JSON으로 응답하세요."
        )

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=REVIEWER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": review_input}],
        )

        raw = message.content[0].text.strip()
        logger.debug("[llm_strategy] 리뷰어 응답: %s", raw[:300])

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        review = json.loads(raw.strip())

        verdict = str(review.get("verdict", "")).lower().strip()
        if verdict not in ("pass", "warn", "reject"):
            logger.warning("[llm_strategy] 리뷰 verdict 비정상: %s — warn으로 처리", verdict)
            review["verdict"] = "warn"

        logger.info(
            "[llm_strategy] 자기검토 결과: verdict=%s, score=%s, issues=%d개",
            review.get("verdict"), review.get("score"), len(review.get("issues", []) or []),
        )
        return review

    except json.JSONDecodeError as e:
        logger.warning("[llm_strategy] 리뷰 JSON 파싱 실패 (스킵): %s", e)
        return {}
    except Exception as e:
        logger.warning("[llm_strategy] 자기검토 호출 실패 (스킵): %s", e)
        return {}


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


def _gate_semantic(conditions: list, strategy_type: str) -> tuple:
    """의미 게이트 — 과매수 영역 매수 등 구조적 결함을 백테스트 이전 단계에서 차단.

    백테스트는 과거 핏일 수 있어 '추세 막바지 추격' 같은 의미적 결함을 잡지 못한다.
    여기서 진입 영역 가드레일(SYSTEM_PROMPT)과 동일한 룰을 코드로 강제한다.
    """
    OVERBOUGHT_RSI_LOWER = 65.0   # RSI 진입 하한이 이 이상이면 과매수 추격
    OVERBOUGHT_STOCH_LOWER = 70.0 # stoch_k/stoch_d 진입 하한이 이 이상이면 과매수 추격

    for c in conditions:
        ind = (c.get("indicator") or "").lower()
        cond = (c.get("condition") or "").lower()
        v1 = c.get("value")
        v2 = c.get("value2")

        def _to_float(x):
            try:
                return float(x) if x is not None else None
            except (TypeError, ValueError):
                return None

        v1f = _to_float(v1)
        v2f = _to_float(v2)

        if ind == "rsi":
            # above N (N >= 65) = 과매수 추격
            if cond == "above" and v1f is not None and v1f >= OVERBOUGHT_RSI_LOWER:
                return False, f"진입 영역 가드레일 위반: rsi above {v1f} — 과매수 추격 매수 금지"
            # between [lo, hi] with lo >= 65 = 과매수 추격
            if cond == "between" and v1f is not None and v1f >= OVERBOUGHT_RSI_LOWER:
                return False, f"진입 영역 가드레일 위반: rsi between {v1f}~{v2f} — 과매수 추격 매수 금지 (하한 {v1f} ≥ {OVERBOUGHT_RSI_LOWER})"

        if ind in ("stoch_k", "stoch_d"):
            if cond == "above" and v1f is not None and v1f >= OVERBOUGHT_STOCH_LOWER:
                return False, f"진입 영역 가드레일 위반: {ind} above {v1f} — 과매수 추격 매수 금지"
            if cond == "between" and v1f is not None and v1f >= OVERBOUGHT_STOCH_LOWER:
                return False, f"진입 영역 가드레일 위반: {ind} between {v1f}~{v2f} — 과매수 추격 매수 금지 (하한 {v1f} ≥ {OVERBOUGHT_STOCH_LOWER})"

    return True, ""


def _gate_strategy(backtest: dict, conditions: list = None, strategy_type: str = "swing") -> tuple:
    """전략 품질 게이팅 → (통과 여부, 거부 사유).

    1) 의미 게이트 (가드레일) — 백테스트 결과와 무관하게 구조적 결함 차단
    2) 백테스트 게이트 — 거래 빈도/승률/수익률 등 통계적 검증
    """
    # 1) 의미 게이트
    if conditions:
        ok, reason = _gate_semantic(conditions, strategy_type)
        if not ok:
            return False, reason

    # 2) 백테스트 게이트
    if not backtest:
        return True, ""  # 백테스트 실패 시 통과 (데이터 부족 상황)

    trades = backtest.get("num_trades", 0)
    ret = backtest.get("total_return_pct", 0)
    win_rate = backtest.get("win_rate", 0)
    avg_daily = backtest.get("avg_daily_signals", None)
    signal_ticker_pct = backtest.get("signal_ticker_pct", None)

    if trades < 3:
        return False, f"거래 횟수 부족 ({trades}회) — 신호 조건이 너무 엄격함"
    if ret < -15:
        return False, f"수익률 미달 ({ret:.1f}%) — 명백한 손실 전략"
    if trades >= 3 and win_rate < 25:
        return False, f"승률 미달 ({win_rate:.1f}%) — 방향성 없음"
    # 신호 빈도 게이팅: 3일에 1번 미만이면 실전에서 거의 거래 없음
    if avg_daily is not None and avg_daily < 0.3:
        return False, f"신호 빈도 부족 (일평균 {avg_daily:.2f}회) — 조건이 너무 좁아 실전 거래가 거의 발생하지 않음"
    # 신호 발생 종목 비율: 전체 종목의 20% 미만이면 편향 심함
    if signal_ticker_pct is not None and signal_ticker_pct < 20:
        return False, f"신호 종목 편중 ({signal_ticker_pct:.0f}%) — 소수 종목에만 신호 발생, 분산 부족"

    return True, ""


def _save_strategy(db, user_id: int, result: dict, backtest: dict = None, review: dict = None) -> Strategy:
    """LLM 결과 → Strategy 레코드 생성. review가 있으면 분석/신뢰도에 반영."""
    conditions = _normalize_conditions(result.get("conditions", []))
    if not conditions:
        raise ValueError("유효한 조건이 없습니다")

    # 샤프비율 기반 신뢰도 (백테스트 있으면 대체, 없으면 Claude 자기평가)
    if backtest and backtest.get("sharpe_ratio") is not None:
        sharpe = backtest.get("sharpe_ratio", 0)
        confidence = min(100, max(0, int(50 + sharpe * 20)))
    else:
        confidence = result.get("confidence", 0)

    # 리뷰 점수가 있으면 confidence와 가중 평균(60% 백테스트 기반 / 40% 리뷰)
    if review and isinstance(review.get("score"), (int, float)):
        review_score = int(review["score"])
        confidence = int(confidence * 0.6 + review_score * 0.4)

    # 분석 텍스트에 리뷰 결과 부착 (warn인 경우 issues 포함)
    base_analysis = result.get("analysis", "")
    if review:
        verdict = review.get("verdict", "")
        issues = review.get("issues") or []
        reasoning = review.get("reasoning", "")
        review_block = f"\n\n[자기검토] verdict={verdict} score={review.get('score')} — {reasoning}"
        if issues:
            review_block += "\n주의 사항: " + " / ".join(str(i) for i in issues)
        analysis_with_review = base_analysis + review_block
    else:
        analysis_with_review = base_analysis

    name = f"[AI] {result.get('strategy_name', '자동생성')} ({date.today()})"
    strategy = Strategy(
        user_id=user_id,
        name=name,
        description=analysis_with_review,
        conditions=conditions,
        strategy_type=_normalize_strategy_type(result.get("strategy_type")),
        source="ai_generated",
        ai_analysis=analysis_with_review,
        ai_confidence=confidence,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    logger.info(
        "[llm_strategy] 전략 저장 완료: id=%d, 조건=%d개, 신뢰도=%d, 리뷰=%s",
        strategy.id, len(conditions), confidence,
        review.get("verdict") if review else "skipped",
    )
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
        norm_strategy_type = _normalize_strategy_type(result.get("strategy_type"))
        backtest = _auto_backtest(db, temp_conditions, norm_strategy_type)

        # 7. 룰 게이팅: 의미 게이트(과매수 영역 매수 등) + 백테스트 기준 미달 시 저장 거부
        passed, gate_reason = _gate_strategy(backtest, conditions=temp_conditions, strategy_type=norm_strategy_type)
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

        # 8. LLM 자기검토 — 룰 게이트가 못 잡는 의미 결함을 별도 LLM 호출로 최종 평가
        review = _review_strategy(
            result=result,
            conditions=temp_conditions,
            backtest=backtest,
            strategy_type=norm_strategy_type,
            market_summary=tech_summary,
        )
        if review.get("verdict") == "reject":
            logger.warning(
                "[llm_strategy] LLM 자기검토 거부: score=%s, issues=%s",
                review.get("score"), review.get("issues"),
            )
            return {
                "status": "review_rejected",
                "review": review,
                "gate_reason": f"LLM 리뷰 거부: {review.get('reasoning', '')}",
                "analysis": result.get("analysis"),
                "conditions": temp_conditions,
                "risk_level": result.get("risk_level"),
                "ml_enhanced": bool(ml_context),
                "backtest": backtest,
            }

        # 9. 전략 저장 (룰 게이트 + LLM 검토 모두 통과)
        strategy = _save_strategy(db, user_id, result, backtest=backtest, review=review)

        return {
            "status": "ok",
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "conditions": strategy.conditions,
            "tickers": backtest.get("tickers", []),
            "analysis": result.get("analysis"),
            "confidence": strategy.ai_confidence,
            "risk_level": result.get("risk_level"),
            "trading_day": ctx.get("trading_day"),
            "ml_enhanced": bool(ml_context),
            "backtest": backtest,
            "review": review,
        }

    except Exception as e:
        logger.error("[llm_strategy] 오류: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
