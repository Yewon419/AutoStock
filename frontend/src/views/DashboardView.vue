<template>
  <div class="dashboard">

    <!-- 헤더 -->
    <div class="dash-header">
      <div class="header-left">
        <div class="greeting">{{ greeting }}</div>
        <div class="date-str">{{ dateStr }}</div>
      </div>
      <div class="header-right">
        <span class="broker-pill" :class="brokerPillClass">
          <span class="pill-dot"></span>
          {{ brokerLabel }}
        </span>
        <button class="btn-emergency" @click="emergencyStop" :disabled="summary.running === 0">
          ⛔ 비상정지
        </button>
      </div>
    </div>

    <!-- AI 캔버스 히어로 -->
    <div class="hero-card" @click="$router.push('/canvas')">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <div class="hero-icon">✦</div>
        <div class="hero-text">
          <div class="hero-title">AI 캔버스</div>
          <div class="hero-desc">전략 설계부터 자동매매 적용까지 — AI와 함께 파이프라인을 구성하세요</div>
        </div>
        <div class="hero-arrow">→</div>
      </div>
      <div class="canvas-chips" v-if="canvasList.length" @click.stop>
        <div
          v-for="c in canvasList.slice(0, 4)"
          :key="c.id"
          class="canvas-chip"
          @click="goCanvas(c.id)"
        >{{ c.name }}</div>
      </div>
    </div>

    <!-- 요약 카드 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Mock 자산</div>
        <div class="stat-value blue">{{ fmtMoney(summary.mock_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.mock_pnl)">{{ fmtPnl(summary.mock_pnl) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Paper 자산</div>
        <div class="stat-value blue">{{ fmtMoney(summary.paper_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.paper_pnl)">{{ fmtPnl(summary.paper_pnl) }}</div>
      </div>
      <div class="stat-card stat-card-real">
        <div class="stat-label-real">실계좌 자산</div>
        <div class="stat-value gold">{{ fmtMoney(summary.real_assets) }}</div>
        <div class="stat-sub" :class="pnlClass(summary.real_pnl)">{{ fmtPnl(summary.real_pnl) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">오늘 손익</div>
        <div class="stat-value" :class="pnlClass(summary.daily_pnl)">{{ fmtPnl(summary.daily_pnl) }}</div>
      </div>
      <div class="stat-card stat-card-clickable" @click="openTodayTrades">
        <div class="stat-label">오늘 거래</div>
        <div class="stat-value blue">{{ summary.today_trades ?? 0 }}건</div>
        <div class="stat-hint">클릭하여 보기</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">실행 중 봇</div>
        <div class="stat-bots">
          <span class="bot-num green">{{ summary.running ?? 0 }}<small>실행</small></span>
          <span class="bot-num gray">{{ summary.stopped ?? 0 }}<small>정지</small></span>
          <span class="bot-num red" v-if="summary.error">{{ summary.error }}<small>오류</small></span>
        </div>
      </div>
    </div>

    <!-- 봇 현황 + 알림 -->
    <div class="bottom-grid">
      <!-- 봇 현황 -->
      <div class="panel">
        <div class="panel-header">
          <span>봇 현황</span>
          <RouterLink to="/bots" class="panel-link">전체 보기 →</RouterLink>
        </div>
        <div v-if="botSnapshots.length === 0" class="empty-panel">실행 중인 봇이 없습니다</div>
        <div v-else class="bot-list">
          <div
            v-for="b in botSnapshots"
            :key="b.id"
            class="bot-row"
            @click="$router.push(`/bots/${b.id}`)"
          >
            <div class="bot-row-left">
              <span class="bot-status-dot" :class="b.status.toLowerCase()"></span>
              <div>
                <div class="bot-row-name">{{ b.name }}</div>
                <div class="bot-row-meta">
                  <span class="mode-tag" :class="modeClass(b.mode)">{{ b.mode }}</span>
                  <span class="pos-tag">포지션 {{ b.position_count }}개</span>
                </div>
              </div>
            </div>
            <div class="bot-row-right">
              <div class="bot-row-assets">{{ fmtMoney(b.total_assets) }}</div>
              <div class="bot-row-pnl" :class="pnlClass(b.pnl)">{{ fmtPnl(b.pnl) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 알림 -->
      <div class="panel">
        <div class="panel-header">
          <span>최근 알림</span>
          <button class="panel-link" @click="clearAlerts">모두 지우기</button>
        </div>
        <div v-if="alerts.length === 0" class="empty-panel">알림이 없습니다</div>
        <div v-else class="alert-list">
          <div v-for="(a, i) in alerts" :key="a.timestamp || i" class="alert-item" :class="alertTypeClass(a.type)">
            <div class="alert-top">
              <span class="alert-type-badge">{{ a.type }}</span>
              <span class="alert-time">{{ fmtDatetime(a.timestamp) }}</span>
            </div>
            <div class="alert-bot">{{ a.bot_name }}</div>
            <div class="alert-msg">{{ a.message }}</div>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- 오늘 거래 모달 -->
  <Teleport to="body">
    <div v-if="showTradesModal" class="modal-backdrop" @click.self="showTradesModal = false">
      <div class="modal">
        <div class="modal-header">
          <span>오늘의 거래 내역</span>
          <button class="modal-close" @click="showTradesModal = false">✕</button>
        </div>
        <div v-if="todayTrades.length === 0" class="modal-empty">오늘 체결된 거래가 없습니다</div>
        <div v-else class="trade-table-wrap">
          <table class="trade-table">
            <thead>
              <tr>
                <th>시간</th>
                <th>봇</th>
                <th>모드</th>
                <th>종목</th>
                <th>구분</th>
                <th>수량</th>
                <th>단가</th>
                <th>손익</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in todayTrades" :key="t.id">
                <td class="td-time">{{ fmtTime(t.executed_at) }}</td>
                <td>{{ t.bot_name }}</td>
                <td><span class="mode-tag" :class="modeClass(t.bot_mode)">{{ t.bot_mode }}</span></td>
                <td class="td-ticker">{{ t.ticker }}</td>
                <td><span class="type-badge" :class="t.execution_type === 'BUY' ? 'type-buy' : 'type-sell'">{{ t.execution_type }}</span></td>
                <td class="td-num">{{ t.quantity }}주</td>
                <td class="td-num">{{ Number(t.price).toLocaleString('ko-KR') }}원</td>
                <td class="td-num" :class="t.profit_loss != null ? pnlClass(t.profit_loss) : ''">
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
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const summary = ref({ running: 0, stopped: 0, error: 0, total_assets: 0, total_pnl: 0, mock_assets: 0, mock_pnl: 0, paper_assets: 0, paper_pnl: 0, real_assets: 0, real_pnl: 0, daily_pnl: 0, today_trades: 0 })
const botSnapshots = ref([])
const alerts = ref([])
const brokerStatus = ref({ mode: 'mock', connected: null })
const canvasList = ref([])
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

async function fetchCanvasList() {
  try {
    const res = await fetch(`${API}/ai/canvases`, { headers: headers() })
    if (res.ok) canvasList.value = await res.json()
  } catch { /* ignore */ }
}

function goCanvas(canvasId) {
  localStorage.setItem('autostock-last-canvas', canvasId)
  router.push('/canvas')
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

function statusClass(s) {
  if (s === 'RUNNING') return 'badge-green'
  if (s === 'ERROR') return 'badge-red'
  return 'badge-gray'
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
  fetchCanvasList()
  refreshTimer = setInterval(fetchAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard { max-width: 1100px; display: flex; flex-direction: column; gap: 20px; }

/* 헤더 */
.dash-header {
  display: flex; justify-content: space-between; align-items: flex-start;
}
.greeting { font-size: 22px; font-weight: 700; color: #e5e7eb; }
.date-str { font-size: 13px; color: #6b7280; margin-top: 4px; }
.header-right { display: flex; align-items: center; gap: 10px; }

.broker-pill {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 600;
  border: 1px solid transparent;
}
.pill-dot { width: 6px; height: 6px; border-radius: 50%; }
.pill-green { background: rgba(16,185,129,.12); color: #10b981; border-color: rgba(16,185,129,.2); }
.pill-green .pill-dot { background: #10b981; box-shadow: 0 0 6px #10b981; }
.pill-red { background: rgba(239,68,68,.12); color: #ef4444; border-color: rgba(239,68,68,.2); }
.pill-red .pill-dot { background: #ef4444; }
.pill-gray { background: rgba(107,114,128,.12); color: #9ca3af; border-color: rgba(107,114,128,.2); }
.pill-gray .pill-dot { background: #6b7280; }

.btn-emergency {
  padding: 6px 14px; background: rgba(239,68,68,.12);
  border: 1px solid rgba(239,68,68,.25); border-radius: 7px;
  color: #ef4444; font-size: 12px; font-weight: 600; cursor: pointer;
}
.btn-emergency:hover { background: rgba(239,68,68,.22); }
.btn-emergency:disabled { opacity: 0.35; cursor: not-allowed; }

/* 히어로 */
.hero-card {
  position: relative; border-radius: 14px; overflow: hidden;
  border: 1px solid rgba(167,139,250,.25);
  background: linear-gradient(135deg, #1a1d27 0%, #1e1730 100%);
  cursor: pointer; transition: border-color .2s;
}
.hero-card:hover { border-color: rgba(167,139,250,.5); }
.hero-bg {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at top right, rgba(139,92,246,.12) 0%, transparent 60%);
  pointer-events: none;
}
.hero-content {
  position: relative; display: flex; align-items: center; gap: 18px;
  padding: 22px 24px 16px;
}
.hero-icon { font-size: 28px; color: #a78bfa; flex-shrink: 0; line-height: 1; }
.hero-title { font-size: 18px; font-weight: 700; color: #e5e7eb; margin-bottom: 4px; }
.hero-desc { font-size: 12px; color: #9ca3af; line-height: 1.5; }
.hero-text { flex: 1; }
.hero-arrow { font-size: 20px; color: #6b7280; flex-shrink: 0; }
.hero-card:hover .hero-arrow { color: #a78bfa; }

.canvas-chips {
  position: relative; display: flex; gap: 8px; padding: 0 24px 18px; flex-wrap: wrap;
}
.canvas-chip {
  padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 500;
  background: rgba(167,139,250,.1); border: 1px solid rgba(167,139,250,.2);
  color: #c4b5fd; cursor: pointer; transition: all .15s;
}
.canvas-chip:hover { background: rgba(167,139,250,.2); color: #e9d5ff; }

/* 요약 카드 */
.stats-row {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px;
}
.stat-card {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px;
  padding: 18px 16px; display: flex; flex-direction: column; gap: 8px;
}
.stat-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }
.stat-label-real { font-size: 11px; color: #f59e0b; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }
.stat-card-real { border-color: rgba(245,158,11,.25); background: linear-gradient(135deg, #1a1d27, #1c1a10); }
.stat-value { font-size: 20px; font-weight: 700; }
.stat-sub { font-size: 12px; font-weight: 500; margin-top: 2px; }
.blue { color: #4f9eff; }
.gold { color: #f59e0b; }
.profit { color: #ef4444; }
.loss { color: #10b981; }
.stat-bots { display: flex; gap: 10px; align-items: baseline; }
.bot-num { font-size: 18px; font-weight: 700; display: flex; align-items: baseline; gap: 3px; }
.bot-num small { font-size: 10px; font-weight: 400; }
.bot-num.green { color: #10b981; }
.bot-num.gray { color: #6b7280; }
.bot-num.red { color: #ef4444; }

/* 하단 그리드 */
.bottom-grid { display: grid; grid-template-columns: 3fr 2fr; gap: 18px; }

.panel {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 12px; overflow: hidden;
}
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid #2a2d3e;
  font-size: 13px; font-weight: 600; color: #e5e7eb;
}
.panel-link {
  font-size: 12px; color: #4f9eff; text-decoration: none;
  background: none; border: none; cursor: pointer; padding: 0;
}
.panel-link:hover { text-decoration: underline; }
.empty-panel { padding: 40px; text-align: center; color: #4b5563; font-size: 13px; }

/* 봇 리스트 */
.bot-list { display: flex; flex-direction: column; }
.bot-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 18px; border-bottom: 1px solid #1a1f2e;
  cursor: pointer; transition: background .12s;
}
.bot-row:last-child { border-bottom: none; }
.bot-row:hover { background: #1f2335; }
.bot-row-left { display: flex; align-items: center; gap: 10px; }
.bot-status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.bot-status-dot.running { background: #10b981; box-shadow: 0 0 6px #10b981; }
.bot-status-dot.stopped { background: #4b5563; }
.bot-status-dot.error { background: #ef4444; box-shadow: 0 0 6px #ef4444; }
.bot-row-name { font-size: 13px; font-weight: 500; color: #e5e7eb; margin-bottom: 3px; }
.bot-row-meta { display: flex; align-items: center; gap: 6px; }
.mode-tag {
  padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;
}
.mode-mock { background: rgba(79,158,255,.15); color: #4f9eff; }
.mode-paper { background: rgba(245,158,11,.15); color: #f59e0b; }
.mode-real { background: rgba(239,68,68,.15); color: #ef4444; }
.pos-tag { font-size: 11px; color: #6b7280; }
.bot-row-right { text-align: right; }
.bot-row-assets { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.bot-row-pnl { font-size: 12px; font-weight: 500; }

/* 클릭 카드 */
.stat-card-clickable { cursor: pointer; transition: border-color .15s, background .15s; }
.stat-card-clickable:hover { border-color: #4f9eff; background: #1e2535; }
.stat-hint { font-size: 10px; color: #4b5563; margin-top: 4px; }

/* 모달 */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center; z-index: 999;
}
.modal {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 14px;
  width: 860px; max-width: 95vw; max-height: 80vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #2a2d3e;
  font-size: 14px; font-weight: 600; color: #e5e7eb;
}
.modal-close {
  background: none; border: none; color: #6b7280;
  font-size: 16px; cursor: pointer; padding: 2px 6px; border-radius: 4px;
}
.modal-close:hover { color: #e5e7eb; background: #2a2d3e; }
.modal-empty { padding: 48px; text-align: center; color: #4b5563; font-size: 13px; }
.trade-table-wrap { overflow-y: auto; flex: 1; }
.trade-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
.trade-table th {
  position: sticky; top: 0; background: #1f2335;
  padding: 10px 14px; text-align: left; color: #6b7280;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  border-bottom: 1px solid #2a2d3e;
}
.trade-table td {
  padding: 10px 14px; border-bottom: 1px solid #1a1f2e; color: #d1d5db;
}
.trade-table tr:last-child td { border-bottom: none; }
.trade-table tr:hover td { background: #1f2335; }
.td-time { color: #6b7280; white-space: nowrap; }
.td-ticker { font-weight: 600; color: #e5e7eb; }
.td-num { text-align: right; font-variant-numeric: tabular-nums; }
.type-badge {
  padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700;
}
.type-buy { background: rgba(239,68,68,.15); color: #ef4444; }
.type-sell { background: rgba(16,185,129,.15); color: #10b981; }

/* 알림 */
.alert-list { display: flex; flex-direction: column; max-height: 360px; overflow-y: auto; }
.alert-item {
  padding: 11px 16px; border-bottom: 1px solid #1a1f2e;
  border-left: 3px solid #2a2d3e;
}
.alert-item:last-child { border-bottom: none; }
.alert-item.alert-error { border-left-color: #ef4444; }
.alert-item.alert-warn { border-left-color: #f59e0b; }
.alert-top { display: flex; justify-content: space-between; margin-bottom: 3px; }
.alert-type-badge { font-size: 10px; font-weight: 700; color: #ef4444; text-transform: uppercase; }
.alert-time { font-size: 10px; color: #4b5563; }
.alert-bot { font-size: 12px; color: #9ca3af; font-weight: 500; margin-bottom: 2px; }
.alert-msg { font-size: 11px; color: #6b7280; }
</style>
