# AutoStock 로그인 페이지 리디자인

다음 세션 진입 시 이 파일부터 읽고 시작.

---

## 출처

인스타 릴스 — valeridoesai
https://www.instagram.com/reel/DYC-x8DogOI/

캡션: "Most people still think building a premium website takes weeks,
designers, and a huge budget. Reality? Claude just replaced half that
workflow."

영상이 쓴 스택:
- Claude Code (터미널)
- UI UX Pro Max skill ← 이미 설치 완료 (`claude plugin list`)
- 21st.dev Hero sections
- Framer Motion

---

## 스택 매핑 (영상 → AutoStock)

영상은 React 기반. AutoStock 프론트는 Vue 3 + Vite + TypeScript.
그대로 못 옮기므로 매핑 필요.

| 영상 (React) | AutoStock (Vue 3) |
|---|---|
| Framer Motion | Motion-v (motion for Vue) 또는 @vueuse/motion 또는 GSAP |
| 21st.dev 컴포넌트 | 컴포넌트 코드 X, 마크업/CSS/디자인 톤만 참고 |
| Tailwind | 현재 LoginView는 scoped CSS. Tailwind 도입 여부 먼저 결정 |

→ 새 세션 첫 결정 사항: **모션 라이브러리 + Tailwind 도입 여부**.

---

## 손댈 파일

- `frontend/src/views/LoginView.vue` (195줄, template + script setup + scoped CSS 한 묶음)
- 로직은 그대로 둘 것:
  - `mode` ref (login/register 토글)
  - `form` reactive (username/email/password)
  - `submit()` → `auth.login()` / `auth.register()`
  - `loading` / `error` / `success` 상태
- 디자인만 갈아끼움.

라우터·스토어는 안 건드림:
- `frontend/src/router/index.ts:8-10, 66, 68`
- `frontend/src/stores/auth.js`

---

## 현재 상태 (변경 전)

다크 톤 박스 카드.
- 배경 `#0f1117`, 박스 `#1a1d27`, border `#2a2d3e`
- 액센트 `#4f9eff`
- max-width 420px, padding 40px, radius 12px
- 탭(로그인/회원가입) + 필드 3개 + 에러/성공 메시지 + submit

---

## 작업 디렉토리

```
design-scratch/login/
├── README.md       ← 이 파일
├── references/     스크린샷·팔레트·영감
└── mockups/        시안 HTML/Vue 단일파일들
```

`design-scratch/`는 AutoStock git 추적되는 폴더 (gitignore 안 함).
완성품은 LoginView.vue에 흡수하고 같이 커밋.

---

## 결정 사항 (2026-05-23 확정)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 모션 라이브러리 | **Motion-v** (Framer Motion의 Vue 포팅) |
| 2 | Tailwind | **도입 안 함** (scoped CSS 유지) |
| 3 | 디자인 방향 | **glassmorphism** (blur·투명도·텍스트 명도 대비 검증 필요) |
| 4 | 모션 강도 | **입장 페이드 + 호버·포커스** |
| 5 | 회원가입 UX | **로그인 우선 + 회원가입 작게** (하단 링크·모달) |

### 디자인 리스크 메모
- glassmorphism은 가독성 함정이 있음. blur 강도와 배경 콘트라스트가 약하면
  텍스트 명도 대비 4.5:1 미만으로 떨어질 수 있음. 모킹 단계에서 WCAG AA
  대비 측정 + 다크 톤 위에 frosted layer 깔 때 배경 밝기 고정 필요.

---

## 작업 완료 (2026-05-23)

1. ✅ `motion-v@2.2.1` 설치
2. ✅ ui-ux-pro-max로 팔레트·폰트 3안 → **C (Slate Gold)** 픽
3. ✅ 시안 `mockups/C-slate-gold.vue` (시각 보존본, 로직 없음)
4. ✅ `frontend/src/views/LoginView.vue` 흡수 — 로직 그대로, 디자인만 교체
5. ✅ `npm run build-only` 통과 (LoginView 128 kB, CSS 3.85 kB)

