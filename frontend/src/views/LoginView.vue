<template>
  <div ref="wrapRef" class="auth-wrap" @mousemove="onMouseMove">
    <div
      class="spotlight"
      aria-hidden="true"
      :style="{ '--mx': mx + 'px', '--my': my + 'px' }"
    ></div>

    <div class="floaters" aria-hidden="true">
      <div class="floater f1">
        <div class="floater-head">
          <span>KOSPI · 5D</span>
          <span class="dot up"></span>
        </div>
        <svg class="f-chart" viewBox="0 0 180 60" preserveAspectRatio="none">
          <defs>
            <linearGradient id="fFillG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4ade80" stop-opacity="0.35" />
              <stop offset="100%" stop-color="#4ade80" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,42 L20,38 L40,44 L60,32 L80,36 L100,24 L120,28 L140,16 L160,20 L180,8 L180,60 L0,60 Z"
            fill="url(#fFillG)"
          />
          <path
            d="M0,42 L20,38 L40,44 L60,32 L80,36 L100,24 L120,28 L140,16 L160,20 L180,8"
            fill="none"
            stroke="#4ade80"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
        <div class="floater-num up">+2.34%</div>
      </div>

      <div class="floater f2">
        <div class="floater-head">
          <span>SHARPE</span>
          <span class="dim">BOT 19</span>
        </div>
        <div class="gauge">
          <svg viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              stroke-width="6"
            />
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="#F59E0B"
              stroke-width="6"
              stroke-linecap="round"
              stroke-dasharray="264"
              stroke-dashoffset="58"
              transform="rotate(-90 50 50)"
            />
          </svg>
          <span class="gauge-val">0.78</span>
        </div>
      </div>

      <div class="floater f3">
        <div class="floater-head">
          <span>ORDERBOOK</span>
          <span class="dim">005930</span>
        </div>
        <div class="depth">
          <div class="depth-row ask">
            <span class="depth-bar" style="width: 38%"></span>
            <span class="depth-px">71,400</span>
          </div>
          <div class="depth-row ask">
            <span class="depth-bar" style="width: 62%"></span>
            <span class="depth-px">71,300</span>
          </div>
          <div class="depth-row bid">
            <span class="depth-bar" style="width: 84%"></span>
            <span class="depth-px">71,200</span>
          </div>
          <div class="depth-row bid">
            <span class="depth-bar" style="width: 46%"></span>
            <span class="depth-px">71,100</span>
          </div>
        </div>
      </div>
    </div>

    <svg
      class="signal"
      viewBox="0 0 2880 200"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="sigGold" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#F59E0B" stop-opacity="0" />
          <stop offset="20%" stop-color="#F59E0B" stop-opacity="0.5" />
          <stop offset="80%" stop-color="#F59E0B" stop-opacity="0.5" />
          <stop offset="100%" stop-color="#F59E0B" stop-opacity="0" />
        </linearGradient>
      </defs>
      <path
        class="signal-path"
        d="M0,100 Q72,40 144,100 T288,100 T432,100 T576,100 T720,100 T864,100 T1008,100 T1152,100 T1296,100 T1440,100 T1584,100 T1728,100 T1872,100 T2016,100 T2160,100 T2304,100 T2448,100 T2592,100 T2736,100 T2880,100"
        stroke="url(#sigGold)"
        stroke-width="1.2"
        fill="none"
      />
    </svg>

    <header class="hud hud-top">
      <div class="hud-cluster">
        <span class="brand-mark">AS</span>
        <span class="hud-sep">/</span>
        <span class="brand-name">AUTOSTOCK</span>
        <span class="hud-sep">/</span>
        <span class="status">
          <span class="status-dot"></span>
          SYSTEM ONLINE
        </span>
      </div>

      <div class="hud-cluster ticker">
        <span
          v-for="(t, i) in tickers"
          :key="t.sym + '-' + i"
          class="ticker-item"
        >
          <span class="ticker-sym">{{ t.sym }}</span>
          <span class="ticker-val" :class="t.dir">{{ t.val }}</span>
        </span>
      </div>

      <div class="hud-cluster">
        <span class="hud-label">UTC+9</span>
        <span class="hud-mono">{{ time }}</span>
      </div>
    </header>

    <main class="main">
      <Motion
        as="div"
        class="eyebrow"
        :initial="{ opacity: 0 }"
        :animate="{ opacity: 1 }"
        :transition="{ duration: 0.6, delay: 0.2 }"
      >
        [ ACCESS / 인증 ]
      </Motion>

      <h1 class="hero">
        <span class="hero-line">
          <Motion
            as="span"
            class="hero-text"
            :initial="{ y: '110%' }"
            :animate="{ y: '0%' }"
            :transition="{ duration: 0.9, delay: 0.35, ease: [0.16, 1, 0.3, 1] }"
          >
            AI가 매매한다.
          </Motion>
        </span>
        <span class="hero-line">
          <Motion
            as="span"
            class="hero-text muted"
            :initial="{ y: '110%' }"
            :animate="{ y: '0%' }"
            :transition="{ duration: 0.9, delay: 0.55, ease: [0.16, 1, 0.3, 1] }"
          >
            당신은 결과만 본다.
          </Motion>
        </span>
      </h1>

      <Motion
        as="div"
        class="meta"
        :initial="{ opacity: 0 }"
        :animate="{ opacity: 1 }"
        :transition="{ duration: 0.8, delay: 1.05 }"
      >
        <span>한국 주식</span>
        <span class="meta-sep">/</span>
        <span>AI 자동매매 운영체제</span>
        <span class="meta-sep">/</span>
        <span>v0.7</span>
      </Motion>

      <form @submit.prevent="submit" class="form" novalidate>
        <Motion
          as="div"
          class="field"
          :initial="{ opacity: 0, y: 16 }"
          :animate="{ opacity: 1, y: 0 }"
          :transition="{ duration: 0.6, delay: 1.25 }"
        >
          <label class="label" for="username">ID / 아이디</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            autocomplete="username"
            required
          />
        </Motion>

        <div v-if="mode === 'register'" class="field field-register">
          <label class="label" for="email">EMAIL / 이메일</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            autocomplete="email"
            required
          />
        </div>

        <Motion
          as="div"
          class="field"
          :initial="{ opacity: 0, y: 16 }"
          :animate="{ opacity: 1, y: 0 }"
          :transition="{ duration: 0.6, delay: 1.35 }"
        >
          <label class="label" for="password">PW / 비밀번호</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            required
          />
        </Motion>

        <p v-if="error" class="msg error" role="alert">
          <span class="msg-tag">ERR</span>
          <span>{{ error }}</span>
        </p>
        <p v-if="success" class="msg success">
          <span class="msg-tag ok">OK</span>
          <span>{{ success }}</span>
        </p>

        <Motion
          as="div"
          class="actions"
          :initial="{ opacity: 0, y: 16 }"
          :animate="{ opacity: 1, y: 0 }"
          :transition="{ duration: 0.6, delay: 1.5 }"
        >
          <button class="submit-btn" type="submit" :disabled="loading">
            <span class="btn-shine" aria-hidden="true"></span>
            <span class="btn-text">{{ btnLabel }}</span>
            <span class="btn-arrow" aria-hidden="true">→</span>
          </button>

          <button type="button" class="link-btn" @click="toggleMode">
            <span class="link-prefix">
              {{ mode === 'login' ? '계정이 없습니까?' : '이미 가입했습니까?' }}
            </span>
            <span class="link-action">
              {{ mode === 'login' ? '회원가입' : '로그인' }}
              <span aria-hidden="true">→</span>
            </span>
          </button>
        </Motion>
      </form>
    </main>

    <footer class="hud hud-bottom">
      <div class="hud-cluster">
        <span class="hud-label">CURSOR</span>
        <span class="hud-mono">{{ cxStr }} , {{ cyStr }}</span>
      </div>
      <div class="hud-cluster hud-bottom-center">
        <span class="hud-label">STATE</span>
        <span class="hud-mono" :class="stateClass">{{ stateLabel }}</span>
      </div>
      <div class="hud-cluster">
        <span class="hud-label">LATENCY</span>
        <span class="hud-mono">{{ latency }}</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Motion } from 'motion-v'

