from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# 체결 상태 상수
FILL_FILLED = 'FILLED'
FILL_PARTIAL = 'PARTIAL'
FILL_PENDING = 'PENDING'
FILL_REJECTED = 'REJECTED'
FILL_CANCELLED = 'CANCELLED'
FILL_UNKNOWN = 'UNKNOWN'


@dataclass
class FillResult:
    """주문 체결 조회 결과. place_* 이후 broker.check_order_fill(ODNO)로 확인한 실체결 상태."""
    status: str           # FILL_* 상수
    filled_quantity: int  # 실제 체결 수량
    avg_price: float      # 가중평균 체결가 (체결 수량 0이면 0)


@dataclass
class OrderResult:
    """주문 접수 결과. 체결은 별도 FillResult로 확인.

    filled_price는 하위호환 필드로, KIS 모드에선 '접수 시 호가'(참고값)가 들어감.
    실체결가는 immediate_fill.avg_price 또는 check_order_fill 결과를 사용.
    """
    filled_price: float
    order_number: Optional[str] = None
    success: bool = True
    # mock처럼 즉시 체결되는 브로커만 세팅. KIS는 None → 폴링 필요.
    immediate_fill: Optional[FillResult] = None


class BaseBroker(ABC):
    """브로커 추상 인터페이스 - mock/KIS 공통"""

    @abstractmethod
    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """매수 주문 접수. price=0 이면 시장가."""
        pass

    @abstractmethod
    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """매도 주문 접수. price=0 이면 시장가."""
        pass

    def check_order_fill(self, order_number: str, ticker: str) -> FillResult:
        """ODNO로 체결 상태 조회. 구현체가 override."""
        raise NotImplementedError

    def connect(self) -> bool:
        return True
