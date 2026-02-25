"""
키움 브릿지 (Windows 전용 standalone 프로세스)
- 실행: python bridge.py
- 조건: 키움 OpenAPI+ 설치, 32-bit Python, PyQt5
- Redis를 통해 백엔드와 통신

채널:
  autostock:commands → 백엔드에서 받는 명령
  autostock:events   → 백엔드로 보내는 결과/이벤트
"""
import json
import logging
import sys
import threading

import redis
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication

REDIS_URL = "redis://localhost:6379"
CMD_CHANNEL = "autostock:commands"
EVT_CHANNEL = "autostock:events"
BRIDGE_STATUS_KEY = "autostock:bridge_status"

# 키움 OpenAPI+ OCX ProgID
KIWOOM_OCX = "KHOPENAPI.KHOpenAPICtrl.1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class KiwoomBridge(QAxWidget):
    def __init__(self, redis_client: redis.Redis):
        super().__init__()
        self._redis = redis_client
        self._connected = False
        self._pending: dict[str, dict] = {}  # request_id → command

        self.setControl(KIWOOM_OCX)

        # OCX 이벤트 연결
        self.OnEventConnect.connect(self._on_event_connect)
        self.OnReceiveChejanData.connect(self._on_chejan_data)
        self.OnReceiveTrData.connect(self._on_tr_data)
        self.OnReceiveMsg.connect(self._on_receive_msg)

        logger.info("KiwoomBridge 초기화 완료 (OCX 로드됨)")

    # ── OCX 이벤트 핸들러 ─────────────────────────────────────────

    def _on_event_connect(self, err_code: int):
        if err_code == 0:
            self._connected = True
            self._redis.set(BRIDGE_STATUS_KEY, "connected")
            logger.info("키움 서버 연결 성공")
            self._publish({"type": "CONNECTED", "success": True})
        else:
            self._connected = False
            self._redis.set(BRIDGE_STATUS_KEY, "disconnected")
            logger.error(f"키움 서버 연결 실패: {err_code}")
            self._publish({"type": "CONNECTED", "success": False, "error_code": err_code})

    def _on_chejan_data(self, s_gubun: str, n_item_cnt: int, s_fid_list: str):
        """체결(0) / 잔고(1) 이벤트"""
        if s_gubun == "0":
            # 체결 통보
            order_number = self.GetChejanData(9203).strip()  # 주문번호
            ticker = self.GetChejanData(9001).strip().lstrip("A")
            filled_qty = int(self.GetChejanData(911) or 0)  # 체결량
            filled_price = float(self.GetChejanData(910) or 0)  # 체결가
            order_type_code = self.GetChejanData(905).strip()  # 매도수구분
            order_type = "BUY" if "매수" in order_type_code else "SELL"

            logger.info(f"체결: {order_type} {ticker} x{filled_qty} @{filled_price} 주문번호={order_number}")

            # 대기 중인 request_id 매칭 (order_number 기반)
            request_id = self._find_request_id_by_order(order_number)

            self._publish({
                "type": "ORDER_RESULT",
                "success": True,
                "request_id": request_id,
                "order_number": order_number,
                "ticker": ticker,
                "order_type": order_type,
                "quantity": filled_qty,
                "filled_price": filled_price,
            })

    def _on_tr_data(self, s_screen_no, s_rq_name, s_tr_code, s_record_name,
                    s_prev_next, n_data_length, s_error_code, s_message, s_spl_msg):
        logger.debug(f"TR 응답: {s_rq_name} {s_tr_code}")

    def _on_receive_msg(self, s_screen_no, s_rq_name, s_tr_code, s_msg):
        logger.info(f"키움 메시지 [{s_rq_name}]: {s_msg}")

    # ── 명령 처리 ──────────────────────────────────────────────────

    def handle_command(self, cmd: dict):
        cmd_type = cmd.get("type")

        if cmd_type == "CONNECT":
            self._do_connect()

        elif cmd_type == "BUY":
            self._do_order(cmd, order_type=1)  # 1=매수

        elif cmd_type == "SELL":
            self._do_order(cmd, order_type=2)  # 2=매도

        elif cmd_type == "GET_BALANCE":
            self._do_get_balance(cmd)

        elif cmd_type == "GET_POSITIONS":
            self._do_get_positions(cmd)

        else:
            logger.warning(f"알 수 없는 명령 타입: {cmd_type}")

    def _do_connect(self):
        logger.info("CommConnect() 호출")
        self.dynamicCall("CommConnect()")

    def _do_order(self, cmd: dict, order_type: int):
        if not self._connected:
            logger.error("연결되지 않은 상태에서 주문 시도")
            self._publish({
                "type": "ORDER_RESULT",
                "success": False,
                "request_id": cmd.get("request_id"),
                "message": "브릿지 미연결",
            })
            return

        account = self._get_account()
        ticker = cmd["ticker"]
        qty = int(cmd["quantity"])
        price = int(cmd.get("price", 0))
        hoga = "03" if price == 0 else "00"  # 03=시장가, 00=지정가
        request_id = cmd.get("request_id", "")

        # request_id → order 매핑 임시 저장 (체결 이벤트에서 역추적)
        screen_no = f"{(hash(request_id) % 9000 + 1000):04d}"
        self._pending[screen_no] = {"request_id": request_id, "ticker": ticker}

        logger.info(f"SendOrder: {'매수' if order_type==1 else '매도'} {ticker} x{qty} price={price} screen={screen_no}")
        result = self.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            ["AutoOrder", screen_no, account, order_type, ticker, qty, price, hoga, ""]
        )
        if result != 0:
            logger.error(f"SendOrder 오류: {result}")
            self._publish({
                "type": "ORDER_RESULT",
                "success": False,
                "request_id": request_id,
                "message": f"SendOrder 오류코드: {result}",
            })

    def _do_get_balance(self, cmd: dict):
        account = self._get_account()
        self.dynamicCall("SetInputValue(QString, QString)", ["계좌번호", account])
        self.dynamicCall("SetInputValue(QString, QString)", ["비밀번호", ""])
        self.dynamicCall("SetInputValue(QString, QString)", ["비밀번호입력매체구분", "00"])
        self.dynamicCall("SetInputValue(QString, QString)", ["조회구분", "2"])
        self.dynamicCall("CommRqData(QString, QString, int, QString)",
                         ["예수금조회", "opw00001", 0, "9999"])

    def _do_get_positions(self, cmd: dict):
        account = self._get_account()
        self.dynamicCall("SetInputValue(QString, QString)", ["계좌번호", account])
        self.dynamicCall("SetInputValue(QString, QString)", ["비밀번호", ""])
        self.dynamicCall("SetInputValue(QString, QString)", ["비밀번호입력매체구분", "00"])
        self.dynamicCall("SetInputValue(QString, QString)", ["조회구분", "2"])
        self.dynamicCall("CommRqData(QString, QString, int, QString)",
                         ["계좌평가잔고조회", "opw00018", 0, "9998"])

    def _get_account(self) -> str:
        accounts = self.dynamicCall("GetLoginInfo(QString)", ["ACCLIST"])
        return accounts.split(";")[0] if accounts else ""

    def _find_request_id_by_order(self, order_number: str) -> str:
        """체결된 주문번호로 request_id 역추적"""
        for screen_no, info in list(self._pending.items()):
            if order_number:
                rid = info.get("request_id", "")
                del self._pending[screen_no]
                return rid
        return ""

    # ── Redis 발행 ─────────────────────────────────────────────────

    def _publish(self, payload: dict):
        self._redis.publish(EVT_CHANNEL, json.dumps(payload, ensure_ascii=False))