### 적용 사양
- 폰트: Asta Sans (Google Fonts, korean+latin, 300~700)
- 카드: `rgba(34,39,53,0.55)` + `backdrop-filter: blur(24px) saturate(180%)` + hairline 보더
- 배경: 슬레이트 그라데이션 + SVG 차트 라인 백드롭 3종 + 골드/슬레이트 글로우 블롭
- 액센트: 골드 그라데이션 `#F59E0B → #D97706`
- 모션: motion-v `<Motion>` 컴포넌트, 카드 entrance fade-up (0.6s, ease [0.16,1,0.3,1])
- 인풋: focus 시 골드 보더 + 3px glow ring
- 회원가입: 탭 폐기, 하단 토글 링크 (`toggleMode()`)
- `prefers-reduced-motion` 대응 / 480px 이하 반응형 패딩 축소

### 보존된 로직
- `mode` (login ↔ register)
- `form.username / email / password`
- `auth.login()` / `auth.register()` 호출
- `loading / error / success` 상태
- 회원가입 성공 시 로그인 모드로 자동 전환

### 검증해야 할 것 (브라우저)
- `npm run dev -- --host --port 3001` 후 `http://localhost:3001/login`
- glassmorphism blur가 실제로 깔리는지 (Firefox는 `backdrop-filter` 플래그 확인 필요할 수 있음)
- 입장 페이드가 자연스러운지
- input focus의 골드 보더 + glow ring
- 로그인 버튼 hover 시 `translateY(-1px)` + shadow 강화
- "회원가입" 링크 → 이메일 필드 노출 → 다시 "로그인" 토글
- 모바일 (375px) 카드 패딩 줄어드는지
- 실제 로그인 → `/dashboard` 라우팅
- 잘못된 비번 → 에러 메시지 박스 빨강
- WCAG: 본문 #F8FAFC on #0F172A ≈ 17:1, muted #94A3B8 ≈ 5.5:1, 골드 버튼 텍스트는 어두운 `#0F172A` 사용

### 결정 후 변경 사항 메모
- README의 결정 #5 "로그인 우선 + 회원가입 작게"를 그대로 구현: 탭 UI 폐기, 하단 단일 링크로 모드 토글
- glassmorphism 가독성 리스크 → 카드 안 input은 blur 없음(이중 blur 방지), 텍스트는 모두 명도 콘트라스트 보장 색만 사용

---

## v2 갈아엎기 (2026-05-23, 같은 날 오후)

v1(Slate Gold glassmorphism) 약했음. 레퍼런스 변경 → `https://matveyan.com/`.
브루털리스트 + 트레이딩 터미널 HUD 컨셉으로 전면 재설계.

### 새 컨셉
**Bloomberg/Linear 톤의 브루털 미니멀 + 라이브 데이터 오버레이.**
글래스 카드 폐기. 카드 자체가 없음 — 전면 풀블리드 다크에 정보가 직접 박힘.

### 사양
- 배경: `#050507` 풀블리드 + 라디얼 마스킹된 80px 그리드 (`rgba(255,255,255,0.018)`)
- 폰트: **Inter** (sans, hero·input) + **JetBrains Mono** (HUD·label·data) + Pretendard fallback (한글)
- 액센트: `#F59E0B` 골드 (CTA·focus·status)
- 시세 상승/하락: `#4ade80` / `#f87171`

