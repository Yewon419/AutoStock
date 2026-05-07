"""전략 신호 발생률 시뮬레이터 — AI 팔레트 사전 게이트.

LLM이 생성한 strategy.conditions가 mock 환경에서 실제로 신호를 발생시킬 수 있는지
사전 측정. 패턴-조건 미스매치로 신호 0건이 강제되는 결함을 백테스트/리뷰 이전
단계에서 차단한다 (5/7 incident: bot_22 scalping_breakout 전략이 mock의 단일
mean_reversion 시나리오 하에서 RSI·VWAP 0% 충족 → 48h 누적 0 trades).

대상은 scalping 전용. swing 전략은 일봉 backtest_engine으로 검증된다.
scalping pattern이 _MOCK_SCENARIOS에 등록된 경우에만 시뮬 가능 — 미등록 패턴은
시뮬 skip (-1.0 반환)하여 후방 호환을 유지한다.
"""
from __future__ import annotations

from tasks.intraday_collector import _MOCK_SCENARIOS, _calc_indicators
from tasks.scalping_engine import _all_scalping_conditions_met

_DEFAULT_TRIALS = 500
_SIM_BASE_PRICE = 10_000.0
_SIM_TICKER = "SIM"


def simulate_signal_rate(
    conditions: list[dict],
    pattern: str,
    n_trials: int = _DEFAULT_TRIALS,
) -> float:
    """N회 mock 시뮬 → strategy.conditions 4중 통과율(0.0~1.0).

    pattern이 mock 시나리오 매트릭스에 없으면 -1.0 반환 (시뮬 미지원).
    호출자는 -1.0을 'skip' 신호로 처리.
    """
    scenario = _MOCK_SCENARIOS.get(pattern)
    if scenario is None:
        return -1.0

    passes = 0
    for _ in range(n_trials):
        candles = scenario(_SIM_BASE_PRICE)
        indicators = _calc_indicators(candles, _SIM_TICKER)
        if not indicators:
            continue
        if _all_scalping_conditions_met(conditions, indicators):
            passes += 1
    return passes / n_trials
