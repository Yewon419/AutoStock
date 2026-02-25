# Docker 구성

**날짜**: 2026-02-24
**상태**: ✅ 확정

---

## 컨테이너 목록

| 컨테이너 | 역할 | 포트 |
|----------|------|------|
| `backend` | FastAPI 백엔드 | 8000 |
| `frontend` | Vue 3 프론트엔드 | 3000 |
| `postgres` | PostgreSQL + TimescaleDB | 5432 |
| `redis` | Redis (메시지 큐, 캐시) | 6379 |
| `kiwoom_bridge` | 키움/Mock 브릿지 | - |

총 **5개 컨테이너**

---

## 주의사항

- `kiwoom_bridge`는 Windows 전용 (OCX 의존)
- 나머지 4개는 Linux 컨테이너로 실행 가능
- Mock 모드 / Real 모드는 환경변수로 전환

```env
BROKER_MODE=mock   # Mock 브릿지
BROKER_MODE=real   # 키움 브릿지
```

---

## 컨테이너 의존성

```
frontend → backend
backend → postgres, redis
kiwoom_bridge → redis
```

---

## docker-compose.yml 구조 (초안)

```yaml
services:
  postgres:
    image: timescale/timescaledb:latest-pg14

  redis:
    image: redis:7

  backend:
    build: ./backend
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    depends_on:
      - backend

  kiwoom_bridge:
    build: ./kiwoom_bridge
    depends_on:
      - redis
```
