# AutoStock 프론트엔드 디자인 통일 로그

**기간**: 2026-05-23
**범위**: 프론트엔드 전체 (8뷰 + 1레이아웃 + 3컴포넌트 + 디자인 토큰)
**최종 커밋**: `5885eb8`

---

## 배경

기존 톤: 파란 액센트 `#4f9eff`, 이모지 아이콘, 단조로운 다크 박스.
신규 톤: 트레이딩 터미널 HUD 컨셉. 다크 베이스 + 골드 액센트 + 모노 캡스 라벨 +
Lucide-스타일 SVG 아이콘.

레퍼런스: matveyan.com (브루털 미니멀 + HUD 오버레이)
시작점: LoginView 풀 리디자인 (`386ec83`)

---

## 페이즈 / 커밋

| Phase | Commit | 파일 | 핵심 |
|---|---|---|---|
| Login | `386ec83` | LoginView.vue | 글래스 카드 → 풀블리드 HUD + 시그널 웨이브 + 유리 데이터 패널 3장 |
| 0 | `dd85a1c` | assets/main.css | CSS 변수 100+ (color·font·space·radius·shadow·motion·z-index·layout) |
| 1 | `9a0571c` | layouts/AppLayout.vue | 글래스 topbar + SVG 사이드바 + 알림 드롭다운 |
| 2-? | `ff0e909` | views/DashboardView.vue | AI 캔버스 배너 제거 + dead code 정리 |
| 2-A | `b1f776c` | DashboardView + main.css | Korean PnL 토큰 + 6 stat 카드 grid + 거래 모달 |
| 2-B | `6969187` | MarketView.vue | 검색바 + KOSPI/KOSDAQ 토글 + 종목 테이블 |
| 2-C | `9b67c6e` | StockDetailView.vue | 한국 캔들 차트 + 1M/3M/6M/1Y + RSI/MACD/VOL 지표 |
| 2-D | `87c8252` | ConnectionView.vue | 브로커 카드 + 계좌 폼 + 5단계 가이드 |
| 3-A | `8daf0e8` | BotView.vue | 봇 카드 grid + SWING/SCALPING 생성 모달 |
| 3-B | `a8c94e5` | AiView + main.css | violet 토큰 + 3탭(ML/최적화/LLM) + SVG chart + 적용 모달 |
| 3-C | `0a551b9` | BotDetailView.vue | 5탭 + 종합 성과 + 점수 카드 + 수정 모달 (1832줄 추가) |
| 4-A·B·C | `b733b4a` | BotCanvas + FlowNode + MlInsightPanel | 캔버스 wrapper + VueFlow 노드 + ML 인사이트 |
| 4-D | `5885eb8` | views/CanvasView.vue | 노드 편집기 (2168 → 3377줄) |

---

## 디자인 시스템 (단일 출처: `frontend/src/assets/main.css`)

### Color tokens

```
Surface:
  --bg-base       #050507    (page bg)
  --bg-elevated   #0a0c12    (header bg)
  --surface-1     #0d1118    (card bg)
  --surface-2     #14181f    (hover bg)
  --glass-bg      rgba(20,24,34,0.55)
  --glass-bg-strong rgba(20,24,34,0.75)

Text:
  --text-primary  #fafafa
  --text-secondary #d4d4d8
  --text-tertiary #a1a1aa
  --text-muted    #71717a
  --text-faint    #3f3f46

Accent (gold):
  --accent        #f59e0b
  --accent-hover  #fbbf24
  --accent-bg     rgba(245,158,11,0.14)
  --accent-border rgba(245,158,11,0.2)
  --shadow-gold   0 4px 24px -8px rgba(245,158,11,0.5)

Korean PnL (익=빨강, 손=파랑):
  --profit        #ef4444
  --profit-bg     rgba(239,68,68,0.12)
  --profit-soft   #fca5a5
  --loss          #60a5fa
  --loss-bg       rgba(96,165,250,0.12)
  --loss-soft     #93c5fd

Market (Western, generic):
  --up            #4ade80
  --up-strong     #22c55e
  --down          #f87171

AI/LLM:
  --violet        #a78bfa
  --violet-strong #7c3aed
  --violet-bg     rgba(167,139,250,0.1)
  --violet-border rgba(167,139,250,0.3)

Status:
  --success #22c55e  --warn #f59e0b  --danger #ef4444  --info #60a5fa

Borders:
  --border          rgba(255,255,255,0.08)
  --border-strong   rgba(255,255,255,0.14)
  --border-faint    rgba(255,255,255,0.05)
```

### Typography

```
--font-sans  Inter, Pretendard, Apple SD Gothic Neo, Noto Sans KR
--font-mono  JetBrains Mono, ui-monospace, SF Mono

Sizes: --text-xs 10.5px → --text-hero clamp(34,5.2vw,62)
Tracking: --tracking-tightest -0.04em → --tracking-hud 0.18em
```

