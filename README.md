# AutoStock

> AI와 함께 설계하고, 직접 거래하는 한국 주식 자동매매 플랫폼

KOSPI/KOSDAQ 종목을 대상으로 ML 스코어링, Claude AI 전략 생성, 백테스트, KIS 실계좌 자동매매까지 하나의 파이프라인으로 운영하는 풀스택 시스템입니다.

<p align="center">
  <img src="docs/screenshots/login.png" width="49%" alt="로그인 — 라이브 시세 티커·오더북 카드">
  <img src="docs/screenshots/bot-dashboard.png" width="49%" alt="봇 상세 — 자산·승률·샤프·보유 종목, AI 튜닝 어시스턴트">
</p>
<p align="center">
  <img src="docs/screenshots/canvas.png" width="49%" alt="AI 캔버스 — 노드 파이프라인 편집기 + AI 어시스턴트">
  <img src="docs/screenshots/stock-data.png" width="49%" alt="주식 데이터 — 캔들 차트·RSI/MACD 지표">
</p>
<p align="center"><sub>로그인 · 봇 상세(mock 계좌) · AI 캔버스 · 주식 데이터</sub></p>

---

## 화면 구성

| 탭 | 설명 |
|----|------|
| 대시보드 | Mock/실계좌 자산 분리 표시, 오늘 거래 내역, AI 캔버스 바로가기 |
| 주식 데이터 | 종목 검색, 일봉 차트, 기술 지표 |
| **AI 캔버스** | 노드 파이프라인 빌더 + AI 어시스턴트 채팅 |
| 자동매매 | 봇 목록, 생성·시작·정지, 성과 상세 |
| 전략 관리 | 전략 CRUD, 백테스트 실행 |
| AI 분석 | ML 스코어 조회, 전략 분석 요청 |
| 연결 설정 | KIS API 키 등록, 브로커 모드 전환 |

---

## 주요 기능

### AI 캔버스
노드 기반 드래그앤드롭 파이프라인 빌더. 자연어 명령으로 전략을 구성하고 실행합니다.

```
[시장 컨텍스트] ──┐
                  ├──▶ [LLM 전략 생성] ──▶ [백테스트] ──▶ [봇 적용]
[ML 스코어 캐시] ──┘

[기술 지표 DB] ──▶ [ML 모델] ──▶ [LLM 전략 생성]
```

**지원 노드 타입**

| 종류 | 노드 |
|------|------|
| 데이터 소스 | 시장 컨텍스트, 기술 지표 DB, ML 스코어 캐시, 계좌 설정 |
| 전략 | 기존 전략 선택, 전략 빌더 (조건 직접 설정) |
| 처리 | ML 모델, LLM 전략 생성, 백테스트 |
| 출력 | 봇 적용 (자동 생성 + 전략 연동) |

**AI 어시스턴트**
- 자연어로 노드 추가·연결·실행
- 에러 자동 진단 및 수정
- 실시간 ML 스코어·시장 지표·백테스트 결과 기반 전략 자동 최적화
- 캔버스별 채팅 로그 영구 저장, 마지막 선택 캔버스 복원

---

### ML 스코어링
- 13개 피처 (RSI, MACD, Stochastic, ADX, ATR, 볼린저 위치, 거래량 비율 등)
- ATR 정규화 라벨 (변동성 대비 수익률)
- Walk-forward 검증 (75% 학습 / 25% OOS)

### LLM 전략 생성
- Claude API (`claude-sonnet-4-6`) 기반
- 시장 컨텍스트 + ML 인사이트 분석 후 조건부 전략 자동 생성
- 품질 게이팅: 거래 ≥ 3회, 수익률 ≥ -15%, 승률 ≥ 25% 미충족 시 자동 폐기
- Sharpe 기반 신뢰도 점수

### 백테스트 엔진
- Next-day fill 방식 (신호 발생 다음날 시가 체결)
- 손절 7% / 익절 15% / 최대 보유일 20일 기본값
- 지원 조건: RSI, MACD, 볼린저밴드, MA, Stochastic, ADX, ATR, 거래량 비율, 시가 갭 등 15+

### 자동매매 봇
- **스윙 봇** (일봉): 1일 1회 중복 매수 방지 (Redis dedup)
- **단타 봇** (분봉): 트레일링 스탑, confirm bars 연속 신호 확인
- KIS 모의투자(paper) / 실계좌(real) 자동 전환
- 실계좌 매수 전 실잔고 확인, DB cash 자동 동기화

### 성과 평가 (100점 만점)
봇 상세 → 일별 보고서 탭에서 확인할 수 있습니다.

| 카테고리 | 가중치 | 주요 지표 |
|----------|--------|-----------|
| 수익률 | 30% | 총 수익률, 샤프비율 보너스 |
| 리스크 관리 | 25% | 샤프비율, 최대낙폭(MDD) |
| 안정성 | 20% | MDD, 수익일 비율 |
| 일관성 | 15% | 승률, 최대연속손실, 거래 수 |
| 거래 효율 | 10% | 손익비(Profit Factor), 평균손익비율 |

**등급**: S (90+) · A (80+) · B (70+) · C (60+) · D (50+) · F

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| Frontend | Vue 3, TypeScript, VueFlow, Pinia, Vite, Lightweight Charts |
| Backend | FastAPI, SQLAlchemy, Pydantic v2 |
| Database | PostgreSQL (TimescaleDB), Redis |
| 비동기 작업 | Celery + Redis Broker |
| ML | scikit-learn (RandomForestClassifier) |
| AI | Anthropic Claude API (claude-sonnet-4-6) |
| 브로커 | KIS 한국투자증권 REST API |
| 인프라 | Docker Compose |

