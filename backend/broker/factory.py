from broker.base import BaseBroker
from core.config import settings


def get_broker(bot_mode: str = None) -> BaseBroker:
    """봇 모드 또는 BROKER_MODE 환경변수에 따라 브로커 인스턴스 반환

    bot_mode:
      'mock'  → MockBroker (인라인 가상 체결)
      'paper' → KiwoomBroker (키움 모의투자 계좌)
      'real'  → KiwoomBroker (키움 실계좌)
      None    → 환경변수 BROKER_MODE 사용
    """
    mode = bot_mode or settings.BROKER_MODE
    if mode in ("paper", "real"):
        from broker.kiwoom_broker import KiwoomBroker
        return KiwoomBroker()
    else:
        from broker.mock_broker import MockBroker
        return MockBroker()
