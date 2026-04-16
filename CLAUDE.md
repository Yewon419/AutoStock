# AutoStock — Claude Code 가이드

AI 기반 한국 주식 자동매매 플랫폼 (FastAPI + Vue 3 + Docker)

---

## 빠른 실행

### 백엔드 (Docker)
```bash
# 전체 스택 시작
docker compose up -d

# 로그 확인
docker compose logs -f backend
docker compose logs -f celery-worker

# 중지
docker compose down
```

| 서비스 | 접속 주소 |
|--------|-----------|
| Backend API | http://localhost:8001 |
| Swagger 문서 | http://localhost:8001/docs |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6379 |

### 프론트엔드
```bash
cd frontend
npm run dev -- --host --port 3001
# http://localhost:3001
```

### DB 초기화 (최초 1회)
```bash
docker exec autostock-backend python -c \
  "from core.database import Base, engine; Base.metadata.create_all(engine)"
```

---

## 환경변수 (.env)

```env
DATABASE_URL=postgresql://autostock:autostock123@postgres:5432/autostock
REDIS_URL=redis://redis:6379
JWT_SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here
BROKER_MODE=mock                    # mock | paper | real
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NO=12345678-01
KIS_IS_PAPER=true
ANTHROPIC_API_KEY=...
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

Fernet 키 생성:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 프로젝트 구조

```
AutoStock/
├── backend/
│   ├── api/            # FastAPI 라우터 (ai, trading, dashboard, market, strategies, broker, users)
│   ├── models/         # SQLAlchemy ORM
│   ├── services/       # 비즈니스 로직 (backtest_engine, trading_service)
│   ├── tasks/          # Celery 태스크 (bot_engine, scalping_engine, ai_tasks, llm_strategy, collect)
│   ├── broker/         # KIS / Mock 브로커
│   ├── core/           # 설정, DB 세션, JWT 인증
│   └── knowledge/      # AI 어시스턴트 지식베이스
├── frontend/src/
│   ├── views/          # DashboardView, CanvasView, BotDetailView 등
│   ├── components/     # FlowNode (VueFlow 노드 UI)
│   └── stores/         # Pinia 상태 관리
├── docker-compose.yml
├── .env
└── 회의/               # 설계 문서 01~11번
```

---

## 주요 설계 원칙

- **브로커 모드**: `mock`(완전 시뮬레이션) → `paper`(KIS 모의) → `real`(실계좌) 순으로 검증
- **실계좌 안전장치**: 매수 전 실잔고 확인 필수, DB cash 자동 동기화
- **봇 타입**: 스윙(일봉, 1일 1회) / 단타(분봉, 트레일링 스탑)
- **전략 품질 게이팅**: 거래 ≥ 3회, 수익률 ≥ -15%, 승률 ≥ 25% 미충족 시 자동 폐기
- **AI 모델**: `claude-sonnet-4-6` (LLM 전략 생성, AI 어시스턴트)

---

## 현재 개발 단계

Phase 7 — KIS 실전 소액 주문 검증 중

| Phase | 내용 | 상태 |
|-------|------|------|
| 1~6 | 기반 구축, Mock 거래, ML, AI 캔버스, KIS paper | 완료 |
| 7 | KIS 실전 소액 주문 검증 | **진행 중** |

---

## 자주 쓰는 명령어

```bash
# 컨테이너 재빌드
docker compose up -d --build

# 특정 서비스만 재시작
docker compose restart backend

# 백엔드 컨테이너 내부 접속
docker exec -it autostock-backend bash

# 프론트엔드 타입 체크
cd frontend && npx tsc --noEmit
```

---

## Git 규칙

- 커밋 후 **반드시 push**까지 실행 (`git push origin master`)
- GitHub: https://github.com/Yewon419/AutoStock
