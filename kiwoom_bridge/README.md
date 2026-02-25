# 키움 브릿지

## 사전 조건
1. 키움 OpenAPI+ 설치 (https://www1.kiwoom.com/h/customer/download/VDownloadKOAIView)
2. 32-bit Python 3.9+ 설치
3. 의존성 설치: `pip install -r requirements.txt`
4. Redis 실행 중 (AutoStock Docker: redis://localhost:6379)

## 실행
```bash
python bridge.py
```

## 동작 방식
1. 실행 시 Redis `autostock:bridge_status` = "disconnected" 설정
2. `autostock:commands` 채널 구독 대기
3. CONNECT 명령 수신 → 키움 로그인 창 표시
4. 로그인 성공 → bridge_status = "connected", CONNECTED 이벤트 발행
5. BUY/SELL 명령 수신 → SendOrder 호출
6. 체결 이벤트 → ORDER_RESULT 이벤트 발행

## 백엔드 설정
`backend/.env` 에서:
```
BROKER_MODE=real
```
으로 변경 후 Docker 재시작.