### Spatial

```
Space: --space-1 4px → --space-20 80px (4·8·12·16·20·24·28·32·40·48·64·80)
Radius: --radius-xs 3px → --radius-2xl 20px + --radius-full
Layout: --header-h 56px / --sidebar-w 220px / --content-max 1280px
```

### Motion

```
--ease-out-expo  cubic-bezier(0.16, 1, 0.3, 1)
--dur-fast 150ms  --dur-base 250ms  --dur-slow 400ms  --dur-cinematic 900ms
```

전역 `prefers-reduced-motion` 차단 적용됨.

---

## 컨벤션

### 페이지 헤더
```vue
<header class="page-header">
  <span class="page-eyebrow">DOMAIN / 한글</span>
  <h1 class="page-title">한글 타이틀</h1>
</header>
```

### 패널 헤더
```vue
<div class="panel-head">
  <span class="panel-title">SECTION · 한글</span>
</div>
```

### 버튼
- **Primary** (gold pill): `--accent` bg + `--bg-base` 텍스트 + `--shadow-gold`
- **Ghost** (secondary): 투명 + `--border` + hover 시 골드
- **Red ghost** (danger): `--profit-bg` + `--profit` 텍스트
- **Violet** (AI/LLM): `--violet-bg` + `--violet-border`
- 모든 버튼 mono caps + SVG (Lucide stroke 1.75)

### 모달
- backdrop `rgba(0,0,0,0.65)` + `blur(4px)`
- `--bg-elevated` 카드 + `--shadow-xl`
- 헤더: `--surface-1` bg + eyebrow + title
- 진입 모션: `modalIn` scale 0.98→1 + y +12→0 (0.4s ease-out-expo)

### 테이블
- 헤더: `--bg-elevated` bg, mono caps uppercase, `--text-muted`
- numeric 칼럼: `font-family: var(--font-mono); font-variant-numeric: tabular-nums;`
- 행 hover: `--surface-2`
- 티커: mono + bold

### 차트 (lightweight-charts)
- 배경 `#0d1118`, 그리드 `rgba(255,255,255,0.04)`, 보더 `rgba(255,255,255,0.08)`
- 텍스트 `#a1a1aa`, 한국 캔들 (up=`#ef4444` / down=`#60a5fa`)

### VueFlow 노드 (카테고리 색)
- source = `--info` blue
- strategy = `--accent` gold
- processing = `--violet`
- output = `--up-strong` green
- config = `--accent-dim` amber-dim

---

## 검증 상태

- **빌드**: 12개 커밋 전부 `npm run build-only` 통과
- **타입 체크**: 사전 존재 TS7016 외 새 에러 없음
- **시각 검증**: 사용자 직접 (브라우저)
- **로직 검증**: 모든 fetch / state / handler / computed 1:1 보존

### 보존된 로직 (체크리스트)
- AppLayout: pendingSummary 30s 폴링, lastSeenMap localStorage
- Dashboard: fetchAll 30s 폴링, emergencyStop, openTodayTrades, clearAlerts
- Market: search debounce 300ms, setMarket, changePage, triggerCollect
- StockDetail: setPeriod, renderCharts, renderIndicatorChart, collectThis
- Connection: connectBroker, addAccount, deleteAccount, fmtTtl
- Bot: createBot (SWING/SCALPING defaults), startBot/stopBot/deleteBot, 5s 폴링
- AI: scoring/optimize/LLM 폴링, applyToBot, openApplyModal
- BotDetail: 5탭 fetch + lightweight-charts 캔들 + 점수 카드
- BotCanvas: AI 채팅 (claude-sonnet-4-6), proposal apply/dismiss, undo, suggestions, history
- CanvasView: 노드 추가/삭제, 자동 저장, 실행, 다중 캔버스, AI 어시스턴트, VueFlow 모든 훅

### 미언급 / 손대지 않음
- `frontend/src/views/StrategyView.vue` (757줄) — 라우트 폐기 + import 0건. 고아.
- `frontend/src/views/StrategyDetailView.vue` (480줄) — 동일.
- 필요 없으면 삭제 가능. 사용자 결정 보류.

---

## 다음 작업 후보

1. 브라우저 전체 동선 점검 (모든 페이지 + 모달 + 차트)
2. 고아 파일(`StrategyView`/`StrategyDetailView`) 삭제 여부 결정
3. 모바일 반응형 추가 점검 (≤640px, ≤900px, ≤1024px 단계)
4. WCAG 대비 측정 (특히 muted 텍스트 + glass 카드)
5. (선택) LoginView 시세 티커 색을 Korean 컨벤션으로 재정렬 — 현재 Western (up=green)
