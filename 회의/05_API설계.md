# API 설계

**날짜**: 2026-02-24
**상태**: ✅ 확정

---

## 기본 규칙

- Base URL: `/api/v1`
- 인증: JWT Bearer Token (로그인 제외)
- 응답 형식: JSON

---

## Users

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/register` | 회원가입 |
| POST | `/auth/login` | 로그인 |

---

## Market

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/stocks` | 종목 목록 |
| GET | `/stocks/{ticker}` | 종목 상세 |
| GET | `/stocks/{ticker}/prices` | 주가 데이터 |
| GET | `/stocks/{ticker}/indicators` | 기술적 지표 |

---

## Strategies

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/strategies` | 전략 목록 |
| GET | `/strategies/{id}` | 전략 상세 |
| POST | `/strategies` | 전략 생성 |
| PUT | `/strategies/{id}` | 전략 수정 |
| DELETE | `/strategies/{id}` | 전략 삭제 |
| POST | `/strategies/{id}/backtest` | 백테스트 실행 |

---

## Trading

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/accounts` | 계좌 목록 |
| POST | `/accounts` | 계좌 등록 |
| DELETE | `/accounts/{id}` | 계좌 삭제 |
| GET | `/bots` | 봇 목록 |
| GET | `/bots/{id}` | 봇 상세 |
| POST | `/bots` | 봇 생성 |
| PUT | `/bots/{id}` | 봇 수정 |
| DELETE | `/bots/{id}` | 봇 삭제 |
| POST | `/bots/{id}/start` | 봇 시작 |
| POST | `/bots/{id}/stop` | 봇 정지 |
| GET | `/bots/{id}/positions` | 봇 현재 포지션 |
| GET | `/bots/{id}/orders` | 봇 주문 내역 |
| GET | `/bots/{id}/reports` | 봇 보고서 |

---

## 참고

- CRUD: Create(POST), Read(GET), Update(PUT), Delete(DELETE)
- 특정 동작은 URL에 동사 포함: `/start`, `/stop`, `/backtest`