const router = useRouter()
const auth = useAuthStore()

const mode = ref('login')
const loading = ref(false)
const error = ref('')
const success = ref('')

const form = reactive({ username: '', email: '', password: '' })

const mx = ref(typeof window !== 'undefined' ? window.innerWidth / 2 : 0)
const my = ref(typeof window !== 'undefined' ? window.innerHeight / 2 : 0)
let rafPending = false
function onMouseMove(e) {
  if (rafPending) return
  rafPending = true
  requestAnimationFrame(() => {
    mx.value = e.clientX
    my.value = e.clientY
    rafPending = false
  })
}

const cxStr = computed(() => String(Math.round(mx.value)).padStart(4, '0'))
const cyStr = computed(() => String(Math.round(my.value)).padStart(4, '0'))

const time = ref('00:00:00')
let timeId = null
function tickTime() {
  const d = new Date()
  time.value = [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((n) => String(n).padStart(2, '0'))
    .join(':')
}

const tickers = ref([
  { sym: 'KOSPI', val: '+0.74%', dir: 'up' },
  { sym: 'KOSDAQ', val: '-0.21%', dir: 'down' },
  { sym: '005930', val: '+1.32%', dir: 'up' },
  { sym: '000660', val: '-0.45%', dir: 'down' },
  { sym: '035420', val: '+0.18%', dir: 'up' },
])
let tickerId = null
function refreshTickers() {
  tickers.value = tickers.value.map((t) => {
    const v = (Math.random() * 2 - 1) * 1.5
    const dir = v >= 0 ? 'up' : 'down'
    return {
      sym: t.sym,
      val: (v >= 0 ? '+' : '') + v.toFixed(2) + '%',
      dir,
    }
  })
}

const latency = ref('0.0s')
let latencyId = null
function refreshLatency() {
  const v = (Math.random() * 0.04).toFixed(3)
  latency.value = v + 's'
}

const stateLabel = computed(() => {
  if (loading.value) return 'PROCESSING'
  if (error.value) return 'ERROR'
  if (success.value) return 'SUCCESS'
  return mode.value === 'login' ? 'LOGIN' : 'REGISTER'
})
const stateClass = computed(() => {
  if (error.value) return 'state-error'
  if (success.value) return 'state-ok'
  if (loading.value) return 'state-busy'
  return ''
})

const btnLabel = computed(() => {
  if (loading.value) return 'PROCESSING'
  return mode.value === 'login' ? '로그인' : '회원가입'
})

onMounted(() => {
  tickTime()
  timeId = setInterval(tickTime, 1000)
  tickerId = setInterval(refreshTickers, 3500)
  latencyId = setInterval(refreshLatency, 2000)
})
onUnmounted(() => {
  if (timeId) clearInterval(timeId)
  if (tickerId) clearInterval(tickerId)
  if (latencyId) clearInterval(latencyId)
})

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
  success.value = ''
}

