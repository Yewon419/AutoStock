"""
Mock 브로커: 실제 주문 없이 즉시 현재가로 체결 확인
"""
from broker.base import BaseBroker, OrderResult


class MockBroker(BaseBroker):
    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        # Mock 모드: 전달받은 현재가로 즉시 체결
        return OrderResult(filled_price=price, order_number=None, success=True)

    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return OrderResult(filled_price=price, order_number=None, success=True)