### 레이어
1. **HUD 상단 바**: `AS / AUTOSTOCK / SYSTEM ONLINE ●` + KOSPI 미니 티커 5종(3.5s마다 랜덤 갱신) + `UTC+9 HH:MM:SS` (1초 틱)
2. **HUD 하단 바**: `CURSOR XXXX,YYYY` (마우스 추적 rAF 스로틀) + `STATE [LOGIN/REGISTER/PROCESSING/ERROR/SUCCESS]` + `LATENCY 0.0XXs` (2s 갱신)
3. **마우스 추적 스포트라이트**: 700px 골드 라디얼 글로우, 마우스 따라옴
4. **시그널 웨이브**: 화면 하단 14% 위치, SVG sine wave (period 144px × 20회), 골드 그라디언트, 스트로크 대시 6/5, drift 22s linear + pulse 5s ease
5. **메인**: eyebrow `[ ACCESS / 인증 ]` → 히어로 2줄 (`AI가 매매한다.` / `당신은 결과만 본다.`) clip-mask 슬라이드 리빌 → meta 줄 → 폼

### 모션
- motion-v `<Motion>`: 히어로 char-line 마스크 리빌 (overflow:hidden + y 110%→0%, 0.9s expo-out)
- 스태거: eyebrow 0.2s → hero1 0.35s → hero2 0.55s → meta 1.05s → field1 1.25s → field2 1.35s → actions 1.5s
- CTA: 골드 pill + skewX 셔이 스윕 (0.7s) + arrow translateX +4px
- input: bottom-border only, focus 시 골드 보더 + 1px shadow
- 무한 모션: status-dot pulse 2s, signal drift 22s, signal pulse 5s, ticker live update, time live update, cursor live, latency live
- `prefers-reduced-motion`: 무한 keyframe 전부 차단, 셔이·스포트라이트 비활성

### HUD 라이브 동작
| 요소 | 갱신 주기 | 데이터 |
|---|---|---|
| 시간 | 1s | 로컬 시각 HH:MM:SS |
| 시세 티커 | 3.5s | 5종 (-1.5%~+1.5% 무작위) |
| 커서 좌표 | rAF | `clientX,Y` 4자리 padStart |
| 레이턴시 | 2s | 0.000~0.040s 무작위 |
| 상태 | 즉시 | mode/loading/error/success 반영 |

### 보존된 로직
- `mode` / `form` / `submit()` / `auth.login` / `auth.register` / `loading·error·success`
- 회원가입 성공 시 로그인 모드 자동 전환 (`form.password` 초기화)

### 검증해야 할 것 (브라우저)
- `npm run dev -- --host --port 3001` 후 `http://localhost:3001/login`
- 히어로 2줄 슬라이드 리빌 — 마스크 잘리지 않고 한글 받침까지 보이는지
- 시그널 웨이브가 끊김 없이 무한 스크롤 (left:0 / 200% width / -50% translate)
- 마우스 추적 — 스포트라이트 + 하단 HUD `CURSOR` 좌표 동시 갱신
- 시세 티커 — 3.5초마다 색·값 갱신, KOSPI/KOSDAQ 등
- 시간 — 1초 정확히 tick
- 입력 focus — 밑줄 골드 + 1px shadow, 한글 받침 깨짐 없음
- 회원가입 토글 — `EMAIL / 이메일` 필드 등장 (slide-in 0.4s)
- ERR/OK 박스 — mono 태그 + 메시지
- 골드 CTA — 셔이 스윕 + arrow shift + hover lift
- 모바일 (≤900px): 티커 숨김 / ≤640px: brand-name·status 숨김 / ≤420px: STATE 숨김
- WCAG: `#FAFAFA` on `#050507` ≈ 18:1, muted `#71717a` ≈ 4.6:1 (AA 통과), 골드 버튼 `#050507` 텍스트 ≈ 12:1
- `prefers-reduced-motion` 확인 (브라우저 설정에서 활성화)

### 빌드 결과
- `npm run build-only` ✓ (LoginView 132 kB / CSS 9 kB)
- 빌드만 통과 — 실제 브라우저 렌더 사용자 직접 확인 필요

### 이전 시안 보존
- `mockups/C-slate-gold.vue` — v1 글래스카드. v2에선 사용 안 하나 비교용 보존.