async function submit() {
  error.value = ''
  success.value = ''
  loading.value = true

  try {
    if (mode.value === 'login') {
      await auth.login(form.username, form.password)
      router.push('/dashboard')
    } else {
      await auth.register(form.username, form.email, form.password)
      success.value = '회원가입 완료. 로그인하세요.'
      mode.value = 'login'
      form.password = ''
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

* {
  box-sizing: border-box;
}

.auth-wrap {
  position: relative;
  height: 100vh;
  height: 100dvh;
  background: #050507;
  color: #fafafa;
  font-family:
    'Inter',
    'Pretendard',
    -apple-system,
    BlinkMacSystemFont,
    'Apple SD Gothic Neo',
    sans-serif;
  overflow: hidden;
  cursor: default;
}

.auth-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px);
  background-size: 80px 80px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(
    ellipse at center,
    black 30%,
    transparent 75%
  );
  pointer-events: none;
  z-index: 0;
}

.spotlight {
  position: fixed;
  pointer-events: none;
  width: 700px;
  height: 700px;
  border-radius: 50%;
  left: var(--mx);
  top: var(--my);
  transform: translate(-50%, -50%);
  background: radial-gradient(
    circle,
    rgba(245, 158, 11, 0.07) 0%,
    rgba(245, 158, 11, 0.025) 25%,
    transparent 65%
  );
  z-index: 1;
}

.floaters {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.floater {
  position: absolute;
  background: rgba(20, 24, 34, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.07),
    0 18px 44px -10px rgba(0, 0, 0, 0.6);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  color: #d4d4d8;
}

.floater::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.07) 0%,
    transparent 38%
  );
  pointer-events: none;
}

.floater-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #71717a;
  margin-bottom: 10px;
}

.floater-head .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.floater-head .dot.up {
  background: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.6);
}

.floater-head .dim {
  color: #52525b;
}

.floater-num {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-top: 6px;
}

.floater-num.up {
  color: #4ade80;
}

.f-chart {
  width: 100%;
  height: 48px;
}

.gauge {
  position: relative;
  width: 96px;
  height: 96px;
  margin: 2px auto 0;
}

.gauge svg {
  width: 100%;
  height: 100%;
}

.gauge-val {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  color: #fafafa;
  letter-spacing: -0.02em;
}

.depth {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.depth-row {
  position: relative;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  height: 18px;
  padding-right: 6px;
}

.depth-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-radius: 2px;
  opacity: 0.5;
}