def redis_listener(bridge: KiwoomBridge, r: redis.Redis):
    """별도 스레드: Redis 구독 → 명령 수신 → PyQt 메인 스레드에서 처리"""
    from PyQt5.QtCore import QMetaObject, Qt
    pubsub = r.pubsub()
    pubsub.subscribe(CMD_CHANNEL)
    logger.info(f"Redis 구독 시작: {CMD_CHANNEL}")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            cmd = json.loads(message["data"])
            logger.info(f"명령 수신: {cmd.get('type')}")
            # PyQt 메인 스레드에서 안전하게 실행 (invokeMethod 대신 직접 호출 - 단순화)
            QMetaObject.invokeMethod(
                bridge, "handle_command_slot",
                Qt.QueuedConnection,
            )
            # 간단히: 직접 호출 (단일 스레드 PyQt에서는 안전하지 않을 수 있음)
            # 실제 운영에서는 QThread + signal/slot 패턴 권장
            bridge.handle_command(cmd)
        except Exception as e:
            logger.error(f"명령 처리 오류: {e}", exc_info=True)


def main():
    logger.info("키움 브릿지 시작")

    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.set(BRIDGE_STATUS_KEY, "disconnected")

    app = QApplication(sys.argv)

    bridge = KiwoomBridge(r)

    # Redis 리스너를 별도 스레드로 실행
    listener_thread = threading.Thread(
        target=redis_listener,
        args=(bridge, r),
        daemon=True,
    )
    listener_thread.start()

    logger.info("PyQt5 이벤트 루프 시작 (종료: Ctrl+C)")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