---

## 프로젝트 구조

```
AutoStock/
├── backend/
│   ├── api/            # FastAPI 라우터
│   │   ├── ai.py       # AI 캔버스, LLM 전략, ML 스코어, 백테스트
│   │   ├── trading.py  # 봇 CRUD, 체결 내역, 성과 평가
│   │   ├── dashboard.py # 요약 통계, 오늘 거래 내역
│   │   ├── market.py   # 종목 검색, 가격/지표 조회
│   │   ├── strategies.py
│   │   ├── broker.py
│   │   └── users.py
│   ├── models/         # SQLAlchemy ORM (User, TradingBot, Strategy, Execution, BotReport ...)
│   ├── services/       # 비즈니스 로직 (backtest_engine, trading_service ...)
│   ├── tasks/          # Celery 태스크
│   │   ├── bot_engine.py       # 스윙 봇 실행, 일별 보고서 생성
│   │   ├── scalping_engine.py  # 단타 봇 실행
│   │   ├── ai_tasks.py         # ML 학습·스코어링·최적화
│   │   ├── llm_strategy.py     # Claude API 전략 생성
│   │   ├── collect.py          # 일봉 데이터 수집
│   │   ├── indicators.py       # 기술 지표 계산
│   │   └── intraday_collector.py
│   ├── broker/         # KIS, Mock 브로커 구현체
│   ├── core/           # 설정, DB 세션, JWT 인증
│   └── knowledge/      # AI 어시스턴트용 주식 전문 지식베이스
├── frontend/
│   └── src/
│       ├── views/      # DashboardView, CanvasView, BotDetailView ...
│       ├── components/ # FlowNode (VueFlow 노드 UI)
│       ├── stores/     # Pinia (auth)
│       └── layouts/    # AppLayout (사이드바, 헤더)
├── docker-compose.yml
├── .env.example
└── 회의/               # 설계 문서 (01~11번 MD)
```

---

## 실행 방법

### 1. 환경변수 설정

```bash
cp .env.example .env
```

```env
# PostgreSQL
DATABASE_URL=postgresql://autostock:autostock123@postgres:5432/autostock
REDIS_URL=redis://redis:6379

# 보안 (필수)
JWT_SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 브로커 모드 (mock | paper | real)
BROKER_MODE=mock

# KIS 한국투자증권 (paper/real 모드 시 필요)
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=12345678-01
KIS_IS_PAPER=true

# Claude AI (AI 캔버스 사용 시 필요)
ANTHROPIC_API_KEY=your_claude_api_key

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### 2. 백엔드 실행 (Docker)

```bash
docker compose up -d
```

| 서비스 | URL / 포트 |
|--------|------------|
| Backend API | http://localhost:8001 |
| API 문서 (Swagger) | http://localhost:8001/docs |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6379 |

### 3. DB 초기화 (최초 1회)

```bash
docker exec autostock-backend python -c \
  "from core.database import Base, engine; Base.metadata.create_all(engine)"
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev -- --host --port 3001
# http://localhost:3001
```

---

## Celery 자동 스케줄

| 태스크 | 스케줄 |
|--------|--------|
| 일봉 데이터 수집 | 매일 07:00 |
| 기술 지표 계산 | 매일 08:00 |
| ML 스코어링 | 매일 09:00 |
| 스윙 봇 실행 | 매 5분 (평일 09:00~15:30) |
| 일별 보고서 생성 | 매일 16:00 |

---

## 주요 API 엔드포인트

```
# 인증
POST   /api/v1/auth/register
POST   /api/v1/auth/login

# 봇
GET    /api/v1/bots
POST   /api/v1/bots
POST   /api/v1/bots/{id}/start
POST   /api/v1/bots/{id}/stop
GET    /api/v1/bots/{id}/performance
GET    /api/v1/bots/{id}/report-score     # 100점 성과 평가
GET    /api/v1/bots/{id}/reports          # 일별 보고서

# 대시보드
GET    /api/v1/dashboard/summary          # Mock/실계좌 자산 분리 포함
GET    /api/v1/dashboard/today-trades     # 오늘 체결 목록

# AI 캔버스
POST   /api/v1/ai/canvas-assistant        # 자연어 파이프라인 조작
POST   /api/v1/ai/generate-strategy       # LLM 전략 생성
POST   /api/v1/ai/backtest-strategy       # 백테스트 실행
POST   /api/v1/ai/score                   # ML 스코어링
GET    /api/v1/ai/canvases                # 캔버스 목록
POST   /api/v1/ai/canvas-state            # 캔버스 상태 저장

# 시장
GET    /api/v1/market/stocks              # 종목 검색 (페이지네이션)
GET    /api/v1/market/stocks/{ticker}/prices
GET    /api/v1/market/stocks/{ticker}/indicators

# 전략
GET    /api/v1/strategies
POST   /api/v1/strategies/{id}/backtest
```

---

## 개발 팁

```bash
# 백엔드 로그 실시간 확인
docker logs -f autostock-backend

# Celery 워커 로그
docker logs -f autostock-celery-worker

# DB 직접 접속
docker exec -it autostock-postgres psql -U autostock -d autostock

# Redis CLI
docker exec -it autostock-redis redis-cli

# 특정 Celery 태스크 수동 실행
docker exec autostock-backend python -c \
  "from tasks.bot_engine import generate_daily_reports; generate_daily_reports.delay()"
```

---

## 라이선스

개인 프로젝트입니다. 참고·학습 목적으로 자유롭게 활용 가능합니다.  
실거래 사용에 따른 손실 책임은 본인에게 있습니다.