.depth-row.ask .depth-bar {
  background: linear-gradient(
    90deg,
    transparent,
    rgba(248, 113, 113, 0.4)
  );
}

.depth-row.bid .depth-bar {
  background: linear-gradient(
    90deg,
    transparent,
    rgba(74, 222, 128, 0.4)
  );
}

.depth-px {
  position: relative;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #d4d4d8;
}

.depth-row.ask .depth-px {
  color: #fca5a5;
}

.depth-row.bid .depth-px {
  color: #86efac;
}

.f1 {
  top: 14vh;
  left: 4vw;
  width: 210px;
  animation: floatA 18s ease-in-out infinite;
}

.f2 {
  top: 22vh;
  right: 5vw;
  width: 150px;
  animation: floatB 24s ease-in-out infinite;
  animation-delay: -5s;
}

.f3 {
  bottom: 18vh;
  right: 7vw;
  width: 200px;
  animation: floatC 22s ease-in-out infinite;
  animation-delay: -9s;
}

@keyframes floatA {
  0%,
  100% {
    transform: rotate(-5deg) translate(0, 0);
  }
  50% {
    transform: rotate(-5deg) translate(18px, -22px);
  }
}

@keyframes floatB {
  0%,
  100% {
    transform: rotate(4deg) translate(0, 0);
  }
  50% {
    transform: rotate(4deg) translate(-14px, 20px);
  }
}

@keyframes floatC {
  0%,
  100% {
    transform: rotate(-2deg) translate(0, 0);
  }
  50% {
    transform: rotate(-2deg) translate(20px, -16px);
  }
}

.signal {
  position: absolute;
  bottom: 14%;
  left: 0;
  width: 200%;
  height: 220px;
  opacity: 0.55;
  z-index: 0;
  animation: signalDrift 22s linear infinite;
}

.signal-path {
  stroke-dasharray: 6 5;
  animation: signalPulse 5s ease-in-out infinite;
}

@keyframes signalDrift {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}

@keyframes signalPulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

.hud {
  position: fixed;
  left: 0;
  right: 0;
  padding: 18px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #a1a1aa;
  z-index: 10;
  pointer-events: none;
}

.hud-top {
  top: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.55), transparent);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
}

.hud-bottom {
  bottom: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  background: linear-gradient(0deg, rgba(0, 0, 0, 0.55), transparent);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
}

