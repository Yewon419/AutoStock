"""
단타봇 최적 전략 세팅 스크립트

실행: python setup_scalping.py

수행 내용:
  1. DB의 모든 scalping 봇 조회
  2. 봇 소유 유저에게 "과매도 반등 + 거래량" 전략 생성 (이미 있으면 재사용)
  3. 봇 설정을 최적값으로 업데이트 (전략 연결 + 리스크/트레일링 설정)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.database import SessionLocal
from models.trading import TradingBot
from models.strategy import Strategy

# ── 최적 전략 조건 ──────────────────────────────────────────────────────
# mock 패턴: 가격 하락 후 RSI < 35 + 50% 확률 거래량 급증(ratio ≈ 30)
# Real 패턴: 과매도 반등 + 거래량 확인은 보편적인 단타 진입 조건
STRATEGY_NAME = "과매도 반등 + 거래량 (단타 최적)"
STRATEGY_DESC = "RSI 35 이하 과매도 구간 + 거래량 2배 급증 시 진입. 트레일링 스탑으로 수익 극대화."
STRATEGY_CONDITIONS = [
    {"indicator": "rsi",          "condition": "below", "value": 35,  "value2": None},
    {"indicator": "volume_ratio", "condition": "above", "value": 2.0, "value2": None},
]

# ── 봇 최적 설정 ────────────────────────────────────────────────────────
BOT_SETTINGS = {
    "candle_interval":    1,      # 1분봉 (가장 빠른 반응)
    "stop_loss_pct":      2.0,    # 하드 손절 2%
    "take_profit_pct":    5.0,    # 고정 익절 5% (트레일링 스탑과 병행)
    "trailing_stop_pct":  1.5,    # 트레일링 스탑: 고가 대비 1.5% 하락 시 청산
    "confirm_bars":       1,      # mock 테스트용 즉시 진입 (실전 시 2 권장)
    "max_drawdown_pct":   10.0,
    "position_size_pct":  20.0,   # 자금의 20%씩 진입 (최대 5포지션 = 100%)
    "max_positions":      5,
    "max_daily_trades":   100,
    "intraday_close":     True,
    "max_order_amount":   5_000_000,   # 포지션 크기(20%) 기준 여유있게
    # intraday_close_time은 기존 값 유지 (14:50 default)
}


def main():
    db = SessionLocal()
    try:
        bots = db.query(TradingBot).filter(TradingBot.bot_type == "scalping").all()

        if not bots:
            print("❌ scalping 봇이 없습니다. 먼저 봇을 생성하세요.")
            return

        print(f"✅ 단타봇 {len(bots)}개 발견\n")

        # 유저별 전략 캐시 (같은 유저에게 전략 중복 생성 방지)
        strategy_cache: dict[int, Strategy] = {}

        for bot in bots:
            user_id = bot.user_id

            # 전략 조회 or 생성
            if user_id not in strategy_cache:
                existing = (
                    db.query(Strategy)
                    .filter(
                        Strategy.user_id == user_id,
                        Strategy.name == STRATEGY_NAME,
                    )
                    .first()
                )

                if existing:
                    # 조건 업데이트
                    existing.conditions = STRATEGY_CONDITIONS
                    existing.description = STRATEGY_DESC
                    existing.strategy_type = "scalping"
                    db.flush()
                    strategy = existing
                    print(f"  [유저 {user_id}] 기존 전략 업데이트: {strategy.name} (id={strategy.id})")
                else:
                    strategy = Strategy(
                        user_id=user_id,
                        name=STRATEGY_NAME,
                        description=STRATEGY_DESC,
                        conditions=STRATEGY_CONDITIONS,
                        strategy_type="scalping",
                    )
                    db.add(strategy)
                    db.flush()
                    print(f"  [유저 {user_id}] 새 전략 생성: {strategy.name} (id={strategy.id})")

                strategy_cache[user_id] = strategy

            strategy = strategy_cache[user_id]

            # 봇 설정 업데이트
            bot.strategy_id = strategy.id
            for k, v in BOT_SETTINGS.items():
                setattr(bot, k, v)

            print(f"  봇 [{bot.id}] '{bot.name}' → 전략 연결 + 설정 완료")
            print(f"    손절 {BOT_SETTINGS['stop_loss_pct']}% / 익절 {BOT_SETTINGS['take_profit_pct']}%"
                  f" / 트레일링 {BOT_SETTINGS['trailing_stop_pct']}%"
                  f" / 확인봉 {BOT_SETTINGS['confirm_bars']}봉")

        db.commit()
        print("\n✅ 모든 단타봇 세팅 완료")
        print("\n[ 전략 조건 ]")
        for c in STRATEGY_CONDITIONS:
            print(f"  · {c['indicator']:20s} {c['condition']:12s} {c['value']}")
        print("\n[ 전략 요약 ]")
        print("  - RSI < 35  : 과매도 구간 (가격 하락 후 반등 대기)")
        print("  - 거래량 2배 : 거래량 급증으로 반등 모멘텀 확인")
        print("  - 손절 2%    : 하드 스탑 (강한 손실 방어)")
        print("  - 익절 5%    : 고정 목표 (단기 수익 확정)")
        print("  - 트레일링 1.5%: 고가 대비 1.5% 하락 시 청산 (수익 극대화)")
        print("  - 1분봉 / 즉시 진입(confirm_bars=1)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
