from broker.base import BaseBroker
from core.config import settings


def get_broker(bot_mode: str | None = None) -> BaseBroker:
    """봇 모드에 따라 브로커 인스턴스 반환

    bot_mode:
      'mock'  → MockBroker (인라인 가상 체결)
      'paper' → KisBroker(is_paper=True)  — KIS 모의투자 URL + VTTCxxxx TR
      'real'  → KisBroker(is_paper=False) — KIS 실계좌 URL + TTTCxxxx TR
      None    → 환경변수 BROKER_MODE 사용

    주의: 전역 settings.KIS_IS_PAPER는 더 이상 브로커 라우팅에 사용하지 않음.
    봇별 mode가 유일한 진실원. (kis_price_stream 등 단일 계정 스트림은 별도 경로.)
    """
    mode = bot_mode or settings.BROKER_MODE
    if mode == "paper":
        from broker.kis_broker import KisBroker
        return KisBroker(is_paper=True)
    if mode == "real":
        from broker.kis_broker import KisBroker
        return KisBroker(is_paper=False)
    from broker.mock_broker import MockBroker
    return MockBroker()
