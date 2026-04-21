"""
Mock 브로커: 실제 주문 없이 전달받은 현재가로 즉시 체결 확인.
KIS와의 인터페이스 대칭을 위해 immediate_fill을 세팅한다.
"""
from broker.base import BaseBroker, OrderResult, FillResult, FILL_FILLED, FILL_UNKNOWN


class MockBroker(BaseBroker):
    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return OrderResult(
            filled_price=price,
            order_number=None,
            success=True,
            immediate_fill=FillResult(status=FILL_FILLED, filled_quantity=quantity, avg_price=price),
        )

    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return OrderResult(
            filled_price=price,
            order_number=None,
            success=True,
            immediate_fill=FillResult(status=FILL_FILLED, filled_quantity=quantity, avg_price=price),
        )

    def check_order_fill(self, order_number: str, ticker: str) -> FillResult:
        # Mock은 immediate_fill로 이미 완결되어 호출될 일이 없지만, 안전망으로 UNKNOWN 반환.
        return FillResult(status=FILL_UNKNOWN, filled_quantity=0, avg_price=0.0)
