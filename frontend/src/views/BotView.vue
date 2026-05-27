<template>
  <div class="bot-view">
    <header class="page-header">
      <div class="page-head-left">
        <span class="page-eyebrow">FLEET / 봇 운영</span>
        <h1 class="page-title">자동매매 봇</h1>
      </div>
      <div class="header-actions">
        <button
          class="btn-emergency"
          type="button"
          :disabled="!hasRunning"
          @click="emergencyStop"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polygon
              points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"
            />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>EMERGENCY STOP</span>
        </button>
        <button class="btn-primary" type="button" @click="openCreate">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>봇 생성</span>
        </button>
      </div>
    </header>

    <!-- 빈 상태 -->
    <div v-if="bots.length === 0 && !loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="4" y="6" width="16" height="14" rx="2" />
          <path d="M12 6V3" />
          <path d="M10 3h4" />
          <circle cx="9" cy="13" r="1" />
          <circle cx="15" cy="13" r="1" />
          <path d="M9 17h6" />
        </svg>
      </div>
      <p class="empty-title">생성된 봇이 없습니다</p>
      <p class="empty-desc">상단의 <strong>봇 생성</strong>으로 자동매매를 시작하세요.</p>
    </div>

    <!-- 봇 카드 그리드 -->
    <div v-else class="bot-grid">
      <article
        v-for="bot in bots"
        :key="bot.id"
        class="bot-card"
        @click="goDetail(bot.id)"
      >
        <header class="bot-card-header">
          <div class="bot-name-row">
            <span class="bot-name">{{ bot.name }}</span>
            <div class="bot-tags">
              <span v-if="bot.bot_type === 'scalping'" class="type-badge type-scalping">
                <span class="t-dot"></span>
                SCALPING
              </span>
              <span v-else class="type-badge type-swing">SWING</span>
              <span class="mode-badge" :class="modeClass(bot.mode)">{{ bot.mode }}</span>
            </div>
          </div>
          <span class="status-badge" :class="statusClass(bot.status)">
            <span class="s-dot"></span>
            {{ bot.status }}
          </span>
        </header>

        <div class="bot-stats">
          <div class="stat">
            <span class="stat-label">초기 자금</span>
            <span class="stat-value mono">{{ fmtMoney(bot.initial_cash) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">총자산</span>
            <span class="stat-value mono" :class="totalAssetsPnl(bot) >= 0 ? 'profit' : 'loss'">
              {{ fmtMoney(bot.total_assets ?? bot.cash) }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">예수금</span>
            <span class="stat-value mono">{{ fmtMoney(bot.cash) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">수익률</span>
            <span class="stat-value mono" :class="totalAssetsPnl(bot) >= 0 ? 'profit' : 'loss'">
              {{ totalAssetsPnl(bot) >= 0 ? '+' : '' }}{{ totalAssetsPnl(bot).toFixed(2) }}%
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">종목</span>
            <span class="stat-value mono">{{ (bot.tickers || []).length }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">손절 / 익절</span>
            <span class="stat-value mono">
              {{ bot.stop_loss_pct }}% / {{ bot.take_profit_pct }}%
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">오늘 손익</span>
            <span class="stat-value mono" :class="(bot.today_pnl ?? 0) >= 0 ? 'profit' : 'loss'">
              {{ fmtTodayPnl(bot) }}
            </span>
          </div>
        </div>

        <div v-if="(bot.tickers || []).length > 0" class="bot-tickers">
          <span
            v-for="t in (bot.tickers || []).slice(0, 6)"
            :key="t"
            class="ticker-tag"
          >{{ t }}</span>
          <span v-if="(bot.tickers || []).length > 6" class="ticker-more">
            +{{ (bot.tickers || []).length - 6 }}
          </span>
        </div>

        <div class="bot-actions" @click.stop>
          <button
            v-if="bot.status !== 'RUNNING'"
            class="btn-action btn-start"
            type="button"
            @click="startBot(bot)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <polygon points="6 4 20 12 6 20 6 4" />
            </svg>
            <span>START</span>
          </button>
          <button
            v-if="bot.status === 'RUNNING'"
            class="btn-action btn-stop"
            type="button"
            @click="stopBot(bot)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <rect x="6" y="6" width="12" height="12" rx="1.5" />
            </svg>
            <span>STOP</span>
          </button>
          <button
            v-if="bot.status !== 'RUNNING'"
            class="btn-action btn-delete"
            type="button"
            @click="deleteBot(bot)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" />
            </svg>
            <span>삭제</span>
          </button>
        </div>
      </article>
    </div>

    <!-- 생성 모달 -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal" role="dialog" aria-modal="true">
          <div class="modal-header">
            <div class="modal-head-text">
              <span class="modal-eyebrow">CREATE / 봇</span>
              <h2 class="modal-title">어떤 봇을 만들까요?</h2>
            </div>
            <button
              class="close-btn"
              type="button"
              aria-label="닫기"
              @click="closeModal"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <p class="create-hint">
              타입만 고르면 바로 생성됩니다. 전략·리스크는 봇 상세 페이지에서 설정합니다.
            </p>
            <div class="type-choice">
              <button
                class="type-choice-btn type-choice-swing"
                type="button"
                :disabled="submitting"
                @click="createBot('swing')"
              >
                <svg
                  class="tc-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <polyline points="3 17 9 11 13 15 21 7" />
                  <polyline points="14 7 21 7 21 14" />
                </svg>
                <span class="tc-title">스윙</span>
                <span class="tc-desc">일봉 기반 · 5분 주기</span>
              </button>
              <button
                class="type-choice-btn type-choice-scalping"
                type="button"
                :disabled="submitting"
                @click="createBot('scalping')"
              >
                <svg
                  class="tc-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
                <span class="tc-title">단타</span>
                <span class="tc-desc">분봉 기반 · 1분 주기</span>
              </button>
            </div>
            <p v-if="submitting" class="creating-msg">
              <span class="loader-dot"></span>
              <span>봇 생성 중...</span>
            </p>
            <p v-if="error" class="msg msg-fail">
              <span class="msg-tag">ERR</span>
              <span>{{ error }}</span>
            </p>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const bots = ref([])
const loading = ref(false)
const showModal = ref(false)
const submitting = ref(false)
const error = ref('')

const SWING_DEFAULTS = {
  stop_loss_pct: 5.0,
  take_profit_pct: 10.0,
  max_drawdown_pct: 15.0,
  max_daily_trades: 20,
  trading_end_time: '15:20',
}

const SCALPING_DEFAULTS = {
  stop_loss_pct: 2.0,
  take_profit_pct: 3.0,
  max_drawdown_pct: 10.0,
  max_daily_trades: 50,
  trading_end_time: '15:10',
  trailing_stop_pct: 2.0,
  confirm_bars: 2,
}

const defaultForm = () => ({
  name: '',
  mode: 'mock',
  strategy_id: null,
  tickers: [],
  initial_cash: 10000000,
  position_size_pct: 10.0,
  max_positions: 5,
  max_order_amount: 1000000,
  trading_start_time: '09:00',
  ...SWING_DEFAULTS,
  bot_type: 'swing',
  candle_interval: 1,
  intraday_close: false,
  intraday_close_time: '14:50',
  trailing_stop_pct: null,
  confirm_bars: 1,
})

function headers() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function fetchBots() {
  loading.value = true
  try {
    const res = await fetch(`${API}/bots`, { headers: headers() })
    bots.value = await res.json()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  error.value = ''
  showModal.value = true
}

function closeModal() {
  if (submitting.value) return
  showModal.value = false
}

function autoBotName(type) {
  const n = new Date()
  const p = (x) => String(x).padStart(2, '0')
  const stamp = `${p(n.getMonth() + 1)}/${p(n.getDate())} ${p(n.getHours())}:${p(n.getMinutes())}`
  return `${type === 'scalping' ? '단타' : '스윙'} 봇 ${stamp}`
}

async function createBot(type) {
  if (submitting.value) return
  error.value = ''
  submitting.value = true
  try {
    const payload = {
      ...defaultForm(),
      ...(type === 'scalping' ? SCALPING_DEFAULTS : SWING_DEFAULTS),
      bot_type: type,
      name: autoBotName(type),
      tickers: [],
    }
    const res = await fetch(`${API}/bots`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(payload),
    })
    if (!res.ok) { error.value = '생성 실패'; return }
    const newBot = await res.json()
    showModal.value = false
    router.push(`/bots/${newBot.id}`)
  } finally {
    submitting.value = false
  }
}

async function startBot(bot) {
  await fetch(`${API}/bots/${bot.id}/start`, { method: 'POST', headers: headers() })
  fetchBots()
}

async function stopBot(bot) {
  await fetch(`${API}/bots/${bot.id}/stop`, { method: 'POST', headers: headers() })
  await fetchBots()
}

async function deleteBot(bot) {
  if (bot.status === 'RUNNING') {
    if (!confirm(`"${bot.name}" 봇이 실행 중입니다.\n정지 후 삭제하시겠습니까?`)) return
    await fetch(`${API}/bots/${bot.id}/stop`, { method: 'POST', headers: headers() })
  } else {
    if (!confirm(`"${bot.name}" 봇을 삭제하시겠습니까?`)) return
  }
  const res = await fetch(`${API}/bots/${bot.id}`, { method: 'DELETE', headers: headers() })
  if (res.ok) await fetchBots()
  else alert('삭제 실패: 서버 오류가 발생했습니다')
}

function goDetail(id) {
  router.push(`/bots/${id}`)
}

const hasRunning = computed(() => bots.value.some(b => b.status === 'RUNNING'))

async function emergencyStop() {
  if (!confirm('모든 RUNNING 봇을 즉시 정지합니까?')) return
  try {
    const res = await fetch(`${API}/broker/emergency-stop`, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' } })
    if (!res.ok) { alert('비상정지 실패: 서버 오류'); return }
    const data = await res.json()
    alert(`${data.count}개 봇이 정지되었습니다`)
    fetchBots()
  } catch {
    alert('비상정지 실패: 네트워크 오류')
  }
}

function statusClass(status) {
  if (status === 'RUNNING') return 'badge-running'
  if (status === 'ERROR') return 'badge-error'
  return 'badge-stopped'
}

function modeClass(mode) {
  if (mode === 'real') return 'mode-real'
  if (mode === 'paper') return 'mode-paper'
  return 'mode-mock'
}

function fmtMoney(v) {
  if (!v) return '0원'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtTodayPnl(bot) {
  const pnl = bot.today_pnl ?? 0
  const pct = bot.today_pnl_pct ?? 0
  const sign = pnl >= 0 ? '+' : ''
  return `${sign}${Number(pnl).toLocaleString('ko-KR')}원 (${sign}${pct.toFixed(2)}%)`
}

function totalAssetsPnl(bot) {
  const initial = bot.initial_cash || 0
  const total = bot.total_assets ?? bot.cash ?? 0
  if (!initial) return 0
  return ((total / initial) - 1) * 100
}

let pollTimer = null

onMounted(async () => {
  await fetchBots()
  pollTimer = setInterval(fetchBots, 5000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>

<style scoped>
.bot-view {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ==========================================================================
   Page header
   ========================================================================== */

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.page-head-left {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--space-2);
}

.btn-emergency {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 9px var(--space-4);
  background: var(--profit-bg);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  color: var(--profit);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.btn-emergency svg {
  width: 14px;
  height: 14px;
}

.btn-emergency:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.45);
}

.btn-emergency:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 9px var(--space-4);
  background: var(--accent);
  color: var(--bg-base);
  border: none;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
  box-shadow: var(--shadow-gold);
}

.btn-primary svg {
  width: 14px;
  height: 14px;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==========================================================================
   Empty state
   ========================================================================== */

.empty-state {
  background: var(--surface-1);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  padding: var(--space-16) var(--space-5);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.empty-icon {
  color: var(--text-faint);
  margin-bottom: var(--space-3);
}

.empty-icon svg {
  width: 48px;
  height: 48px;
}

.empty-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.empty-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.empty-desc strong {
  font-family: var(--font-mono);
  color: var(--accent);
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

/* ==========================================================================
   Bot grid
   ========================================================================== */

.bot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-4);
}

.bot-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  transition:
    border-color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.bot-card:hover {
  border-color: var(--accent-border);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.bot-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
}

.bot-name-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.bot-name {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  word-break: keep-all;
}

.bot-tags {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  border: 1px solid;
}

.type-swing {
  background: rgba(96, 165, 250, 0.1);
  color: var(--info);
  border-color: rgba(96, 165, 250, 0.25);
}

.type-scalping {
  background: var(--accent-bg);
  color: var(--accent);
  border-color: var(--accent-border);
}

.type-scalping .t-dot {
  width: 5px;
  height: 5px;
  border-radius: var(--radius-full);
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent);
  animation: tDotPulse 1.4s ease-in-out infinite;
}

@keyframes tDotPulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.mode-badge {
  font-family: var(--font-mono);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.mode-mock {
  background: rgba(96, 165, 250, 0.14);
  color: var(--info);
}

.mode-paper {
  background: var(--accent-bg);
  color: var(--accent);
}

.mode-real {
  background: var(--profit-bg);
  color: var(--profit);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  padding: 4px 9px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  flex-shrink: 0;
}

.s-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
}

.badge-running {
  background: var(--up-bg);
  color: var(--up-strong);
}
.badge-running .s-dot {
  background: var(--up-strong);
  box-shadow: 0 0 6px var(--up-strong);
  animation: tDotPulse 2s ease-in-out infinite;
}

.badge-stopped {
  background: var(--surface-2);
  color: var(--text-muted);
}
.badge-stopped .s-dot {
  background: var(--text-muted);
}

.badge-error {
  background: var(--profit-bg);
  color: var(--profit);
}
.badge-error .s-dot {
  background: var(--profit);
  box-shadow: 0 0 6px var(--profit);
}

/* ==========================================================================
   Bot stats
   ========================================================================== */

.bot-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.stat-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.stat-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 600;
}

.stat-value.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--tracking-wide);
}

.profit {
  color: var(--profit);
}

.loss {
  color: var(--loss);
}

/* ==========================================================================
   Tickers
   ========================================================================== */

.bot-tickers {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.ticker-tag {
  font-family: var(--font-mono);
  background: var(--surface-2);
  color: var(--text-tertiary);
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  letter-spacing: var(--tracking-wide);
}

.ticker-more {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 11px;
  align-self: center;
  letter-spacing: var(--tracking-wide);
}

/* ==========================================================================
   Actions
   ========================================================================== */

.bot-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-faint);
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.btn-action svg {
  width: 12px;
  height: 12px;
}

.btn-start {
  color: var(--up-strong);
  border-color: rgba(34, 197, 94, 0.3);
}

.btn-start:hover {
  background: var(--up-bg);
}

.btn-stop {
  color: var(--profit);
  border-color: rgba(239, 68, 68, 0.3);
}

.btn-stop:hover {
  background: var(--profit-bg);
}

.btn-delete {
  margin-left: auto;
  color: var(--text-muted);
}

.btn-delete:hover {
  color: var(--profit);
  border-color: rgba(239, 68, 68, 0.3);
  background: var(--profit-bg);
}

/* ==========================================================================
   Create modal
   ========================================================================== */

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  animation: overlayIn var(--dur-base) var(--ease-out);
}

@keyframes overlayIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal {
  width: 480px;
  max-width: 92vw;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  animation: modalIn var(--dur-slow) var(--ease-out);
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.modal-head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.modal-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--accent);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.modal-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.close-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.close-btn svg {
  width: 14px;
  height: 14px;
}

.close-btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.modal-body {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.create-hint {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-snug);
}

.type-choice {
  display: flex;
  gap: var(--space-3);
}

.type-choice-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--space-5) var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.type-choice-swing:hover:not(:disabled) {
  border-color: var(--info);
  background: rgba(96, 165, 250, 0.05);
  transform: translateY(-2px);
}

.type-choice-scalping:hover:not(:disabled) {
  border-color: var(--accent);
  background: rgba(245, 158, 11, 0.05);
  transform: translateY(-2px);
}

.type-choice-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tc-icon {
  width: 28px;
  height: 28px;
  margin-bottom: var(--space-1);
}

.type-choice-swing .tc-icon {
  color: var(--info);
}

.type-choice-scalping .tc-icon {
  color: var(--accent);
}

.tc-title {
  font-size: var(--text-lg);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
}

.tc-desc {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.creating-msg {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.loader-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--accent);
  animation: loaderBlink 1s ease-in-out infinite;
}

@keyframes loaderBlink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.msg {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  border: 1px solid;
  margin: 0;
}

.msg-fail {
  background: var(--profit-bg);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--profit-soft);
}

.msg-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.08);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
  .header-actions {
    justify-content: space-between;
  }
  .bot-grid {
    grid-template-columns: 1fr;
  }
}
</style>