.hud-cluster {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.hud-bottom-center {
  flex: 1;
  justify-content: center;
}

.brand-mark {
  font-weight: 700;
  font-size: 10.5px;
  letter-spacing: 0.08em;
  background: rgba(245, 158, 11, 0.14);
  color: #f59e0b;
  padding: 3px 7px;
  border-radius: 3px;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.brand-name {
  font-weight: 600;
  color: #fafafa;
  letter-spacing: 0.12em;
}

.hud-sep {
  color: #3f3f46;
}

.status {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #d4d4d8;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.9);
  }
}

.ticker {
  gap: 18px;
}

.ticker-item {
  display: inline-flex;
  gap: 6px;
}

.ticker-sym {
  color: #71717a;
  font-weight: 500;
}

.ticker-val {
  font-weight: 600;
  transition: color 0.3s ease;
}

.ticker-val.up {
  color: #4ade80;
}

.ticker-val.down {
  color: #f87171;
}

.hud-label {
  color: #52525b;
}

.hud-mono {
  color: #fafafa;
  font-weight: 500;
}

.hud-mono.state-error {
  color: #f87171;
}
.hud-mono.state-ok {
  color: #4ade80;
}
.hud-mono.state-busy {
  color: #f59e0b;
}

.main {
  position: relative;
  z-index: 2;
  height: 100vh;
  height: 100dvh;
  padding: 84px 32px 76px;
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.eyebrow {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #f59e0b;
  margin-bottom: 18px;
}

.hero {
  font-size: clamp(34px, 5.2vw, 62px);
  font-weight: 700;
  line-height: 1.02;
  letter-spacing: -0.035em;
  margin: 0 0 22px;
  font-family:
    'Inter',
    'Pretendard',
    -apple-system,
    'Apple SD Gothic Neo',
    sans-serif;
}

.hero-line {
  display: block;
  overflow: hidden;
  padding-bottom: 0.14em;
}

.hero-text {
  display: inline-block;
}

.hero-text.muted {
  color: #52525b;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #71717a;
  margin-bottom: 36px;
}

.meta-sep {
  color: #3f3f46;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 460px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-register {
  animation: fieldIn 0.4s ease-out;
}

@keyframes fieldIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.label {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 10.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #71717a;
}

.field input {
  width: 100%;
  padding: 4px 0 8px;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  color: #fafafa;
  font-size: 17px;
  font-weight: 500;
  font-family: inherit;
  letter-spacing: -0.01em;
  outline: none;
  transition:
    border-color 0.3s ease,
    box-shadow 0.3s ease,
    color 0.2s ease;
}

.field input:hover {
  border-bottom-color: rgba(255, 255, 255, 0.28);
}

.field input:focus {
  border-bottom-color: #f59e0b;
  box-shadow: 0 1px 0 0 #f59e0b;
}

.field input::placeholder {
  color: #3f3f46;
}

.msg {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
  margin: 0;
  padding: 4px 0;
}

.msg.error {
  color: #fca5a5;
}

.msg.success {
  color: #86efac;
}

.msg-tag {
  display: inline-block;
  font-weight: 700;
  padding: 3px 7px;
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
  border-radius: 3px;
  font-size: 10px;
  letter-spacing: 0.12em;
}

.msg-tag.ok {
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
}

.actions {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-items: flex-start;
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 13px 24px;
  background: #f59e0b;
  color: #050507;
  border: none;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  letter-spacing: 0.02em;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition:
    transform 0.2s ease,
    background 0.2s ease,
    box-shadow 0.3s ease;
  box-shadow: 0 4px 24px -8px rgba(245, 158, 11, 0.5);
}

.btn-shine {
  position: absolute;
  top: 0;
  left: -120%;
  width: 60%;
  height: 100%;
  background: linear-gradient(
    100deg,
    transparent 30%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 70%
  );
  transform: skewX(-20deg);
  transition: left 0.7s ease;
  pointer-events: none;
}

.submit-btn:hover:not(:disabled) .btn-shine {
  left: 130%;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #fbbf24;
  box-shadow: 0 6px 32px -6px rgba(245, 158, 11, 0.65);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-text {
  position: relative;
  z-index: 1;
}

.btn-arrow {
  position: relative;
  z-index: 1;
  transition: transform 0.25s ease;
  font-size: 16px;
}

.submit-btn:hover:not(:disabled) .btn-arrow {
  transform: translateX(4px);
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-align: left;
  display: inline-flex;
  align-items: baseline;
  gap: 10px;
  color: #71717a;
}

.link-prefix {
  font-size: 13px;
}

.link-action {
  color: #f59e0b;
  font-weight: 600;
  position: relative;
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.link-action::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 1px;
  background: #f59e0b;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s ease;
}

.link-btn:hover .link-action::after {
  transform: scaleX(1);
}

@media (max-width: 1100px) {
  .f2 {
    display: none;
  }
}

@media (max-width: 900px) {
  .ticker {
    display: none;
  }
  .floaters {
    display: none;
  }
}

@media (max-width: 640px) {
  .hud {
    padding: 14px 18px;
    font-size: 10px;
  }
  .brand-name,
  .status {
    display: none;
  }
  .main {
    padding: 70px 22px 64px;
  }
  .meta {
    margin-bottom: 28px;
  }
  .form {
    gap: 16px;
  }
}

@media (max-width: 420px) {
  .hud-bottom .hud-bottom-center {
    display: none;
  }
}

/* Short viewports: laptops at 720p / split screens */
@media (max-height: 760px) {
  .eyebrow {
    margin-bottom: 12px;
  }
  .hero {
    font-size: clamp(28px, 4.4vw, 48px);
    margin-bottom: 16px;
  }
  .meta {
    margin-bottom: 22px;
  }
  .form {
    gap: 14px;
  }
  .field input {
    font-size: 16px;
    padding: 3px 0 7px;
  }
  .actions {
    gap: 14px;
  }
  .submit-btn {
    padding: 11px 22px;
  }
  .main {
    padding: 72px 32px 66px;
  }
}

@media (max-height: 620px) {
  .hero {
    font-size: clamp(24px, 4vw, 38px);
    margin-bottom: 12px;
  }
  .meta {
    display: none;
  }
  .form {
    gap: 12px;
  }
  .signal {
    opacity: 0.3;
  }
  .floaters {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .signal {
    animation: none;
    opacity: 0.3;
  }
  .signal-path {
    animation: none;
    opacity: 0.6;
  }
  .status-dot {
    animation: none;
  }
  .btn-shine {
    display: none;
  }
  .spotlight {
    display: none;
  }
  .floater {
    animation: none !important;
  }
}
</style>
