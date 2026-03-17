# AutoStock — AI 기반 한국 주식 자동매매 시스템

한국 주식(KOSPI/KOSDAQ)을 대상으로 ML 스코어링, LLM 전략 생성, 백테스트, 자동매매까지 하나의 파이프라인으로 운영하는 풀스택 자동매매 플랫폼입니다.

---

## 주요 기능

### AI 캔버스
노드 기반 드래그앤드롭 파이프라인 빌더. 자연어 명령으로 전략을 구성하고 실행합니다.

| 노드 | 역할 |
|------|------|
| 시장 컨텍스트 | 뉴스·지수·투자자동향 수집 |
| 기술 지표 DB | RSI·MACD·볼린저밴드 등 DB 조회 |
| ML 스코어 캐시 | 저장된 ML 스코어링 결과 |
| 기존 전략 | DB에서 전략 선택 |
| 전략 빌더 | 조건 직접 설정 후 저장 |
| ML 모델 | RandomForest 학습 및 종목 스코어링 |
| LLM 전략 생성 | Claude AI 기반 전략 자동 생성 |
| 백테스트 | 전략 성과 시뮬레이션 |
| 봇 적용 | 생성된 전략을 자동매매 봇에 적용 |

### AI 어시스턴트
- 자연어로 파이프라인 구성·실행·수정
- 노드 에러 자동 진단 및 수정 명령 실행
- **실시간 데이터 기반 자동 최적화**: ML 스코어·시장 지표·백테스트 성과를 분석해 전략 조건·파라미터 자동 업데이트
- 주식 전문 지식 베이스 상시 참조 (한국 시장 규칙, 기술 지표 해석, 켈리 공식, 시장 국면 판단 등)

### ML 스코어링 엔진
- 13개 피처 (RSI, MACD, Stoch, ADX, ATR, 볼린저 위치, RSI 3일 변화율, 거래량 비율 등)
- ATR 정규화 라벨 (단순 수익률 대신 변동성 대비 수익률)
- Walk-forward 검증 (75% 학습 / 25% OOS 정확도 측정)

### 백테스트 엔진
- 손절(7%)/익절(15%)/최대보유일(20일) 기본 적용
- next-day fill: 신호 발생 다음날 시가 체결 (현실적 시뮬레이션)
- 지원 지표: RSI, MACD, 볼린저밴드, MA, Stochastic, ADX, ATR, 거래량 비율, 시가 갭 등

### LLM 전략 생성
- Claude API 기반 시장 컨텍스트 + ML 인사이트 분석
- 백테스트 품질 게이팅: 거래 ≥ 3회, 수익률 ≥ -15%, 승률 ≥ 25% 미충족 시 자동 폐기
- 신뢰도 점수: Sharpe 기반 자동 계산

### 자동매매 봇
- 스윙(일봉) / 단타(분봉) 두 가지 엔진
- 일봉 봇: 1일 1회 중복 매수 방지 (Redis 기반 dedup)
- 단타 봇: 트레일링 스탑, confirm bars 연속 신호 확인
- KIS(한국투자증권) API 연동 (모의/실계좌)

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Vue 3 + TypeScript, VueFlow, Pinia |
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| 비동기 작업 | Celery + Redis |
| ML | scikit-learn (RandomForestClassifier) |
| AI | Anthropic Claude API (claude-sonnet-4-6) |
| 인프라 | Docker Compose |
| 증권사 | 한국투자증권 KIS API |

---

## 프로젝트 구조

```
AutoStock/
├── backend/
│   ├── api/           # FastAPI 라우터 (ai, bots, strategies, auth 등)
│   ├── models/        # SQLAlchemy ORM 모델
│   ├── services/      # 백테스트 엔진, KIS 브로커
│   ├── tasks/         # Celery 태스크 (ML, LLM, 봇 엔진, 크롤러)
│   ├── broker/        # KIS API 래퍼
│   ├── knowledge/     # AI 어시스턴트 주식 전문 지식 베이스
│   └── main.py
├── frontend/
│   └── src/
│       ├── views/     # CanvasView, BotView, AiView 등
│       ├── components/
│       └── stores/    # Pinia (auth)
├── kiwoom_bridge/     # 키움증권 브릿지 (Windows 전용)
├── 회의/              # 설계 문서 (01~11번)
└── docker-compose.yml
```

---

## 실행 방법

### 사전 준비
- Docker Desktop 설치
- `.env` 파일 설정 (`.env.example` 참고)

```env
ANTHROPIC_API_KEY=your_key   # Claude AI 전략 생성
KIS_APP_KEY=your_key         # 한국투자증권 API
KIS_APP_SECRET=your_secret
KIS_ACCOUNT_NO=12345678-01
```

### 백엔드 실행

```bash
docker compose up -d
```

서비스 목록:
- `autostock-backend` — FastAPI (port 8001)
- `autostock-celery-worker` — Celery 워커
- `autostock-celery-beat` — 스케줄러
- `autostock-postgres` — PostgreSQL
- `autostock-redis` — Redis

### 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev   # http://localhost:3001
```

---

## AI 캔버스 사용법

1. 상단 팔레트에서 노드를 추가하거나 하단 AI 어시스턴트에 자연어로 요청
2. 노드 간 연결선을 드래그해 파이프라인 구성
3. 각 노드의 ▶ 실행 버튼 또는 전체 실행 클릭
4. **자동 최적화**: AI 어시스턴트에 "지금 데이터 보고 전략 최적화해줘" 입력
   → 실시간 ML 스코어·시장 지표·백테스트 성과를 분석해 전략 조건 자동 업데이트

### 추천 파이프라인 구성

```
[시장 컨텍스트] ──┐
                  ├──▶ [LLM 전략 생성] ──▶ [백테스트] ──▶ [봇 적용]
[ML 스코어 캐시] ──┘

[기술 지표 DB] ──▶ [ML 모델] ──┐
                               └──▶ [LLM 전략 생성]
```

---

## 설계 문서

| 문서 | 내용 |
|------|------|
| [01 프로젝트 기획](회의/01_프로젝트_기획.md) | 목표, 범위 |
| [02 기술스택](회의/02_기술스택.md) | 기술 선택 이유 |
| [03 DB 설계](회의/03_DB설계.md) | 테이블 구조 |
| [09 AI 캔버스 설계](회의/09_캔버스_AI탭_설계.md) | 캔버스 아키텍처 |
| [10 시스템 보수 설계](회의/10_시스템_보수_설계.md) | P1~P5 개선 내역 |
| [11 주식 전문 지식베이스](회의/11_주식_전문_지식베이스.md) | AI 참고 자료 |

---

## 라이선스

개인 프로젝트입니다. 참고·학습 목적으로 자유롭게 활용 가능합니다.
실거래 사용에 따른 손실에 대한 책임은 본인에게 있습니다.
