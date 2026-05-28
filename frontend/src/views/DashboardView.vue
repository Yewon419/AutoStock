<template>
  <div class="dashboard">
    <!-- 헤더 -->
    <header class="dash-header">
      <div class="header-left">
        <h1 class="greeting">{{ greeting }}</h1>
        <p class="date-str">{{ dateStr }}</p>
      </div>
      <div class="header-right">
        <span class="broker-pill" :class="brokerPillClass">
          <span class="pill-dot"></span>
          {{ brokerLabel }}
        </span>
        <button
          class="btn-emergency"
          type="button"
          :disabled="summary.running === 0"
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
      </div>
    </header>

    <!-- 요약 카드 -->
    <section class="stats-row">
      <div class="stat-card">
        <div class="stat-label">MOCK 자산</div>
        <div class="stat-value">{{ fmtMoney(summary.mock_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.mock_pnl)">
          {{ fmtPnl(summary.mock_pnl) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">PAPER 자산</div>
        <div class="stat-value">{{ fmtMoney(summary.paper_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.paper_pnl)">
          {{ fmtPnl(summary.paper_pnl) }}
        </div>
      </div>
      <div class="stat-card stat-card-real">
        <div class="stat-label gold">REAL 실계좌</div>
        <div class="stat-value gold-num">{{ fmtMoney(summary.real_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.real_pnl)">
          {{ fmtPnl(summary.real_pnl) }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">오늘 손익</div>
        <div class="stat-value" :class="pnlClass(summary.daily_pnl)">
          {{ fmtPnl(summary.daily_pnl) }}
        </div>
        <div class="stat-split">
          <span :class="pnlClass(summary.daily_evaluation_pnl)">
            평가 {{ fmtPnl(summary.daily_evaluation_pnl) }}
          </span>
          <span class="split-sep">·</span>
          <span :class="pnlClass(summary.daily_realized_pnl)">
            실현 {{ fmtPnl(summary.daily_realized_pnl) }}
          </span>
        </div>
      </div>
      <div class="stat-card stat-card-clickable" @click="openTodayTrades">
        <div class="stat-label">오늘 거래</div>
        <div class="stat-value">{{ summary.today_trades ?? 0 }}<span class="unit">건</span></div>
        <div class="stat-hint">클릭 →</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">봇 상태</div>
        <div class="stat-bots">
          <span class="bot-num up">
            <span class="bot-num-val">{{ summary.running ?? 0 }}</span>
            <span class="bot-num-lbl">RUN</span>
          </span>
          <span class="bot-num dim">
            <span class="bot-num-val">{{ summary.stopped ?? 0 }}</span>
            <span class="bot-num-lbl">STOP</span>
          </span>
          <span v-if="summary.error" class="bot-num err">
            <span class="bot-num-val">{{ summary.error }}</span>
            <span class="bot-num-lbl">ERR</span>
          </span>
        </div>
      </div>
    </section>

    <!-- 봇 현황 + 알림 -->
    <section class="bottom-grid">
      <!-- 봇 현황 -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">봇 현황</span>
          <RouterLink to="/bots" class="panel-link">
            전체 보기
            <span aria-hidden="true">→</span>
          </RouterLink>
        </div>
        <div v-if="botSnapshots.length === 0" class="empty-panel">
          실행 중인 봇이 없습니다
        </div>
        <div v-else class="bot-list">
          <button
            v-for="b in botSnapshots"
            :key="b.id"
            class="bot-row"
            type="button"
            @click="$router.push(`/bots/${b.id}`)"
          >
            <div class="bot-row-left">
              <span class="bot-status-dot" :class="b.status.toLowerCase()"></span>
              <div class="bot-row-info">
                <div class="bot-row-name">{{ b.name }}</div>
                <div class="bot-row-meta">
                  <span class="mode-tag" :class="modeClass(b.mode)">{{ b.mode }}</span>
                  <span class="pos-tag">포지션 {{ b.position_count }}</span>
                </div>
              </div>
            </div>
            <div class="bot-row-right">
              <div class="bot-row-assets">{{ fmtMoney(b.total_assets) }}</div>
              <div class="bot-row-pnl" :class="pnlClass(b.pnl)">{{ fmtPnl(b.pnl) }}</div>
            </div>
          </button>
        </div>
      </div>

      <!-- 알림 -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">최근 알림</span>
          <button class="panel-link" type="button" @click="clearAlerts">모두 지우기</button>
        </div>
        <div v-if="alerts.length === 0" class="empty-panel">알림이 없습니다</div>
        <div v-else class="alert-list">
          <div
            v-for="(a, i) in alerts"
            :key="a.timestamp || i"
            class="alert-item"
            :class="alertTypeClass(a.type)"
          >
            <div class="alert-top">
              <span class="alert-type-badge">{{ a.type }}</span>
              <span class="alert-time">{{ fmtDatetime(a.timestamp) }}</span>
            </div>
            <div class="alert-bot">{{ a.bot_name }}</div>
            <div class="alert-msg">{{ a.message }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <!-- 오늘 거래 모달 -->
  <Teleport to="body">
    <div
      v-if="showTradesModal"
      class="modal-backdrop"
      @click.self="showTradesModal = false"
    >
      <div class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <span class="modal-title">오늘의 거래 내역</span>
          <button
            class="modal-close"
            type="button"
            aria-label="닫기"
            @click="showTradesModal = false"
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
        <div v-if="todayTrades.length === 0" class="modal-empty">
          오늘 체결된 거래가 없습니다
        </div>
        <div v-else class="trade-table-wrap">
          <table class="trade-table">
            <thead>
              <tr>
                <th>시간</th>
                <th>봇</th>
                <th>모드</th>
                <th>종목</th>
                <th>구분</th>
                <th class="th-num">수량</th>
                <th class="th-num">단가</th>
                <th class="th-num">손익</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in todayTrades" :key="t.id">
                <td class="td-time">{{ fmtTime(t.executed_at) }}</td>
                <td>{{ t.bot_name }}</td>
                <td>
                  <span class="mode-tag" :class="modeClass(t.bot_mode)">{{ t.bot_mode }}</span>
                </td>
                <td class="td-ticker"><StockLink :ticker="t.ticker" /></td>
                <td>
                  <span
                    class="type-badge"
                    :class="t.execution_type === 'BUY' ? 'type-buy' : 'type-sell'"
                  >{{ t.execution_type }}</span>
                </td>
                <td class="td-num">{{ t.quantity }}주</td>
                <td class="td-num">{{ Number(t.price).toLocaleString('ko-KR') }}원</td>
                <td
                  class="td-num"
                  :class="t.profit_loss != null ? pnlClass(t.profit_loss) : ''"
                >
                  {{ t.profit_loss != null ? fmtPnl(t.profit_loss) : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import StockLink from '@/components/StockLink.vue'

const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const summary = ref({ running: 0, stopped: 0, error: 0, total_assets: 0, total_pnl: 0, mock_assets: 0, mock_pnl: 0, paper_assets: 0, paper_pnl: 0, real_assets: 0, real_pnl: 0, daily_pnl: 0, daily_realized_pnl: 0, daily_evaluation_pnl: 0, today_trades: 0 })
const botSnapshots = ref([])
const alerts = ref([])
const brokerStatus = ref({ mode: 'mock', connected: null })
const showTradesModal = ref(false)
const todayTrades = ref([])

let refreshTimer = null

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

// 인사말
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6)  return '좋은 새벽입니다'
  if (h < 12) return '좋은 아침입니다'
  if (h < 18) return '좋은 오후입니다'
  return '좋은 저녁입니다'
})

const dateStr = computed(() => {
  return new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
})

const brokerLabel = computed(() => {
  const { mode, connected, kis_is_paper } = brokerStatus.value
  if (mode === 'real' || mode === 'paper') {
    if (connected) return kis_is_paper === false ? 'KIS 실계좌 연결됨' : 'KIS 모의 연결됨'
    return 'KIS 미연결'
  }
  return 'Mock 모드'
})

const brokerPillClass = computed(() => {
  const { mode, connected } = brokerStatus.value
  if (mode === 'real' || mode === 'paper') return connected ? 'pill-green' : 'pill-red'
  return 'pill-gray'
})

async function fetchAll() {
  try {
    const [s, b, br] = await Promise.all([
      fetch(`${API}/dashboard/summary`, { headers: headers() }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/dashboard/bots`, { headers: headers() }).then(r => r.ok ? r.json() : []),
      fetch(`${API}/broker/status`, { headers: headers() }).then(r => r.ok ? r.json() : {}),
    ])
    if (s) { summary.value = s; alerts.value = s.alerts || [] }
    if (b) botSnapshots.value = b
    if (br) brokerStatus.value = br
  } catch { /* ignore */ }
}

async function emergencyStop() {
  if (!confirm('모든 RUNNING 봇을 즉시 정지하시겠습니까?')) return
  try {
    const res = await fetch(`${API}/broker/emergency-stop`, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' } })
    if (!res.ok) { alert('비상정지 실패: 서버 오류'); return }
    const data = await res.json()
    alert(`${data.count}개 봇이 정지되었습니다`)
    fetchAll()
  } catch { alert('비상정지 실패: 네트워크 오류') }
}

async function openTodayTrades() {
  showTradesModal.value = true
  try {
    const res = await fetch(`${API}/dashboard/today-trades`, { headers: headers() })
    if (res.ok) todayTrades.value = await res.json()
  } catch { /* ignore */ }
}

async function clearAlerts() {
  await fetch(`${API}/broker/alerts`, { method: 'DELETE', headers: headers() })
  alerts.value = []
}

function modeClass(m) {
  if (m === 'real') return 'mode-real'
  if (m === 'paper') return 'mode-paper'
  return 'mode-mock'
}

function alertTypeClass(t) {
  if (t === 'ERROR') return 'alert-error'
  if (t === 'MAX_DRAWDOWN') return 'alert-warn'
  return ''
}

function pnlClass(v) {
  if (Number(v) > 0) return 'profit'
  if (Number(v) < 0) return 'loss'
  return ''
}

function fmtMoney(v) {
  if (!v && v !== 0) return '-'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtPnl(v) {
  if (v == null) return '-'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toLocaleString('ko-KR') + '원'
}

function fmtTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDatetime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  fetchAll()
  refreshTimer = setInterval(fetchAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ==========================================================================
   Header
   ========================================================================== */

.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.greeting {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  margin: 0;
}

.date-str {
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.broker-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-3);
  border-radius: var(--radius-full);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  border: 1px solid transparent;
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
}

.pill-green {
  background: var(--up-bg);
  color: var(--up-strong);
  border-color: rgba(34, 197, 94, 0.25);
}
.pill-green .pill-dot {
  background: var(--up-strong);
  box-shadow: 0 0 6px var(--up-strong);
}

.pill-red {
  background: var(--profit-bg);
  color: var(--profit);
  border-color: rgba(239, 68, 68, 0.25);
}
.pill-red .pill-dot {
  background: var(--profit);
}

.pill-gray {
  background: var(--surface-2);
  color: var(--text-muted);
  border-color: var(--border);
}
.pill-gray .pill-dot {
  background: var(--text-muted);
}

.btn-emergency {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  background: var(--profit-bg);
  border: 1px solid rgba(239, 68, 68, 0.28);
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
    border-color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.btn-emergency svg {
  width: 14px;
  height: 14px;
}

.btn-emergency:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.45);
}

.btn-emergency:active:not(:disabled) {
  transform: translateY(1px);
}

.btn-emergency:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* ==========================================================================
   Stats row
   ========================================================================== */

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.stat-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  transition: border-color var(--dur-fast) var(--ease-out);
}

.stat-card-real {
  border-color: var(--accent-border);
  background: linear-gradient(
    135deg,
    var(--surface-1) 0%,
    rgba(245, 158, 11, 0.05) 100%
  );
}

.stat-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  font-weight: 500;
}

.stat-label.gold {
  color: var(--accent);
  font-weight: 600;
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
  margin-top: var(--space-1);
}

.stat-value.gold-num {
  color: var(--accent);
}

.stat-value .unit {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-muted);
  margin-left: 3px;
}

.stat-sub {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
}

.stat-split {
  display: flex;
  gap: 6px;
  align-items: baseline;
  font-family: var(--font-mono);
  font-size: 10px;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  flex-wrap: wrap;
}

.split-sep {
  color: var(--text-faint);
}

.profit {
  color: var(--profit);
}

.loss {
  color: var(--loss);
}

.stat-bots {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  margin-top: 2px;
}

.bot-num {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-1);
  font-variant-numeric: tabular-nums;
}

.bot-num-val {
  font-size: var(--text-xl);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
}

.bot-num-lbl {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  color: var(--text-faint);
}

.bot-num.up .bot-num-val {
  color: var(--up-strong);
}

.bot-num.dim .bot-num-val {
  color: var(--text-muted);
}

.bot-num.err .bot-num-val {
  color: var(--profit);
}

.stat-card-clickable {
  cursor: pointer;
}

.stat-card-clickable:hover {
  border-color: var(--accent-border);
}

.stat-card-clickable:hover .stat-hint {
  color: var(--accent);
}

.stat-hint {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-top: 2px;
  transition: color var(--dur-fast) var(--ease-out);
}

/* ==========================================================================
   Bottom grid (bots + alerts)
   ========================================================================== */

.bottom-grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--space-5);
}

.panel {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.panel-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-secondary);
}

.panel-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--accent);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-decoration: none;
  transition: color var(--dur-fast) var(--ease-out);
}

.panel-link:hover {
  color: var(--accent-hover);
}

.empty-panel {
  padding: var(--space-12) var(--space-5);
  text-align: center;
  color: var(--text-faint);
  font-size: var(--text-sm);
}

/* ==========================================================================
   Bot list
   ========================================================================== */

.bot-list {
  display: flex;
  flex-direction: column;
}

.bot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: var(--space-3) var(--space-5);
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border-faint);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.bot-row:last-child {
  border-bottom: none;
}

.bot-row:hover {
  background: var(--surface-2);
}

.bot-row-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.bot-status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.bot-status-dot.running {
  background: var(--up-strong);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.6);
}

.bot-status-dot.stopped {
  background: var(--text-faint);
}

.bot-status-dot.error {
  background: var(--profit);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
}

.bot-row-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.bot-row-name {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-primary);
}

.bot-row-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.mode-tag {
  font-family: var(--font-mono);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
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

.pos-tag {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.bot-row-right {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.bot-row-assets {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.bot-row-pnl {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  margin-top: 2px;
}

/* ==========================================================================
   Alerts
   ========================================================================== */

.alert-list {
  display: flex;
  flex-direction: column;
  max-height: 360px;
  overflow-y: auto;
}

.alert-item {
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  border-left: 3px solid var(--border);
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-item.alert-error {
  border-left-color: var(--profit);
}

.alert-item.alert-warn {
  border-left-color: var(--accent);
}

.alert-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.alert-type-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--profit);
}

.alert-item.alert-warn .alert-type-badge {
  color: var(--accent);
}

.alert-time {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-faint);
  letter-spacing: var(--tracking-wide);
}

.alert-bot {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 2px;
}

.alert-msg {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-snug);
}

/* ==========================================================================
   Modal
   ========================================================================== */

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  animation: backdropFade var(--dur-base) var(--ease-out);
}

@keyframes backdropFade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  width: 920px;
  max-width: 95vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
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
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.modal-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-secondary);
}

.modal-close {
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

.modal-close svg {
  width: 14px;
  height: 14px;
}

.modal-close:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.modal-empty {
  padding: var(--space-16) var(--space-5);
  text-align: center;
  color: var(--text-faint);
  font-size: var(--text-sm);
}

.trade-table-wrap {
  overflow-y: auto;
  flex: 1;
}

.trade-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.trade-table th {
  position: sticky;
  top: 0;
  background: var(--surface-2);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}

.trade-table th.th-num {
  text-align: right;
}

.trade-table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  color: var(--text-secondary);
}

.trade-table tr:last-child td {
  border-bottom: none;
}

.trade-table tbody tr:hover td {
  background: var(--surface-1);
}

.td-time {
  font-family: var(--font-mono);
  color: var(--text-muted);
  white-space: nowrap;
}

.td-ticker {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
}

.td-num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.type-badge {
  font-family: var(--font-mono);
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

.type-buy {
  background: var(--profit-bg);
  color: var(--profit);
}

.type-sell {
  background: var(--up-bg);
  color: var(--up-strong);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 900px) {
  .bottom-grid {
    grid-template-columns: 1fr;
  }
  .dash-header {
    flex-direction: column;
    align-items: stretch;
  }
  .header-right {
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .greeting {
    font-size: var(--text-2xl);
  }
}
</style>
