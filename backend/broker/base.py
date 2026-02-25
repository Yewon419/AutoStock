from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResult:
    filled_price: float
    order_number: Optional[str] = None
    success: bool = True


class BaseBroker(ABC):
    """브로커 추상 인터페이스 - mock/kiwoom 공통"""

    @abstractmethod
    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """매수 주문. price=0 이면 시장가."""
        pass

    @abstractmethod
    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        """매도 주문. price=0 이면 시장가."""
        pass

    def connect(self) -> bool:
        """브릿지 연결 (real 모드에서만 의미 있음)"""
        return True
