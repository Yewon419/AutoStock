<template>
  <div class="bot-detail" v-if="bot">
    <!-- 헤더 -->
    <div class="detail-header">
      <div class="header-left">
        <button class="back-btn" @click="router.push('/bots')">← 목록</button>
        <h1>{{ bot.name }}</h1>
        <span class="badge" :class="statusClass(bot.status)">{{ bot.status }}</span>
      </div>
      <div class="header-actions">
        <button
          v-if="bot.status !== 'RUNNING'"
          class="btn-start"
          @click="startBot"
        >▶ 시작</button>
        <button
          v-if="bot.status === 'RUNNING'"
          class="btn-stop"
          @click="stopBot"
        >⏹ 정지</button>
      </div>
    </div>

    <!-- 요약 카드 -->
    <div class="summary-grid">
      <div class="summary-card">
        <span class="s-label">초기 자금</span>
        <span class="s-value">{{ fmtMoney(bot.initial_cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">현재 캐시</span>
        <span class="s-value">{{ fmtMoney(bot.cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">손절 / 익절</span>
        <span class="s-value">{{ bot.stop_loss_pct }}% / {{ bot.take_profit_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">최대 낙폭</span>
        <span class="s-value">{{ bot.max_drawdown_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">포지션 크기</span>
        <span class="s-value">{{ bot.position_size_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">거래 시간</span>
        <span class="s-value">{{ fmtTime(bot.trading_start_time) }} ~ {{ fmtTime(bot.trading_end_time) }}</span>
      </div>
    </div>

    <!-- 종목 태그 -->
    <div class="tickers-row">
      <span class="tickers-label">대상 종목</span>
      <div class="ticker-tags">
        <span v-for="t in (bot.tickers || [])" :key="t" class="ticker-tag">{{ t }}</span>
        <span v-if="!(bot.tickers || []).length" class="no-tickers">종목 없음</span>
      </div>
    </div>

    <!-- 탭 -->
    <div class="tabs">
      <button
        v-for="tab in ['positions', 'orders', 'reports']"
        :key="tab"
        class="tab-btn"
        :class="{ active: activeTab === tab }"
        @click="switchTab(tab)"
      >{{ tabLabel(tab) }}</button>
    </div>

    <!-- 포지션 탭 -->
    <div v-if="activeTab === 'positions'">
      <div v-if="positions.length === 0" class="empty-tab">보유 포지션이 없습니다.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>종목</th>
            <th>수량</th>
            <th>평균단가</th>
            <th>현재가</th>
            <th>평가금액</th>
            <th>미실현손익</th>
            <th>수익률</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pos in positions" :key="pos.id">
            <td class="ticker-cell">{{ pos.ticker }}</td>
            <td>{{ pos.quantity.toLocaleString() }}</td>
            <td>{{ fmtPrice(pos.avg_price) }}</td>
            <td>{{ fmtPrice(pos.current_price) }}</td>
            <td>{{ fmtPrice(pos.market_value) }}</td>
            <td :class="pnlClass(pos.unrealized_pnl)">{{ fmtPnl(pos.unrealized_pnl) }}</td>
            <td :class="pnlClass(pos.unrealized_pct)">{{ pos.unrealized_pct > 0 ? '+' : '' }}{{ pos.unrealized_pct.toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 주문 탭 -->
    <div v-if="activeTab === 'orders'">
      <div v-if="orders.length === 0" class="empty-tab">주문 내역이 없습니다.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>시각</th>
            <th>종목</th>
            <th>구분</th>
            <th>수량</th>
            <th>체결가</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td class="time-cell">{{ fmtDatetime(o.created_at) }}</td>
            <td>{{ o.ticker }}</td>
            <td :class="o.order_type === 'BUY' ? 'buy-cell' : 'sell-cell'">{{ o.order_type }}</td>
            <td>{{ o.quantity.toLocaleString() }}</td>
            <td>{{ fmtPrice(o.price) }}</td>
            <td><span class="badge badge-gray">{{ o.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 보고서 탭 -->
    <div v-if="activeTab === 'reports'">
      <div v-if="reports.length === 0" class="empty-tab">일별 보고서가 없습니다.</div>
      <div v-else>
        <!-- 누적 손익 차트 -->
        <div class="chart-container">
          <div ref="chartEl" style="height: 200px;"></div>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>총 자산</th>
              <th>캐시</th>
              <th>보유 평가</th>
              <th>일일 손익</th>
              <th>누적 손익</th>
              <th>승률</th>
              <th>거래 수</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id">
              <td>{{ r.date }}</td>
              <td>{{ fmtPrice(r.total_assets) }}</td>
              <td>{{ fmtPrice(r.cash) }}</td>
              <td>{{ fmtPrice(r.holdings_value) }}</td>
              <td :class="pnlClass(r.daily_pnl)">{{ fmtPnl(r.daily_pnl) }}</td>
              <td :class="pnlClass(r.total_pnl)">{{ fmtPnl(r.total_pnl) }}</td>
              <td>{{ r.win_rate.toFixed(1) }}%</td>
              <td>{{ r.total_trades }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div v-else class="loading">불러오는 중...</div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const API = 'http://localhost:8001/api/v1'

const bot = ref(null)
const positions = ref([])
const orders = ref([])
const reports = ref([])
const activeTab = ref('positions')
const chartEl = ref(null)
let chart = null
let lineSeries = null

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

const botId = route.params.id

async function fetchBot() {
  const res = await fetch(`${API}/bots/${botId}`, { headers: headers() })
  if (res.ok) bot.value = await res.json()
}

async function fetchPositions() {
  const res = await fetch(`${API}/bots/${botId}/positions`, { headers: headers() })
  if (res.ok) positions.value = await res.json()
}

async function fetchOrders() {
  const res = await fetch(`${API}/bots/${botId}/orders`, { headers: headers() })
  if (res.ok) orders.value = await res.json()
}

async function fetchReports() {
  const res = await fetch(`${API}/bots/${botId}/reports`, { headers: headers() })
  if (res.ok) {
    const data = await res.json()
    // 최신순 → 오래된순 정렬 (차트용)
    reports.value = data
    await nextTick()
    renderChart(data.slice().reverse())
  }
}

async function renderChart(data) {
  if (!chartEl.value || !data.length) return
  const { createChart } = await import('lightweight-charts')
  if (chart) { chart.remove(); chart = null }
  chart = createChart(chartEl.value, {
    layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
    grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
    rightPriceScale: { borderColor: '#2a2d3e' },
    timeScale: { borderColor: '#2a2d3e', timeVisible: true },
    height: 200,
  })
  lineSeries = chart.addLineSeries({
    color: '#4f9eff',
    lineWidth: 2,
    priceFormat: { type: 'price', precision: 0, minMove: 1 },
  })
  lineSeries.setData(data.map(r => ({
    time: r.date,
    value: r.total_pnl,
  })))
  chart.timeScale().fitContent()
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'positions') await fetchPositions()
  else if (tab === 'orders') await fetchOrders()
  else if (tab === 'reports') await fetchReports()
}

async function startBot() {
  await fetch(`${API}/bots/${botId}/start`, { method: 'POST', headers: headers() })
  fetchBot()
}

async function stopBot() {
  await fetch(`${API}/bots/${botId}/stop`, { method: 'POST', headers: headers() })
  fetchBot()
}

function statusClass(s) {
  if (s === 'RUNNING') return 'badge-green'
  if (s === 'ERROR') return 'badge-red'
  return 'badge-gray'
}

function tabLabel(tab) {
  return { positions: '보유 포지션', orders: '주문 내역', reports: '일별 보고서' }[tab]
}

function fmtMoney(v) {
  if (!v) return '0원'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtPrice(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtPnl(v) {
  if (v == null) return '-'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toLocaleString('ko-KR') + '원'
}

function fmtTime(t) {
  if (!t) return '-'
  return String(t).slice(0, 5)
}

function fmtDatetime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function pnlClass(v) {
  const n = Number(v)
  if (n > 0) return 'profit'
  if (n < 0) return 'loss'
  return ''
}

onMounted(async () => {
  await fetchBot()
  await fetchPositions()
})
</script>

<style scoped>
.bot-detail { max-width: 1100px; }

.loading { text-align: center; color: #6b7280; padding: 80px 0; }

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.back-btn {
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.back-btn:hover { color: #e5e7eb; border-color: #4b5563; }

h1 { margin: 0; font-size: 20px; font-weight: 700; color: #e5e7eb; }

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green { background: rgba(16,185,129,.2); color: #10b981; }
.badge-red { background: rgba(239,68,68,.2); color: #ef4444; }
.badge-gray { background: rgba(107,114,128,.2); color: #9ca3af; }

.header-actions { display: flex; gap: 8px; }

.btn-start, .btn-stop {
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 14px;
  border: none;
  cursor: pointer;
  font-weight: 600;
}
.btn-start { background: rgba(16,185,129,.2); color: #10b981; }
.btn-start:hover { background: rgba(16,185,129,.3); }
.btn-stop { background: rgba(239,68,68,.2); color: #ef4444; }
.btn-stop:hover { background: rgba(239,68,68,.3); }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.summary-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.s-label { font-size: 11px; color: #6b7280; }
.s-value { font-size: 14px; color: #e5e7eb; font-weight: 600; }

.tickers-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding: 12px 16px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
}

.tickers-label { font-size: 12px; color: #6b7280; white-space: nowrap; }

.ticker-tags { display: flex; flex-wrap: wrap; gap: 6px; }

.ticker-tag {
  background: #2a2d3e;
  color: #9ca3af;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.no-tickers { font-size: 12px; color: #4b5563; }

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid #2a2d3e;
}

.tab-btn {
  padding: 10px 20px;
  background: none;
  border: none;
  color: #6b7280;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab-btn:hover { color: #e5e7eb; }
.tab-btn.active { color: #4f9eff; border-bottom-color: #4f9eff; }

.empty-tab {
  text-align: center;
  color: #4b5563;
  padding: 60px 0;
  font-size: 14px;
}

.chart-container {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  padding: 10px 12px;
  text-align: right;
  color: #6b7280;
  font-weight: 500;
  border-bottom: 1px solid #2a2d3e;
  white-space: nowrap;
}
.data-table th:first-child { text-align: left; }

.data-table td {
  padding: 10px 12px;
  text-align: right;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2235;
}
.data-table td:first-child { text-align: left; }

.data-table tbody tr:hover { background: #1f2235; }

.ticker-cell { font-weight: 600; color: #4f9eff; }
.time-cell { color: #9ca3af; font-size: 12px; }
.buy-cell { color: #ef4444; font-weight: 600; }
.sell-cell { color: #10b981; font-weight: 600; }

.profit { color: #ef4444; }
.loss { color: #10b981; }
</style>
