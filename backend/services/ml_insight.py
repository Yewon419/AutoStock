"""
ML 인사이트 생성: 시장 진단 + 종목별 z-score 기여도 설명
- Redis의 ml_scores / ml_scores_meta / ml_feature_importance /
  ml_top_profiles / ml_feature_stats 5개 키를 읽어 사용자용 인사이트 가공
- 학습 모델 자체는 다시 로드하지 않음 — 학습 시점에 저장한 통계만 사용
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import redis

from core.config import settings

ML_SCORES_KEY = "autostock:ml_scores"
ML_SCORES_META_KEY = "autostock:ml_scores_meta"
ML_FEATURE_IMPORTANCE_KEY = "autostock:ml_feature_importance"
ML_TOP_PROFILES_KEY = "autostock:ml_top_profiles"
ML_FEATURE_STATS_KEY = "autostock:ml_feature_stats"

# 피처별 사람 친화 설명 (UI 그대로 노출 가능)
_FEATURE_LABELS: dict[str, str] = {
    "RSI":              "RSI (과매수/과매도)",
    "MACD_hist_norm":   "MACD 히스토그램",
    "Stoch_K":          "Stochastic %K",
    "Stoch_D":          "Stochastic %D",
    "ADX":              "ADX (추세 강도)",
    "MA20_MA50":        "MA20/MA50 비율",
    "ATR_norm":         "ATR 정규화 변동성",
    "Boll_pos":         "볼린저밴드 위치",
    "RSI_3d_delta":     "RSI 3일 변화",
    "MACD_hist_slope":  "MACD 5일 기울기",
    "Vol_ratio":        "거래량 / 20일 평균",
    "Price_vs_MA20":    "MA20 대비 종가 (%)",
    "BB_squeeze":       "볼린저밴드 수축도",
}


@dataclass
class FeatureContribution:
    name: str
    label: str
    value: float
    z_score: float
    direction: str  # "high" | "low"
    importance_pct: float


@dataclass
class TickerInsight:
    ticker: str
    score: float
    top_drivers: list[FeatureContribution]
    summary: str  # 자연어 한 줄 요약


@dataclass
class MarketInsight:
    has_data: bool
    date: Optional[str]
    oos_accuracy: Optional[float]
    train_samples: int
    positive_rate: float
    ticker_count: int
    feature_importance: list[dict]
    top_drivers_market: list[str]      # 시장 전반 핵심 피처 자연어
    regime_summary: list[str]          # 시장 regime 자연어 진단 라인들
    ticker_insights: list[TickerInsight]


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL)


def _load_redis_json(r: redis.Redis, key: str) -> Optional[object]:
    raw = r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _direction_word(z: float) -> str:
    return "high" if z > 0 else "low"


def _describe_feature(name: str, z: float) -> str:
    """피처명 + z-score 방향 → 자연어 한 조각"""
    label = _FEATURE_LABELS.get(name, name)
    if name == "RSI":
        return f"{label} {'상위' if z > 0 else '과매도'} (z={z:+.1f})"
    if name == "ADX":
        return f"{label} {'강함' if z > 0 else '약함'} (z={z:+.1f})"
    if name == "Vol_ratio":
        return f"거래량 {'폭발' if z > 0 else '위축'} (z={z:+.1f})"
    if name == "BB_squeeze":
        return f"변동성 {'확장' if z > 0 else '수축'} (z={z:+.1f})"
    if name == "ATR_norm":
        return f"{label} {'높음' if z > 0 else '낮음'} (z={z:+.1f})"
    if name == "Boll_pos":
        return f"BB 위치 {'상단' if z > 0 else '하단'} (z={z:+.1f})"
    if name == "Price_vs_MA20":
        return f"MA20 {'상회' if z > 0 else '하회'} (z={z:+.1f})"
    return f"{label} {_direction_word(z)} (z={z:+.1f})"


def _build_ticker_summary(ticker: str, score: float, drivers: list[FeatureContribution]) -> str:
    if not drivers:
        return f"{ticker} 점수 {score:.1f} (드라이버 정보 없음)"
    parts = [_describe_feature(d.name, d.z_score) for d in drivers[:3]]
    return f"{ticker} 점수 {score:.1f} — " + " / ".join(parts)


def _build_ticker_insight(
    ticker: str,
    profile: dict,
    feature_stats: dict,
    importance_map: dict[str, float],
) -> Optional[TickerInsight]:
    features = profile.get("features")
    if not features:
        return None
    score = float(profile.get("score", 0))

    contribs: list[FeatureContribution] = []
    for name, value in features.items():
        stats = feature_stats.get(name)
        if not stats:
            continue
        std = float(stats.get("std", 0))
        mean = float(stats.get("mean", 0))
        z = (float(value) - mean) / std if std > 0 else 0.0
        contribs.append(FeatureContribution(
            name=name,
            label=_FEATURE_LABELS.get(name, name),
            value=float(value),
            z_score=round(z, 2),
            direction=_direction_word(z),
            importance_pct=round(float(importance_map.get(name, 0)), 1),
        ))

    # importance × |z| 결합 점수 = 모델 학습에 핵심 + 이 종목에서 두드러진 피처
    contribs.sort(key=lambda c: -(abs(c.z_score) * c.importance_pct))
    top = contribs[:3]
    return TickerInsight(
        ticker=ticker,
        score=score,
        top_drivers=top,
        summary=_build_ticker_summary(ticker, score, top),
    )


def _build_regime_lines(
    meta: dict,
    importance: list[dict],
    top_profiles: dict,
) -> tuple[list[str], list[str]]:
    """시장 regime 자연어 진단 + 시장 전반 핵심 피처 라인"""
    lines: list[str] = []
    pos_rate = float(meta.get("positive_rate", 0))
    if pos_rate >= 45:
        lines.append(f"매수 신호 강세 — 학습 데이터의 {pos_rate:.1f}%가 양호한 5일 후 수익 (평균 35% 대비 +)")
    elif pos_rate >= 30:
        lines.append(f"매수 신호 보통 — 학습 데이터의 {pos_rate:.1f}%가 양호한 5일 후 수익")
    else:
        lines.append(f"매수 신호 약세 — 학습 데이터의 {pos_rate:.1f}%만 양호 (시장 전반 부진)")

    if top_profiles:
        rsis = [p.get("rsi") for p in top_profiles.values() if p.get("rsi") is not None]
        adxs = [p.get("adx") for p in top_profiles.values() if p.get("adx") is not None]
        if rsis:
            avg_rsi = sum(rsis) / len(rsis)
            if avg_rsi <= 35:
                lines.append(f"Top {len(rsis)}종목 평균 RSI {avg_rsi:.0f} — 과매도 반등 후보군 우세")
            elif avg_rsi >= 65:
                lines.append(f"Top {len(rsis)}종목 평균 RSI {avg_rsi:.0f} — 과매수 종목 우세 (주의)")
            else:
                lines.append(f"Top {len(rsis)}종목 평균 RSI {avg_rsi:.0f} — 중립 구간")
        if adxs:
            avg_adx = sum(adxs) / len(adxs)
            if avg_adx >= 25:
                lines.append(f"평균 ADX {avg_adx:.0f} — 추세 강한 종목이 상위 (모멘텀 시장)")
            else:
                lines.append(f"평균 ADX {avg_adx:.0f} — 추세 약함 (박스권/횡보 시장)")

    drivers: list[str] = []
    for f in importance[:3]:
        name = f.get("indicator", "")
        imp = float(f.get("importance_pct", 0))
        label = _FEATURE_LABELS.get(name, name)
        drivers.append(f"{label} {imp:.1f}%")

    return lines, drivers


def compute_insight(top_n: int = 20) -> MarketInsight:
    """Redis에서 ML 산출물을 읽어 시장+종목 인사이트 생성"""
    r = _get_redis()

    meta_obj = _load_redis_json(r, ML_SCORES_META_KEY)
    if not isinstance(meta_obj, dict):
        return MarketInsight(
            has_data=False, date=None, oos_accuracy=None,
            train_samples=0, positive_rate=0, ticker_count=0,
            feature_importance=[], top_drivers_market=[],
            regime_summary=[], ticker_insights=[],
        )

    scores_obj = _load_redis_json(r, ML_SCORES_KEY) or {}
    importance_obj = _load_redis_json(r, ML_FEATURE_IMPORTANCE_KEY) or []
    profiles_obj = _load_redis_json(r, ML_TOP_PROFILES_KEY) or {}
    stats_obj = _load_redis_json(r, ML_FEATURE_STATS_KEY) or {}

    scores: dict = scores_obj if isinstance(scores_obj, dict) else {}
    importance: list = importance_obj if isinstance(importance_obj, list) else []
    profiles: dict = profiles_obj if isinstance(profiles_obj, dict) else {}
    feature_stats: dict = stats_obj if isinstance(stats_obj, dict) else {}

    importance_map = {
        f.get("indicator", ""): float(f.get("importance_pct", 0))
        for f in importance
    }

    regime_lines, market_drivers = _build_regime_lines(meta_obj, importance, profiles)

    # 점수 내림차순 상위 top_n
    ranked = sorted(
        scores.items(),
        key=lambda kv: -float(kv[1]),
    )[:top_n]

    ticker_insights: list[TickerInsight] = []
    for ticker, _score in ranked:
        profile = profiles.get(ticker)
        if not profile:
            continue
        ti = _build_ticker_insight(ticker, profile, feature_stats, importance_map)
        if ti:
            ticker_insights.append(ti)

    return MarketInsight(
        has_data=True,
        date=str(meta_obj.get("date")) if meta_obj.get("date") else None,
        oos_accuracy=(
            float(meta_obj["oos_accuracy"])
            if meta_obj.get("oos_accuracy") is not None else None
        ),
        train_samples=int(meta_obj.get("train_samples", 0)),
        positive_rate=float(meta_obj.get("positive_rate", 0)),
        ticker_count=int(meta_obj.get("ticker_count", 0)),
        feature_importance=importance,
        top_drivers_market=market_drivers,
        regime_summary=regime_lines,
        ticker_insights=ticker_insights,
    )
