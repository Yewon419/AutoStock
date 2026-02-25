"""
키움 브로커: Redis pub/sub를 통해 kiwoom_bridge 프로세스와 통신
- autostock:commands 채널에 명령 발행
- autostock:events 채널에서 결과 수신 (최대 30초 대기)
"""
import json
import logging
import time
import uuid

import redis

from broker.base import BaseBroker, OrderResult
from core.config import settings

logger = logging.getLogger(__name__)

CMD_CHANNEL = "autostock:commands"
EVT_CHANNEL = "autostock:events"
TIMEOUT_SEC = 30


class KiwoomBroker(BaseBroker):
    def __init__(self):
        self._redis = redis.from_url(settings.REDIS_URL)

    def connect(self) -> bool:
        self._publish({"type": "CONNECT"})
        return True

    def place_buy(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return self._send_order("BUY", bot_id, ticker, quantity, price)

    def place_sell(self, bot_id: int, ticker: str, quantity: int, price: float = 0) -> OrderResult:
        return self._send_order("SELL", bot_id, ticker, quantity, price)

    def _send_order(self, order_type: str, bot_id: int, ticker: str, quantity: int, price: float) -> OrderResult:
        request_id = str(uuid.uuid4())
        cmd = {
            "type": order_type,
            "request_id": request_id,
            "bot_id": bot_id,
            "ticker": ticker,
            "quantity": quantity,
            "price": int(price),  # 키움은 정수 가격
        }

        # 이벤트 구독 먼저 (명령 발행 전에 구독해야 누락 없음)
        pubsub = self._redis.pubsub()
        pubsub.subscribe(EVT_CHANNEL)

        self._publish(cmd)
        logger.info(f"[kiwoom] {order_type} {ticker} x{quantity} request_id={request_id}")

        deadline = time.time() + TIMEOUT_SEC
        try:
            while time.time() < deadline:
                message = pubsub.get_message(timeout=1.0)
                if not message or message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                if data.get("type") == "ORDER_RESULT" and data.get("request_id") == request_id:
                    if data.get("success"):
                        return OrderResult(
                            filled_price=float(data["filled_price"]),
                            order_number=data.get("order_number"),
                            success=True,
                        )
                    else:
                        raise RuntimeError(f"키움 주문 실패: {data.get('message', '')}")
        finally:
            pubsub.unsubscribe()
            pubsub.close()

        raise TimeoutError(f"키움 주문 응답 시간 초과 ({TIMEOUT_SEC}s): {ticker} {order_type}")

    def _publish(self, payload: dict):
        self._redis.publish(CMD_CHANNEL, json.dumps(payload, ensure_ascii=False))
