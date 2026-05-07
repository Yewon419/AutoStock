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
  "risk_level": "low | medium | high",
  "risk_params": {
    "stop_loss_pct": 1.5~8.0 (전략 변동성에 맞춰 결정),
    "take_profit_pct": 3.0~15.0 (손익비 ≥ 1.5 권장),
    "max_drawdown_pct": 5.0~15.0 (포트폴리오 분산 고려),
    "position_size_pct": 5.0~25.0 (전략당 종목 비중),
    "max_positions": 1~6 (집중도와 회전율 조절),
    "max_daily_trades": 5~50 (단타는 높게, 스윙은 낮게),
    "trailing_stop_pct": null 또는 0.8~3.0,
    "intraday_close": true (scalping) | false (swing),
    "candle_interval": 1|3|5 (분봉, scalping용)
  }
}

조건 생성 규칙:
- conditions는 2~4개 (AND 조건, 모두 충족 시 매수 신호)
- between 조건은 value(하한) < value2(상한) 형식
- golden_cross/dead_cross는 value=0 (기준선 돌파 감지)
- 지표명은 반드시 제공된 목록에서만 선택 (임의 작명·오타 시 자동 거부)
- swing 전략은 일봉 엔진이 평가 가능한 지표만 사용 (vwap, price_vs_vwap 등 분봉 전용 제외)
- scalping 전략은 분봉 엔진이 평가 가능한 지표만 사용 (stoch_k/stoch_d, ma_50, ma_200, adx, obv 제외)
- 진입 영역 가드레일을 반드시 준수 (위반 시 자동 거부)

