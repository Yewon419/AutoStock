<template>
  <div class="bot-view">
    <div class="page-header">
      <h1>자동매매 봇</h1>
      <div class="header-actions">
        <button class="btn-emergency" @click="emergencyStop" :disabled="!hasRunning">⛔ 비상정지</button>
        <button class="btn-primary" @click="openCreate">+ 봇 생성</button>
      </div>
    </div>

    <!-- 봇 카드 목록 -->
    <div v-if="bots.length === 0 && !loading" class="empty-state">
      <p>생성된 봇이 없습니다. 봇을 생성하여 자동매매를 시작하세요.</p>
    </div>

    <div class="bot-grid">
      <div
        v-for="bot in bots"
        :key="bot.id"
        class="bot-card"
        @click="goDetail(bot.id)"
      >
        <div class="bot-card-header">
          <div class="bot-name-row">
            <span class="bot-name">{{ bot.name }}</span>
            <span v-if="bot.bot_type === 'scalping'" class="type-badge type-scalping">⚡ SCALPING</span>
          </div>
          <div class="badges">
            <span class="mode-badge" :class="modeClass(bot.mode)">{{ bot.mode }}</span>
            <span class="badge" :class="statusClass(bot.status)">{{ bot.status }}</span>
          </div>
        </div>
        <div class="bot-stats">
          <div class="stat">
            <span class="stat-label">초기 자금</span>
            <span class="stat-value">{{ fmtMoney(bot.initial_cash) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">총자산</span>
            <span class="stat-value" :class="totalAssetsPnl(bot) >= 0 ? 'profit' : 'loss'">
              {{ fmtMoney(bot.total_assets ?? bot.cash) }}
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">예수금</span>
            <span class="stat-value">{{ fmtMoney(bot.cash) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">수익률</span>
            <span class="stat-value" :class="totalAssetsPnl(bot) >= 0 ? 'profit' : 'loss'">
              {{ totalAssetsPnl(bot) >= 0 ? '+' : '' }}{{ totalAssetsPnl(bot).toFixed(2) }}%
            </span>
          </div>
          <div class="stat">
            <span class="stat-label">종목 수</span>
            <span class="stat-value">{{ (bot.tickers || []).length }}개</span>
          </div>
          <div class="stat">
            <span class="stat-label">손절 / 익절</span>
            <span class="stat-value">{{ bot.stop_loss_pct }}% / {{ bot.take_profit_pct }}%</span>
          </div>
        </div>
        <div class="bot-tickers">
          <span v-for="t in (bot.tickers || []).slice(0, 4)" :key="t" class="ticker-tag">{{ t }}</span>
          <span v-if="(bot.tickers || []).length > 4" class="ticker-more">+{{ (bot.tickers || []).length - 4 }}</span>
        </div>
        <div class="bot-actions" @click.stop>
          <button
            v-if="bot.status !== 'RUNNING'"
            class="btn-start"
            @click="startBot(bot)"
          >▶ 시작</button>
          <button
            v-if="bot.status === 'RUNNING'"
            class="btn-stop"
            @click="stopBot(bot)"
          >⏹ 정지</button>
          <button
            v-if="bot.status !== 'RUNNING'"
            class="btn-danger"
            @click="deleteBot(bot)"
          >삭제</button>
        </div>
      </div>
    </div>

    <!-- 생성 모달 (타입만 선택 → 즉시 생성) -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal modal-compact">
        <div class="modal-header">
          <h2>어떤 봇을 만들까요?</h2>
          <button class="close-btn" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <p class="create-hint">타입만 고르면 바로 생성됩니다. 전략·리스크는 봇 페이지에서 설정해요.</p>
          <div class="type-choice">
            <button class="type-choice-btn" :disabled="submitting" @click="createBot('swing')">
              <span class="tc-emoji">📈</span>
              <span class="tc-title">스윙</span>
              <span class="tc-desc">일봉 기반 · 5분 주기</span>
            </button>
            <button class="type-choice-btn" :disabled="submitting" @click="createBot('scalping')">
              <span class="tc-emoji">⚡</span>
              <span class="tc-title">단타</span>
              <span class="tc-desc">분봉 기반 · 1분 주기</span>
            </button>
          </div>
          <p v-if="submitting" class="creating-msg">생성 중…</p>
          <p v-if="error" class="error-msg">{{ error }}</p>
        </div>
      </div>
    </div>
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
  // 스윙 기본값
  ...SWING_DEFAULTS,
  // 단타 설정
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
    router.push(`/bots/${newBot.id}`)  // 캔버스 탭에서 전략·리스크 설정
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
  if (status === 'RUNNING') return 'badge-green'
  if (status === 'ERROR') return 'badge-red'
  return 'badge-gray'
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

function totalAssetsPnl(bot) {
  const initial = bot.initial_cash || 0
  const total = bot.total_assets ?? bot.cash ?? 0
  if (!initial) return 0
  return ((total / initial) - 1) * 100
}

let pollTimer = null

onMounted(async () => {
  await fetchBots()
  // 5초마다 봇 상태 갱신 (다른 탭에서 시작/정지 반영)
  pollTimer = setInterval(fetchBots, 5000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>

<style scoped>
.bot-view { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.header-actions { display: flex; gap: 10px; }

.btn-emergency {
  padding: 8px 16px;
  background: rgba(239,68,68,.15);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: 6px;
  color: #ef4444;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-emergency:hover { background: rgba(239,68,68,.25); }
.btn-emergency:disabled { opacity: 0.4; cursor: not-allowed; }

.page-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: #e5e7eb;
  margin: 0;
}

.empty-state {
  text-align: center;
  color: #6b7280;
  padding: 80px 0;
  font-size: 15px;
}

.bot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.bot-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.bot-card:hover { border-color: #4f9eff; }

.bot-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.bot-name-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bot-name { font-size: 16px; font-weight: 600; color: #e5e7eb; }

.type-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.type-scalping {
  background: rgba(251,191,36,.15);
  color: #fbbf24;
  border: 1px solid rgba(251,191,36,.25);
}

.badges { display: flex; gap: 6px; align-items: center; }

.mode-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}
.mode-mock { background: rgba(79,158,255,.15); color: #4f9eff; }
.mode-paper { background: rgba(245,158,11,.15); color: #f59e0b; }
.mode-real { background: rgba(239,68,68,.15); color: #ef4444; }

.warning-box {
  background: rgba(239,68,68,.08);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  color: #ef4444;
}

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green { background: rgba(16,185,129,.2); color: #10b981; }
.badge-red { background: rgba(239,68,68,.2); color: #ef4444; }
.badge-gray { background: rgba(107,114,128,.2); color: #9ca3af; }

.bot-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}

.stat { display: flex; flex-direction: column; gap: 2px; }
.stat-label { font-size: 11px; color: #6b7280; }
.stat-value { font-size: 13px; color: #e5e7eb; font-weight: 500; }

.bot-tickers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
  min-height: 24px;
}

.ticker-tag {
  background: #2a2d3e;
  color: #9ca3af;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.ticker-more { color: #6b7280; font-size: 12px; align-self: center; }

.bot-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid #2a2d3e;
  padding-top: 14px;
}

.btn-start, .btn-stop, .btn-danger {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}
.btn-start { background: rgba(16,185,129,.2); color: #10b981; }
.btn-start:hover { background: rgba(16,185,129,.3); }
.btn-stop { background: rgba(239,68,68,.2); color: #ef4444; }
.btn-stop:hover { background: rgba(239,68,68,.3); }
.btn-danger { background: rgba(107,114,128,.15); color: #9ca3af; margin-left: auto; }
.btn-danger:hover { background: rgba(239,68,68,.2); color: #ef4444; }

/* 봇 타입 탭 */
.bot-type-tabs {
  display: flex;
  border-bottom: 1px solid #2a2d3e;
}

.type-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 12px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #6b7280;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: -1px;
}

.type-tab:hover { color: #9ca3af; background: rgba(255,255,255,.03); }

.type-tab.active {
  color: #e5e7eb;
  border-bottom-color: #4f9eff;
}

.type-tab.active:last-child {
  border-bottom-color: #fbbf24;
  color: #fbbf24;
}

.tab-desc {
  font-size: 11px;
  font-weight: 400;
  color: #4b5563;
}

.type-tab.active .tab-desc { color: #6b7280; }

/* 단타 설정 섹션 */
.scalping-section {
  background: rgba(251,191,36,.05);
  border: 1px solid rgba(251,191,36,.2);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  color: #fbbf24;
  letter-spacing: 0.05em;
}

.intraday-close-group { justify-content: flex-start; }

.toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.toggle-slider {
  position: absolute;
  inset: 0;
  background: #2a2d3e;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 14px; height: 14px;
  left: 3px; top: 3px;
  background: #6b7280;
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}

.toggle-switch input:checked + .toggle-slider { background: rgba(251,191,36,.2); }
.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(16px);
  background: #fbbf24;
}

.time-inline {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  padding: 5px 8px;
  font-size: 13px;
  width: 100px;
}
.time-inline:focus { outline: none; border-color: #fbbf24; }

.toggle-off-label { font-size: 12px; color: #4b5563; }
.label-hint { font-size: 10px; color: #4b5563; font-weight: 400; }

/* 모달 */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}

.modal {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  width: 560px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #2a2d3e;
}

.modal-header h2 { margin: 0; font-size: 17px; color: #e5e7eb; }

.close-btn {
  background: none; border: none; color: #6b7280; font-size: 18px; cursor: pointer;
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid #2a2d3e;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.form-group label { font-size: 12px; color: #9ca3af; }

.form-group input,
.form-group select {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  padding: 8px 10px;
  font-size: 14px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #4f9eff;
}

.form-row {
  display: flex;
  gap: 12px;
}

.error-msg { color: #ef4444; font-size: 13px; }

.modal-compact { width: 420px; }

.create-hint { margin: 0; font-size: 13px; color: #9ca3af; line-height: 1.5; }

.type-choice { display: flex; gap: 12px; }

.type-choice-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 12px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  color: #e5e7eb;
  cursor: pointer;
  transition: border-color .12s, background .12s;
}

.type-choice-btn:hover:not(:disabled) {
  border-color: #4f9eff;
  background: rgba(79,158,255,.08);
}

.type-choice-btn:disabled { opacity: .5; cursor: not-allowed; }

.tc-emoji { font-size: 26px; }
.tc-title { font-size: 15px; font-weight: 700; }
.tc-desc { font-size: 11px; color: #6b7280; }

.creating-msg { margin: 0; font-size: 13px; color: #9ca3af; text-align: center; }

.btn-primary {
  background: #4f9eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:hover { background: #3b8ae8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  padding: 8px 18px;
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary:hover { border-color: #4b5563; color: #e5e7eb; }
.profit { color: #ef4444; }
.loss { color: #60a5fa; }
</style>
