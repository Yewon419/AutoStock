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
          <span class="bot-name">{{ bot.name }}</span>
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
            <span class="stat-label">현재 캐시</span>
            <span class="stat-value">{{ fmtMoney(bot.cash) }}</span>
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

    <!-- 생성 모달 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2>봇 생성</h2>
          <button class="close-btn" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>봇 이름 *</label>
            <input v-model="form.name" type="text" placeholder="예: RSI 전략 봇" />
          </div>
          <div class="form-group">
            <label>거래 모드</label>
            <select v-model="form.mode">
              <option value="mock">Mock (가상 자금)</option>
              <option value="paper">Paper (키움 모의투자)</option>
              <option value="real">Real (키움 실계좌)</option>
            </select>
          </div>
          <div v-if="form.mode === 'real'" class="warning-box">
            ⚠️ 실계좌 모드입니다. 실제 주문이 체결됩니다.
          </div>
          <div class="form-group">
            <label>전략</label>
            <select v-model="form.strategy_id">
              <option :value="null">전략 선택 (선택사항)</option>
              <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>종목 (쉼표로 구분)</label>
            <input v-model="tickersInput" type="text" placeholder="예: 005930,000660,035720" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>초기 자금 (원)</label>
              <input v-model.number="form.initial_cash" type="number" min="100000" />
            </div>
            <div class="form-group">
              <label>포지션 크기 (%)</label>
              <input v-model.number="form.position_size_pct" type="number" min="1" max="100" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>손절 (%)</label>
              <input v-model.number="form.stop_loss_pct" type="number" min="0" step="0.5" />
            </div>
            <div class="form-group">
              <label>익절 (%)</label>
              <input v-model.number="form.take_profit_pct" type="number" min="0" step="0.5" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>최대 낙폭 (%)</label>
              <input v-model.number="form.max_drawdown_pct" type="number" min="0" step="0.5" />
            </div>
            <div class="form-group">
              <label>최대 동시 포지션</label>
              <input v-model.number="form.max_positions" type="number" min="1" max="20" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>일일 최대 거래 수</label>
              <input v-model.number="form.max_daily_trades" type="number" min="1" />
            </div>
            <div class="form-group">
              <label>단일 주문 최대 금액 (원)</label>
              <input v-model.number="form.max_order_amount" type="number" min="0" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>거래 시작 시간</label>
              <input v-model="form.trading_start_time" type="time" />
            </div>
            <div class="form-group">
              <label>거래 종료 시간</label>
              <input v-model="form.trading_end_time" type="time" />
            </div>
          </div>
          <p v-if="error" class="error-msg">{{ error }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeModal">취소</button>
          <button class="btn-primary" @click="submitCreate" :disabled="submitting">
            {{ submitting ? '생성 중...' : '생성' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const API = 'http://localhost:8001/api/v1'

const bots = ref([])
const strategies = ref([])
const loading = ref(false)
const showModal = ref(false)
const submitting = ref(false)
const error = ref('')
const tickersInput = ref('')

const defaultForm = () => ({
  name: '',
  mode: 'mock',
  strategy_id: null,
  tickers: [],
  initial_cash: 10000000,
  stop_loss_pct: 5.0,
  take_profit_pct: 10.0,
  max_drawdown_pct: 15.0,
  position_size_pct: 10.0,
  max_positions: 5,
  max_daily_trades: 20,
  max_order_amount: 1000000,
  trading_start_time: '09:00',
  trading_end_time: '15:20',
})
const form = ref(defaultForm())

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

async function fetchStrategies() {
  const res = await fetch(`${API}/strategies`, { headers: headers() })
  strategies.value = await res.json()
}

function openCreate() {
  form.value = defaultForm()
  tickersInput.value = ''
  error.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function submitCreate() {
  if (!form.value.name.trim()) { error.value = '봇 이름을 입력하세요'; return }
  error.value = ''
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      tickers: tickersInput.value.split(',').map(t => t.trim()).filter(Boolean),
    }
    const res = await fetch(`${API}/bots`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(payload),
    })
    if (!res.ok) { error.value = '생성 실패'; return }
    closeModal()
    fetchBots()
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
  fetchBots()
}

async function deleteBot(bot) {
  if (!confirm(`"${bot.name}" 봇을 삭제하시겠습니까?`)) return
  const res = await fetch(`${API}/bots/${bot.id}`, { method: 'DELETE', headers: headers() })
  if (res.ok) fetchBots()
  else alert('실행 중인 봇은 삭제할 수 없습니다')
}

function goDetail(id) {
  router.push(`/bots/${id}`)
}

const hasRunning = computed(() => bots.value.some(b => b.status === 'RUNNING'))

async function emergencyStop() {
  if (!confirm('모든 RUNNING 봇을 즉시 정지합니까?')) return
  const res = await fetch(`${API}/broker/emergency-stop`, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' } })
  const data = await res.json()
  alert(`${data.count}개 봇이 정지되었습니다`)
  fetchBots()
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

onMounted(() => {
  fetchBots()
  fetchStrategies()
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
  align-items: center;
  margin-bottom: 16px;
}

.bot-name { font-size: 16px; font-weight: 600; color: #e5e7eb; }

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
</style>