risk_params 결정 원칙:
- 변동성 큰 전략(돌파/단타)은 stop_loss 작게(1.5~3%), take_profit 적당(3~6%), max_positions 작게(1~3)
- 안정적 전략(눌림목/추세)은 stop_loss 보통(3~5%), take_profit 크게(8~12%), max_positions 보통(3~5)
- 손익비(take_profit/stop_loss) ≥ 1.5 필수, 1.5 미만이면 자동 거부
- scalping은 intraday_close=true 필수 (장 마감 전 청산)"""


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


# ── 패턴 정의 (다변화 포트폴리오용 5패턴) ────────────────────────────

PATTERNS: dict[str, dict] = {
    "trend_breakout": {
        "korean": "추세돌파",
        "strategy_type": "swing",
        "directive": (
            "추세돌파(swing) 전략 — 정배열 + 모멘텀 가속 시점 매수.\n"
            "필수 조합: price > ma_20 + macd_histogram above 0 + adx above 20 (또는 volume_ratio above 1.3)\n"
            "RSI 사용 시 between 50~65 권장 (과매수 영역 금지). 종목군은 강세 추세 진행 중인 대형/중형 모멘텀주."
        ),
    },
    "pullback": {
        "korean": "눌림목",
        "strategy_type": "swing",
        "directive": (
            "눌림목(swing) 전략 — 상승 추세 종목의 일시적 조정 후 회복 시점 매수.\n"
            "필수 조합: RSI between 35~50 + macd_histogram above 0 + price > ma_20 (추세 유지 확인)\n"
            "역추세 베팅이 아니라 *추세 유지 + 단기 조정* 종목만 포착."
        ),
    },
    "volatility_squeeze": {
        "korean": "변동성압축",
        "strategy_type": "swing",
        "directive": (
            "변동성압축(swing) 전략 — 볼린저 밴드 폭 축소(BB_squeeze) 후 확장 시점 매수.\n"
            "필수 조합: bollinger_lower~bollinger_upper 폭 축소 + volume_ratio above 1.3 + macd_histogram above 0\n"
            "ML Feature Importance에서 ATR_norm/BB_squeeze가 상위인 환경에서 우위."
        ),
    },
    "scalping_mean_reversion": {
        "korean": "과매도단타",
        "strategy_type": "scalping",
        "directive": (
            "과매도반등(scalping) 전략 — 분봉 RSI 과매도 + VWAP 하방 이탈 후 거래량 반등 매수.\n"
            "필수 조합: RSI < 35 + price_vs_vwap below -0.5 + volume_ratio above 1.3\n"
            "intraday_close=true 필수, candle_interval=1~3분."
        ),
    },
    "scalping_breakout": {
        "korean": "돌파단타",
        "strategy_type": "scalping",
        "directive": (
            "돌파단타(scalping) 전략 — 분봉 VWAP 상향 돌파 + 변동성 확장 + 거래량 급증 매수.\n"
            "필수 조합: price_vs_vwap above 0.3 + atr (변동성 확장) + volume_ratio above 2\n"
            "RSI 50~65 권장 (과매수 65 초과 금지). intraday_close=true 필수, candle_interval=1~3분."
        ),
    },
}


def _normalize_pattern(raw) -> Optional[str]:
    if not raw:
        return None
    r = str(raw).lower().strip()
    if r in PATTERNS:
        return r
    return None


# ── risk_params 검증 ──────────────────────────────────────────────

def _validate_risk_params(rp: dict, strategy_type: str) -> tuple[bool, str, dict]:
    """LLM이 결정한 risk_params를 검증하고 정규화. (ok, reason, normalized) 반환."""
    if not isinstance(rp, dict):
        return False, "risk_params 누락 또는 형식 오류", {}

    def _f(key, lo, hi, default=None):
        v = rp.get(key)
        if v is None:
            return default
        try:
            f = float(v)
        except (TypeError, ValueError):
            return default
        if f < lo or f > hi:
            return None  # 범위 위반 마커
        return f

    sl = _f("stop_loss_pct", 1.0, 10.0)
    tp = _f("take_profit_pct", 2.0, 20.0)
    md = _f("max_drawdown_pct", 3.0, 20.0)
    ps = _f("position_size_pct", 3.0, 30.0)
    mp = rp.get("max_positions")
    mdt = rp.get("max_daily_trades")
    ts = _f("trailing_stop_pct", 0.5, 5.0, default=None)
    ic = bool(rp.get("intraday_close", strategy_type == "scalping"))
    ci = rp.get("candle_interval")

    if sl is None or tp is None or md is None or ps is None:
        return False, "risk_params 값 범위 위반 (stop_loss/take_profit/max_drawdown/position_size 중)", {}

    if sl == 0 or tp / sl < 1.5:
        return False, f"손익비 미달 (TP {tp} / SL {sl} = {tp/sl if sl else 'inf'} < 1.5)", {}

    try:
        mp_int = int(mp) if mp is not None else (3 if strategy_type == "swing" else 2)
        mdt_int = int(mdt) if mdt is not None else (10 if strategy_type == "swing" else 30)
    except (TypeError, ValueError):
        return False, "max_positions/max_daily_trades 형식 오류", {}

    if mp_int < 1 or mp_int > 8:
        return False, f"max_positions 범위 위반 ({mp_int})", {}
    if mdt_int < 1 or mdt_int > 100:
        return False, f"max_daily_trades 범위 위반 ({mdt_int})", {}

    if strategy_type == "scalping" and not ic:
        return False, "scalping 전략은 intraday_close=true 필수", {}

    try:
        ci_int = int(ci) if ci is not None else (5 if strategy_type == "swing" else 3)
    except (TypeError, ValueError):
        ci_int = 5 if strategy_type == "swing" else 3
    if ci_int not in (1, 3, 5):
        ci_int = 3 if strategy_type == "scalping" else 5

    normalized = {
        "stop_loss_pct": round(sl, 2),
        "take_profit_pct": round(tp, 2),
        "max_drawdown_pct": round(md, 2),
        "position_size_pct": round(ps, 2),
        "max_positions": mp_int,
        "max_daily_trades": mdt_int,
        "trailing_stop_pct": round(ts, 2) if ts is not None else None,
        "intraday_close": ic,
        "candle_interval": ci_int,
    }
    return True, "", normalized


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
   - 백테스트 win_rate가 50% 미만이라도 손익비(take_profit/stop_loss) ≥ 1.5면 기대값 양수 가능 →
     win_rate만으로 reject하지 말고 risk_params의 손익비와 함께 판단할 것
   - ⚠ 단, strategy_type='scalping'(분봉 단타)은 현재 시스템에 자동 백테스트가 미구현되어
     백테스트 결과가 비어있는 것이 *정상*이다. scalping에 대해서는 "백테스트 데이터 없음"
     자체를 reject 사유로 삼지 말 것. 의미·논리·시장 정합성으로 평가하라.
   - ⚠ risk_params(stop_loss/take_profit/max_positions 등)는 별도 검증을 이미 통과한 값이다.
     "출구 전략 미정의" 같은 사유로 reject하지 말 것 — 입력에 명시된 risk_params를 신뢰할 것.
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


def _review_strategy(result: dict, conditions: list, backtest: dict, strategy_type: str, market_summary: str = "", risk_params: Optional[dict] = None) -> dict:
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

        # risk_params 텍스트 (LLM이 결정한 SL/TP/MDD 등)
        rp_for_prompt = risk_params if risk_params is not None else result.get("risk_params")
        rp_text = json.dumps(rp_for_prompt, ensure_ascii=False, indent=2) if rp_for_prompt else "(LLM이 risk_params 미제출)"

        # 검토 입력: 전략 + 조건 + risk_params + 백테스트 + 시장 요약
        review_input = (
            f"=== 검토 대상 전략 ===\n"
            f"전략명: {result.get('strategy_name', 'N/A')}\n"
            f"전략 타입: {strategy_type}\n"
            f"의도/분석: {result.get('analysis', 'N/A')}\n"
            f"리스크 레벨: {result.get('risk_level', 'N/A')}\n"
            f"자기 신뢰도: {result.get('confidence', 'N/A')}\n\n"
            f"=== 진입 조건 (AND 결합) ===\n"
            f"{json.dumps(conditions, ensure_ascii=False, indent=2)}\n\n"
            f"=== 리스크 파라미터 (출구 전략 — 별도 검증 통과 완료) ===\n"
            f"{rp_text}\n\n"
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


# swing/scalping 각 엔진이 실제로 평가 가능한 indicator 집합 (단일 진실원).
# 엔진과 불일치 시 LLM이 만든 strategy가 silent False로 매번 매수 0건이 되는 사고 방지.
# (5/6 incident: bot_20 strategy가 volume_ratio 사용했으나 swing 엔진에서 평가 불가했던 사례.
#  Phase A에서 swing 엔진이 vol_ctx를 받도록 보강됐으므로 이제 swing도 인트라데이 동적지표 OK.)
_SWING_VALID_INDICATORS = {
    "rsi", "macd", "macd_signal", "macd_histogram",
    "stoch_k", "stoch_d",
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_5", "ma_10", "ma_20", "ma_50", "ma_200",
    "atr", "adx", "obv",
    "volume_ratio", "opening_gap", "ma5_minus_ma20",
}
_SCALPING_VALID_INDICATORS = {
    "rsi", "macd", "macd_signal", "macd_histogram",
    "bollinger_upper", "bollinger_middle", "bollinger_lower",
    "ma_5", "ma_10", "ma_20",
    "volume_ratio", "opening_gap", "atr",
    "vwap", "price_vs_vwap", "ma5_minus_ma10", "ma5_minus_ma20",
}


def _gate_semantic(conditions: list, strategy_type: str) -> tuple:
    """의미 게이트 — 과매수 영역 매수 등 구조적 결함을 백테스트 이전 단계에서 차단.

    백테스트는 과거 핏일 수 있어 '추세 막바지 추격' 같은 의미적 결함을 잡지 못한다.
    여기서 진입 영역 가드레일(SYSTEM_PROMPT)과 동일한 룰을 코드로 강제한다.

    추가: 엔진이 실제 평가 가능한 indicator만 사용하는지 검증 (swing/scalping 각 화이트리스트).
    엔진 미지원 indicator는 평가 시 silent False가 되어 매수 0건 → 사고 차단.
    """
    OVERBOUGHT_RSI_LOWER = 65.0   # RSI 진입 하한이 이 이상이면 과매수 추격
    OVERBOUGHT_STOCH_LOWER = 70.0 # stoch_k/stoch_d 진입 하한이 이 이상이면 과매수 추격

    valid_set = (
        _SCALPING_VALID_INDICATORS if strategy_type == "scalping"
        else _SWING_VALID_INDICATORS
    )

    for c in conditions:
        ind = (c.get("indicator") or "").lower()
        cond = (c.get("condition") or "").lower()
        v1 = c.get("value")
        v2 = c.get("value2")

        # indicator 화이트리스트 — 엔진 미지원 지표 사용 차단
        if ind and ind not in valid_set:
            return False, (
                f"indicator '{ind}'은(는) {strategy_type} 엔진이 평가 불가. "
                f"허용 목록 외 지표는 매번 silent False가 되어 매수 0건 사고 발생. "
                f"허용된 indicator만 사용하세요."
            )

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


# 신호 발생률 게이트 임계값. mock 시뮬 N회 중 4중 조건 통과율이 이 값 미만이면
# 패턴-조건 미스매치로 판정하여 거부. 0.5%면 N=500에서 약 2~3건만 발생해도 통과 —
# 패턴 정의와 정합되는 조건은 통상 5~30% 통과율을 보이므로 보수적 컷오프로 충분.
_SIGNAL_RATE_THRESHOLD = 0.005


def _gate_signal_rate(conditions: list, pattern: str | None, strategy_type: str) -> tuple:
    """신호 발생률 게이트 — mock 시뮬로 strategy.conditions가 실제로 신호 가능한지 검증.

    scalping 전용. swing은 _auto_backtest로 통계 검증되므로 skip.
    pattern이 mock 시나리오 매트릭스에 없으면 skip (시뮬 미지원 패턴 후방 호환).
    """
    if strategy_type != "scalping" or not pattern:
        return True, ""
    try:
        from services.strategy_simulator import simulate_signal_rate
    except ImportError as e:
        logger.warning("[llm_strategy] strategy_simulator import 실패 — 신호률 게이트 skip: %s", e)
        return True, ""

    rate = simulate_signal_rate(conditions, pattern, n_trials=500)
    if rate < 0:
        logger.info("[llm_strategy] 신호률 게이트 skip — pattern '%s' mock 시나리오 미등록", pattern)
        return True, ""
    logger.info("[llm_strategy] 신호률 게이트: pattern=%s rate=%.2f%% (threshold=%.2f%%)",
                pattern, rate * 100, _SIGNAL_RATE_THRESHOLD * 100)
    if rate < _SIGNAL_RATE_THRESHOLD:
        return False, (
            f"신호 발생률 미달 (mock 시뮬 N=500: {rate*100:.2f}% < {_SIGNAL_RATE_THRESHOLD*100:.1f}%) — "
            f"strategy.conditions가 '{pattern}' 패턴 mock 환경에서 거의 신호 발생 불가. "
            f"패턴 정의와 정합되는 진입 영역으로 재생성할 것."
        )
    return True, ""


def _gate_strategy(backtest: dict, conditions: list = None, strategy_type: str = "swing",
                   pattern: str | None = None) -> tuple:
    """전략 품질 게이팅 → (통과 여부, 거부 사유).

    1) 의미 게이트 (가드레일) — 백테스트 결과와 무관하게 구조적 결함 차단
    2) 신호 발생률 게이트 (scalping 전용) — mock 시뮬로 패턴-조건 정합성 사전 검증
    3) 백테스트 게이트 — 거래 빈도/승률/수익률 등 통계적 검증
    """
    # 1) 의미 게이트
    if conditions:
        ok, reason = _gate_semantic(conditions, strategy_type)
        if not ok:
            return False, reason

    # 2) 신호 발생률 게이트 (scalping 전용)
    if conditions:
        ok, reason = _gate_signal_rate(conditions, pattern, strategy_type)
        if not ok:
            return False, reason

    # 3) 백테스트 게이트
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


def _save_strategy(
    db, user_id: int, result: dict,
    backtest: dict = None, review: dict = None,
    pattern: Optional[str] = None, risk_params: Optional[dict] = None,
) -> Strategy:
    """LLM 결과 → Strategy 레코드 생성. review가 있으면 분석/신뢰도에 반영.
    pattern/risk_params는 force_pattern 호출 시 설정되어 봇 생성 단계에서 우선 적용된다."""
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
        pattern=pattern,
        risk_params=risk_params,
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

# ── Pattern Reopening Monitor ───────────────────────────────────────
# 거부된 패턴(예: trend_breakout)을 주기적으로 재시도해 시장 적합 시점 자동 포착.

_PENDING_PATTERN_KEY = "autostock:pattern:pending"           # SET — 재시도 대기 패턴
_PATTERN_REJECT_KEY = "autostock:pattern:reject:{pattern}"   # JSON — 마지막 시도 메타데이터
_PATTERN_REJECT_TTL = 30 * 24 * 3600                         # 30일
_PATTERN_REOPENED_ALERT = "PATTERN_REOPENED"
_PATTERN_REOPEN_COOLDOWN_HOURS = 20                          # 같은 패턴 1일 1회 시도 (08:30 cron 다음 09:30 reopen 사이클)


def mark_pattern_rejected(pattern: str, attempts: int, review: dict) -> None:
    """generate_strategy가 패턴을 reject했을 때 호출 — 재시도 큐에 등록."""
    if not pattern:
        return
    try:
        import redis as _redis
        from datetime import datetime as _dt, timezone as _tz
        r = _redis.from_url(settings.REDIS_URL)
        meta = {
            "pattern": pattern,
            "last_attempt": _dt.now(_tz.utc).isoformat(),
            "attempts": attempts,
            "last_review_score": (review or {}).get("score"),
            "last_review_reasoning": (review or {}).get("reasoning", "")[:500],
        }
        r.setex(_PATTERN_REJECT_KEY.format(pattern=pattern), _PATTERN_REJECT_TTL, json.dumps(meta, ensure_ascii=False))
        r.sadd(_PENDING_PATTERN_KEY, pattern)
        logger.info("[llm_strategy] pattern '%s' marked for reopening monitor", pattern)
    except Exception as e:
        logger.warning("[llm_strategy] mark_pattern_rejected 실패: %s", e)


def _push_pattern_alert(alert_type: str, message: str, extra: Optional[dict] = None) -> None:
    try:
        import redis as _redis
        from datetime import datetime as _dt, timezone as _tz
        r = _redis.from_url(settings.REDIS_URL)
        payload = {
            "type": alert_type,
            "message": message,
            "timestamp": _dt.now(_tz.utc).isoformat(),
        }
        if extra:
            payload.update(extra)
        r.lpush("autostock:alerts", json.dumps(payload, ensure_ascii=False))
        r.ltrim("autostock:alerts", 0, 199)
    except Exception as e:
        logger.warning("[llm_strategy] alert push 실패: %s", e)


@celery_app.task(name="tasks.llm_strategy.reopen_pending_patterns")
def reopen_pending_patterns(user_id: int = 1):
    """매일 09:30 KST 실행 — 거부된 패턴이 시장 변화로 통과 가능한지 재시도.

    통과 시: strategy 자동 저장 + PATTERN_REOPENED 알림 (사용자가 봇 추가 결정).
    재거부 시: 메타데이터 갱신, 큐 유지.
    """
    import redis as _redis
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td

    r = _redis.from_url(settings.REDIS_URL)
    pending_raw = r.smembers(_PENDING_PATTERN_KEY)
    pending = sorted({(p.decode() if isinstance(p, bytes) else p) for p in pending_raw})

    if not pending:
        logger.info("[reopen_patterns] 대기 패턴 없음")
        return {"status": "no_pending"}

    summary: list[dict] = []
    for pattern in pending:
        if pattern not in PATTERNS:
            r.srem(_PENDING_PATTERN_KEY, pattern)
            r.delete(_PATTERN_REJECT_KEY.format(pattern=pattern))
            continue

        # 쿨다운 체크: 마지막 시도 시각이 _PATTERN_REOPEN_COOLDOWN_HOURS 내면 skip
        meta_raw = r.get(_PATTERN_REJECT_KEY.format(pattern=pattern))
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                last = _dt.fromisoformat(meta.get("last_attempt"))
                age_h = (_dt.now(_tz.utc) - last).total_seconds() / 3600
                if age_h < _PATTERN_REOPEN_COOLDOWN_HOURS:
                    logger.info("[reopen_patterns] %s skip (cooldown %.1fh<%dh)", pattern, age_h, _PATTERN_REOPEN_COOLDOWN_HOURS)
                    summary.append({"pattern": pattern, "result": "cooldown", "age_h": round(age_h, 1)})
                    continue
            except Exception:
                pass

        logger.info("[reopen_patterns] retrying pattern '%s'", pattern)
        result = generate_strategy(user_id=user_id, force_pattern=pattern)
        st = result.get("status")

        if st == "ok":
            r.srem(_PENDING_PATTERN_KEY, pattern)
            r.delete(_PATTERN_REJECT_KEY.format(pattern=pattern))
            sid = result.get("strategy_id")
            sname = result.get("strategy_name")
            verdict = (result.get("review") or {}).get("verdict", "?")
            score = (result.get("review") or {}).get("score", "?")
            msg = (
                f"[패턴 재오픈] '{pattern}' 패턴이 시장 변화로 통과 (strategy_id={sid}, name={sname}, "
                f"리뷰={verdict}/{score}). 봇 추가 여부 결정 필요."
            )
            _push_pattern_alert(_PATTERN_REOPENED_ALERT, msg, {
                "pattern": pattern, "strategy_id": sid, "strategy_name": sname,
                "review_verdict": verdict, "review_score": score,
            })
            summary.append({"pattern": pattern, "result": "passed", "strategy_id": sid})
        else:
            # 재거부 — 메타데이터 갱신, 큐 유지
            mark_pattern_rejected(pattern, result.get("attempts", 0), result.get("review", {}))
            summary.append({
                "pattern": pattern, "result": "still_rejected",
                "score": (result.get("review") or {}).get("score"),
            })

    return {"status": "ok", "summary": summary}


@celery_app.task(name="tasks.llm_strategy.generate_strategy")
def generate_strategy(
    user_id: int = 1,
    force_strategy_type: Optional[str] = None,
    force_pattern: Optional[str] = None,
):
    """
    시장 컨텍스트 수집 → Claude 분석 → 전략 조건 생성 → DB 저장
    매일 08:30 자동 실행 + 수동 트리거 가능

    Args:
        user_id: 전략 소유자
        force_strategy_type: 'swing' | 'scalping' (선택). 지정 시 LLM이 해당 타입만 생성하도록 강제.
        force_pattern: PATTERNS 키 중 하나 (선택). 5패턴(trend_breakout/pullback/volatility_squeeze/
            scalping_mean_reversion/scalping_breakout)을 강제하여 포트폴리오 다변화에 사용.
            지정 시 strategy_type은 패턴 정의에 따라 자동 결정 (force_strategy_type 무시).
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

        # 4. 프롬프트 조합 (force_strategy_type이 지정되면 타입 강제 지시 추가)
        market_text = _build_market_context_text(ctx)
        indicator_list = "\n".join(f"- {ind}" for ind in AVAILABLE_INDICATORS)

        # force_pattern이 지정되면 strategy_type도 자동 결정 (패턴 정의 우선)
        norm_pattern = _normalize_pattern(force_pattern)
        if norm_pattern:
            pattern_def = PATTERNS[norm_pattern]
            forced_norm = pattern_def["strategy_type"]
            type_directive = (
                f"\n\n⚠ 필수: 이번 호출은 '{pattern_def['korean']}'({norm_pattern}) 패턴 전용입니다.\n"
                f"- 반드시 strategy_type='{forced_norm}'으로 응답하세요.\n"
                f"- 패턴 가이드:\n  {pattern_def['directive']}\n"
                f"- 가드레일은 그대로 적용: RSI > 65, stoch > 70 영역 매수 진입 절대 금지.\n"
            )
        else:
            forced_norm = _normalize_strategy_type(force_strategy_type) if force_strategy_type else None
            if forced_norm == "scalping":
                type_directive = (
                    "\n\n⚠ 필수: 이번 호출은 단타(scalping) 전략 생성 전용입니다.\n"
                    "- 반드시 strategy_type='scalping'으로 응답하세요.\n"
                    "- 분봉 단위 회전 트레이딩에 적합한 진입 조건만 사용 (vwap, price_vs_vwap, atr, volume_ratio, rsi 과매도 반등 등).\n"
                    "- swing 트레이딩 패턴(추세 추종, 일봉 골든크로스 등)은 사용 금지.\n"
                    "- 가드레일은 그대로 적용: RSI > 65, stoch > 70 영역 매수 진입 절대 금지.\n"
                )
            elif forced_norm == "swing":
                type_directive = (
                    "\n\n⚠ 필수: 이번 호출은 스윙(swing) 전략 생성 전용입니다.\n"
                    "- 반드시 strategy_type='swing'으로 응답하세요.\n"
                    "- 일봉 단위 추세 추종 또는 눌림목 매수 패턴 사용.\n"
                )
            else:
                type_directive = ""

        base_message = f"""{market_text}
{ml_context}
=== 기술적 지표 요약 (DB 전체 종목) ===
{tech_summary}

=== 사용 가능한 지표 목록 ===
{indicator_list}
{type_directive}
위 시장 데이터와 ML 분석 결과를 종합하여 현재 시장에 최적화된 매매 전략 조건을 생성해주세요."""

        # 5~8단계: Claude 호출 → 게이트/리뷰. reject 시 issues 피드백 후 1회 재시도.
        from tasks.llm_strategy import _normalize_conditions
        MAX_ATTEMPTS = 2
        attempt = 0
        last_failure: dict = {}
        prev_failure_block = ""

        while attempt < MAX_ATTEMPTS:
            attempt += 1
            user_message = base_message + prev_failure_block

            # 5. Claude API 호출
            result = _call_claude(user_message)
            logger.info(
                "[llm_strategy] Claude 응답 attempt=%d: 전략=%s, 신뢰도=%s",
                attempt, result.get("strategy_name"), result.get("confidence"),
            )

            # 6. 정규화 + 타입 강제 검사
            temp_conditions = _normalize_conditions(result.get("conditions", []))
            norm_strategy_type = _normalize_strategy_type(result.get("strategy_type"))

            if forced_norm and norm_strategy_type != forced_norm:
                logger.warning(
                    "[llm_strategy] attempt=%d force_strategy_type=%s 위반 (LLM=%s)",
                    attempt, forced_norm, norm_strategy_type,
                )
                last_failure = {
                    "stage": "type_mismatch",
                    "reason": f"force_strategy_type={forced_norm}이지만 LLM이 {norm_strategy_type}로 응답",
                    "result": result, "conditions": temp_conditions, "backtest": {},
                }
                prev_failure_block = (
                    f"\n\n[직전 시도 실패 — 재생성 시 반드시 반영]\n"
                    f"- 타입 불일치: 반드시 strategy_type='{forced_norm}'으로 응답할 것.\n"
                )
                continue

            backtest = _auto_backtest(db, temp_conditions, norm_strategy_type)

            # 7. 룰 게이트 (의미 + 신호률 + 백테스트)
            passed, gate_reason = _gate_strategy(
                backtest, conditions=temp_conditions, strategy_type=norm_strategy_type,
                pattern=norm_pattern,
            )
            if not passed:
                logger.warning("[llm_strategy] attempt=%d 룰 게이트 거부: %s", attempt, gate_reason)
                last_failure = {
                    "stage": "rule_gate", "reason": gate_reason,
                    "result": result, "conditions": temp_conditions, "backtest": backtest,
                }
                prev_failure_block = (
                    f"\n\n[직전 시도 실패 — 재생성 시 반드시 반영]\n"
                    f"- 룰 게이트 거부 사유: {gate_reason}\n"
                    f"- 직전 조건: {json.dumps(temp_conditions, ensure_ascii=False)}\n"
                    f"- 같은 영역/패턴을 다시 시도하지 말고, 위 사유를 해소하는 다른 조건 조합을 사용할 것.\n"
                )
                continue

            # 8. LLM 자기검토 (LLM이 응답한 risk_params를 함께 전달 — 출구 전략 false-reject 방지)
            review = _review_strategy(
                result=result,
                conditions=temp_conditions,
                backtest=backtest,
                strategy_type=norm_strategy_type,
                market_summary=tech_summary,
                risk_params=result.get("risk_params"),
            )
            if review.get("verdict") == "reject":
                logger.warning(
                    "[llm_strategy] attempt=%d 리뷰 거부: score=%s, issues=%s",
                    attempt, review.get("score"), review.get("issues"),
                )
                last_failure = {
                    "stage": "review_rejected", "review": review,
                    "result": result, "conditions": temp_conditions, "backtest": backtest,
                }
                issues_list = review.get("issues") or []
                issues_text = "\n".join(f"  · {i}" for i in issues_list)
                prev_failure_block = (
                    f"\n\n[직전 시도 실패 — 재생성 시 반드시 반영]\n"
                    f"- 리뷰 거부 사유: {review.get('reasoning', '')}\n"
                    f"- 발견된 결함:\n{issues_text}\n"
                    f"- 직전 조건: {json.dumps(temp_conditions, ensure_ascii=False)}\n"
                    f"- 위 결함을 모두 해소하는 다른 조건 조합으로 재생성할 것. 같은 패턴 반복 금지.\n"
                )
                continue

            # 8.5. risk_params 검증 (LLM이 결정한 SL/TP/MDD 등)
            rp_ok, rp_reason, normalized_rp = _validate_risk_params(
                result.get("risk_params") or {}, norm_strategy_type,
            )
            if not rp_ok:
                logger.warning("[llm_strategy] attempt=%d risk_params 검증 실패: %s", attempt, rp_reason)
                last_failure = {
                    "stage": "risk_params", "reason": rp_reason,
                    "result": result, "conditions": temp_conditions, "backtest": backtest,
                    "review": review,
                }
                prev_failure_block = (
                    f"\n\n[직전 시도 실패 — 재생성 시 반드시 반영]\n"
                    f"- risk_params 검증 실패: {rp_reason}\n"
                    f"- 직전 risk_params: {json.dumps(result.get('risk_params'), ensure_ascii=False)}\n"
                    f"- 손익비(take_profit/stop_loss) >= 1.5 필수, 모든 값 범위 준수.\n"
                )
                continue

            # 모든 게이트 통과
            break
        else:
            # while-else: break 없이 종료 (= 모든 시도 실패)
            stage = last_failure.get("stage", "unknown")
            logger.warning("[llm_strategy] %d회 시도 모두 실패 (last_stage=%s)", MAX_ATTEMPTS, stage)

            # force_pattern으로 호출됐는데 거부됐으면 reopen 큐에 등록 (시장 변화 시 재시도)
            if norm_pattern:
                mark_pattern_rejected(norm_pattern, attempt, last_failure.get("review") or {})

            return {
                "status": "review_rejected" if stage == "review_rejected" else "gated",
                "gate_reason": last_failure.get("reason") or (
                    f"LLM 리뷰 거부: {(last_failure.get('review') or {}).get('reasoning', '')}"
                ),
                "review": last_failure.get("review", {}),
                "analysis": (last_failure.get("result") or {}).get("analysis"),
                "conditions": last_failure.get("conditions", []),
                "risk_level": (last_failure.get("result") or {}).get("risk_level"),
                "ml_enhanced": bool(ml_context),
                "backtest": last_failure.get("backtest", {}),
                "attempts": attempt,
                "pattern": norm_pattern,
                "reopen_queued": bool(norm_pattern),
            }

        # 9. 전략 저장 (룰 게이트 + 리뷰 + risk_params 모두 통과)
        strategy = _save_strategy(
            db, user_id, result,
            backtest=backtest, review=review,
            pattern=norm_pattern, risk_params=normalized_rp,
        )

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
            "attempts": attempt,
            "pattern": norm_pattern,
            "risk_params": normalized_rp,
        }

    except Exception as e:
        logger.error("[llm_strategy] 오류: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
