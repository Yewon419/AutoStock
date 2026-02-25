<template>
  <div class="dashboard">
    <div class="dash-header">
      <h1>대시보드</h1>
      <div class="header-right">
        <span class="broker-pill" :class="brokerPillClass()">
          {{ brokerLabel() }}
        </span>
        <button class="btn-emergency" @click="emergencyStop" :disabled="summary.running === 0">
          ⛔ 비상정지
        </button>
      </div>
    </div>

    <!-- 요약 카드 -->
    <div class="summary-grid">
      <div class="s-card">
        <span class="s-label">총 자산</span>
        <span class="s-value blue">{{ fmtMoney(summary.total_assets) }}</span>
      </div>
      <div class="s-card">
        <span class="s-label">누적 손익</span>
        <span class="s-value" :class="pnlClass(summary.total_pnl)">{{ fmtPnl(summary.total_pnl) }}</span>
      </div>
      <div class="s-card">
        <span class="s-label">오늘 손익</span>
        <span class="s-value" :class="pnlClass(summary.daily_pnl)">{{ fmtPnl(summary.daily_pnl) }}</span>
      </div>
      <div class="s-card">
        <span class="s-label">오늘 거래 수</span>
        <span class="s-value blue">{{ summary.today_trades ?? 0 }}건</span>
      </div>
      <div class="s-card status-card">
        <span class="s-label">봇 상태</span>
        <div class="status-row">
          <span class="status-num green">{{ summary.running ?? 0 }} <small>실행</small></span>
          <span class="status-num gray">{{ summary.stopped ?? 0 }} <small>정지</small></span>
          <span class="status-num red">{{ summary.error ?? 0 }} <small>오류</small></span>
        </div>
      </div>
      <div class="s-card">
        <span class="s-label">수집 종목</span>
        <span class="s-value blue">{{ stockCount ?? '-' }}개</span>
      </div>
    </div>

    <!-- 봇 목록 + 알림 -->
    <div class="bottom-grid">
      <!-- 봇 현황 -->
      <div class="panel">
        <div class="panel-header">
          <span>봇 현황</span>
          <RouterLink to="/bots" class="panel-link">전체 보기 →</RouterLink>
        </div>
        <div v-if="botSnapshots.length === 0" class="empty-panel">봇이 없습니다</div>
        <table v-else class="mini-table">
          <thead>
            <tr>
              <th>봇명</th>
              <th>모드</th>
              <th>상태</th>
              <th>총 자산</th>
              <th>손익</th>
              <th>포지션</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="b in botSnapshots"
              :key="b.id"
              class="clickable"
              @click="$router.push(`/bots/${b.id}`)"
            >
              <td class="bot-name-cell">{{ b.name }}</td>
              <td><span class="mode-badge" :class="modeClass(b.mode)">{{ b.mode }}</span></td>
              <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
              <td>{{ fmtMoney(b.total_assets) }}</td>
              <td :class="pnlClass(b.pnl)">{{ fmtPnl(b.pnl) }}</td>
              <td>{{ b.position_count }}개</td>
            </tr>
          </tbody>
        </table>
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
              <span class="alert-type">{{ a.type }}</span>
              <span class="alert-time">{{ fmtDatetime(a.timestamp) }}</span>
            </div>
            <div class="alert-bot">{{ a.bot_name }}</div>
            <div class="alert-msg">{{ a.message }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API = 'http://localhost:8001/api/v1'

const summary = ref({ bot_count: 0, running: 0, stopped: 0, error: 0, total_assets: 0, total_pnl: 0, daily_pnl: 0, today_trades: 0, alerts: [] })
const botSnapshots = ref([])
const alerts = ref([])
const stockCount = ref(null)
const brokerStatus = ref({ mode: 'mock', connected: null })

let refreshTimer = null

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function fetchAll() {
  try {
    const [s, b, br, stocks] = await Promise.all([
      fetch(`${API}/dashboard/summary`, { headers: headers() }).then(r => r.json()),
      fetch(`${API}/dashboard/bots`, { headers: headers() }).then(r => r.json()),
      fetch(`${API}/broker/status`, { headers: headers() }).then(r => r.json()),
      fetch(`${API}/market/stocks?limit=1`, { headers: headers() }).then(r => r.json()).catch(() => null),
    ])
    summary.value = s
    alerts.value = s.alerts || []
    botSnapshots.value = b
    brokerStatus.value = br
    if (stocks) stockCount.value = stocks.total
  } catch (e) {
    // 무시
  }
}

async function emergencyStop() {
  if (!confirm('모든 RUNNING 봇을 즉시 정지하시겠습니까?')) return
  const res = await fetch(`${API}/broker/emergency-stop`, { method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' } })
  const data = await res.json()
  alert(`${data.count}개 봇이 정지되었습니다`)
  fetchAll()
}

async function clearAlerts() {
  await fetch(`${API}/broker/alerts`, { method: 'DELETE', headers: headers() })
  alerts.value = []
}

const brokerLabel = () => {
  if (brokerStatus.value.mode === 'real') return brokerStatus.value.connected ? '키움 연결됨' : '키움 미연결'
  return 'Mock 모드'
}

const brokerPillClass = () => {
  if (brokerStatus.value.mode === 'real') return brokerStatus.value.connected ? 'pill-green' : 'pill-red'
  return 'pill-blue'
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

function fmtDatetime(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  fetchAll()
  refreshTimer = setInterval(fetchAll, 30000)  // 30초마다 갱신
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard { max-width: 1200px; }

.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

h1 { margin: 0; font-size: 22px; font-weight: 700; color: #e5e7eb; }

.header-right { display: flex; align-items: center; gap: 12px; }

.broker-pill {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.pill-blue { background: rgba(79,158,255,.15); color: #4f9eff; }
.pill-green { background: rgba(16,185,129,.15); color: #10b981; }
.pill-red { background: rgba(239,68,68,.15); color: #ef4444; }

.btn-emergency {
  padding: 7px 16px;
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

/* 요약 카드 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

.s-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.s-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }
.s-value { font-size: 20px; font-weight: 700; }
.blue { color: #4f9eff; }
.profit { color: #ef4444; }
.loss { color: #10b981; }

.status-card .status-row { display: flex; gap: 12px; }
.status-num { font-size: 18px; font-weight: 700; display: flex; align-items: baseline; gap: 3px; }
.status-num small { font-size: 10px; font-weight: 400; }
.status-num.green { color: #10b981; }
.status-num.gray { color: #6b7280; }
.status-num.red { color: #ef4444; }

/* 하단 그리드 */
.bottom-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.panel {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #2a2d3e;
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.panel-link {
  font-size: 12px;
  color: #4f9eff;
  text-decoration: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.panel-link:hover { text-decoration: underline; }

.empty-panel {
  padding: 40px;
  text-align: center;
  color: #4b5563;
  font-size: 13px;
}

/* 봇 미니 테이블 */
.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.mini-table th {
  padding: 8px 14px;
  text-align: right;
  color: #6b7280;
  font-weight: 500;
  background: #14172080;
  border-bottom: 1px solid #2a2d3e;
}
.mini-table th:first-child, .mini-table th:nth-child(2), .mini-table th:nth-child(3) { text-align: left; }

.mini-table td {
  padding: 10px 14px;
  text-align: right;
  color: #e5e7eb;
  border-bottom: 1px solid #1a1f2e;
}
.mini-table td:first-child, .mini-table td:nth-child(2), .mini-table td:nth-child(3) { text-align: left; }

.mini-table tbody tr.clickable { cursor: pointer; }
.mini-table tbody tr.clickable:hover { background: #1f2235; }

.bot-name-cell { font-weight: 500; }

.badge {
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}
.badge-green { background: rgba(16,185,129,.2); color: #10b981; }
.badge-red { background: rgba(239,68,68,.2); color: #ef4444; }
.badge-gray { background: rgba(107,114,128,.2); color: #9ca3af; }

.mode-badge {
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}
.mode-mock { background: rgba(79,158,255,.15); color: #4f9eff; }
.mode-paper { background: rgba(245,158,11,.15); color: #f59e0b; }
.mode-real { background: rgba(239,68,68,.15); color: #ef4444; }

/* 알림 */
.alert-list {
  display: flex;
  flex-direction: column;
  max-height: 400px;
  overflow-y: auto;
}

.alert-item {
  padding: 12px 16px;
  border-bottom: 1px solid #1a1f2e;
  border-left: 3px solid #2a2d3e;
}
.alert-item.alert-error { border-left-color: #ef4444; }
.alert-item.alert-warn { border-left-color: #f59e0b; }

.alert-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 3px;
}

.alert-type { font-size: 10px; font-weight: 700; color: #ef4444; text-transform: uppercase; }
.alert-time { font-size: 10px; color: #4b5563; }
.alert-bot { font-size: 12px; color: #9ca3af; font-weight: 500; margin-bottom: 2px; }
.alert-msg { font-size: 11px; color: #6b7280; }
</style>
