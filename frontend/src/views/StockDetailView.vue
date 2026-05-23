<template>
  <div class="stock-detail">
    <header class="detail-header">
      <RouterLink to="/market" class="back-link">
        <span aria-hidden="true">←</span>
        <span>마켓 목록</span>
      </RouterLink>
      <div v-if="stock" class="stock-info">
        <h1 class="stock-name">{{ stock.company_name }}</h1>
        <span class="stock-ticker">{{ stock.ticker }}</span>
        <span class="badge" :class="stock.market_type.toLowerCase()">
          {{ stock.market_type }}
        </span>
      </div>
    </header>

    <div v-if="loading" class="loading">LOADING...</div>
    <div v-else-if="!stock" class="error">
      <span class="err-tag">404</span>
      종목을 찾을 수 없습니다.
    </div>

    <template v-else>
      <!-- 기간 선택 -->
      <div class="control-bar">
        <span class="control-label">PERIOD</span>
        <div class="tab-group" role="tablist">
          <button
            v-for="p in periods"
            :key="p.days"
            class="tab-btn"
            type="button"
            :class="{ active: selectedDays === p.days }"
            role="tab"
            :aria-selected="selectedDays === p.days"
            @click="setPeriod(p.days)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <!-- 가격 없음 안내 -->
      <div v-if="prices.length === 0" class="no-data">
        <div class="no-data-icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="3 17 9 11 13 15 21 7" />
            <polyline points="14 7 21 7 21 14" />
          </svg>
        </div>
        <p class="no-data-title">가격 데이터가 없습니다</p>
        <p class="no-data-desc">
          전체 수집이 안 돌았거나 이 종목 데이터가 누락됐을 수 있습니다.
        </p>
        <button
          class="collect-btn"
          type="button"
          :disabled="collecting"
          @click="collectThis"
        >
          <svg
            v-if="!collecting"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M21 12a9 9 0 1 1-9-9" />
            <polyline points="21 4 21 10 15 10" />
          </svg>
          <svg
            v-else
            class="spin"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M21 12a9 9 0 1 1-6-8.5" />
          </svg>
          <span>{{ collecting ? 'COLLECTING' : 'COLLECT THIS' }}</span>
        </button>
      </div>

      <!-- 캔들 차트 -->
      <div v-else class="chart-stack">
        <div class="chart-block">
          <div class="chart-head">
            <span class="chart-label">CANDLE · 일봉</span>
            <span class="chart-meta">{{ prices.length }} BARS</span>
          </div>
          <div ref="candleRef" class="chart-container"></div>
        </div>

        <!-- 지표 차트 -->
        <div class="chart-block">
          <div class="chart-head">
            <span class="chart-label">INDICATOR</span>
            <div class="tab-group small" role="tablist">
              <button
                v-for="ind in indicatorList"
                :key="ind.key"
                class="tab-btn"
                type="button"
                :class="{ active: selectedIndicator === ind.key }"
                role="tab"
                :aria-selected="selectedIndicator === ind.key"
                @click="selectedIndicator = ind.key"
              >
                {{ ind.label }}
              </button>
            </div>
          </div>
          <div ref="indicatorRef" class="chart-container small"></div>
        </div>

        <!-- 최신 지표 수치 -->
        <div v-if="latestIndicator" class="indicator-values">
          <div class="ind-head">
            <span class="chart-label">LATEST · 지표</span>
          </div>
          <div class="ind-grid">
            <div v-for="item in indicatorSummary" :key="item.label" class="ind-item">
              <span class="ind-label">{{ item.label }}</span>
              <span class="ind-value" :class="item.cls">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/index'

const route = useRoute()
const ticker = route.params.ticker

const stock = ref(null)
const prices = ref([])
const indicators = ref([])
const loading = ref(true)
const collecting = ref(false)
const selectedDays = ref(180)
const selectedIndicator = ref('rsi')

const candleRef = ref(null)
const indicatorRef = ref(null)

let candleChart = null
let candleSeries = null
let indicatorChart = null
let indicatorSeries = null

const periods = [
  { days: 30, label: '1M' },
  { days: 90, label: '3M' },
  { days: 180, label: '6M' },
  { days: 365, label: '1Y' },
]

const indicatorList = [
  { key: 'rsi', label: 'RSI' },
  { key: 'macd', label: 'MACD' },
  { key: 'volume', label: 'VOL' },
]

const latestIndicator = computed(() => {
  return indicators.value.length > 0 ? indicators.value[indicators.value.length - 1] : null
})

const indicatorSummary = computed(() => {
  const ind = latestIndicator.value
  if (!ind) return []
  const fmt = (v) => (v != null ? v.toFixed(2) : '-')
  const rsiCls = ind.rsi != null ? (ind.rsi >= 70 ? 'overbought' : ind.rsi <= 30 ? 'oversold' : '') : ''
  return [
    { label: 'RSI(14)', value: fmt(ind.rsi), cls: rsiCls },
    { label: 'MACD', value: fmt(ind.macd), cls: '' },
    { label: 'Signal', value: fmt(ind.macd_signal), cls: '' },
    { label: 'Stoch %K', value: fmt(ind.stoch_k), cls: '' },
    { label: 'Stoch %D', value: fmt(ind.stoch_d), cls: '' },
    { label: 'MA20', value: fmt(ind.ma_20), cls: '' },
    { label: 'MA50', value: fmt(ind.ma_50), cls: '' },
    { label: 'ADX', value: fmt(ind.adx), cls: '' },
  ]
})

function toTimestamp(dateStr) {
  return Math.floor(new Date(dateStr).getTime() / 1000)
}

// 차트 공통 옵션 (디자인 토큰 톤과 일치)
function chartOpts(CrosshairMode) {
  return {
    layout: { background: { color: '#0d1118' }, textColor: '#a1a1aa' },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.04)' },
      horzLines: { color: 'rgba(255,255,255,0.04)' },
    },
    crosshair: { mode: CrosshairMode?.Normal ?? 1 },
    timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true },
    rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
  }
}

async function fetchData() {
  loading.value = true
  try {
    const [stockData, priceData, indData] = await Promise.all([
      api.get(`/market/stocks/${ticker}`),
      api.get(`/market/stocks/${ticker}/prices?start_date=${getStartDate()}`),
      api.get(`/market/stocks/${ticker}/indicators?start_date=${getStartDate()}`),
    ])
    stock.value = stockData
    prices.value = priceData
    indicators.value = indData
  } catch {
    stock.value = null
  } finally {
    loading.value = false
  }
}

function getStartDate() {
  const d = new Date()
  d.setDate(d.getDate() - selectedDays.value)
  return d.toISOString().split('T')[0]
}

async function setPeriod(days) {
  selectedDays.value = days
  await fetchData()
  renderCharts()
}

function renderCharts() {
  if (prices.value.length === 0) return

  import('lightweight-charts').then((lc) => {
    const { createChart, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } = lc
    const opts = chartOpts(CrosshairMode)

    if (candleRef.value) {
      if (candleChart) candleChart.remove()
      candleChart = createChart(candleRef.value, {
        ...opts,
        width: candleRef.value.clientWidth,
        height: 360,
      })
      candleSeries = candleChart.addSeries(CandlestickSeries, {
        upColor: '#ef4444',     // 한국: 빨강 = 상승
        downColor: '#60a5fa',   // 파랑 = 하락
        borderVisible: false,
        wickUpColor: '#ef4444',
        wickDownColor: '#60a5fa',
      })
      const candleData = prices.value.map((p) => ({
        time: toTimestamp(p.date),
        open: p.open_price ?? p.close_price,
        high: p.high_price ?? p.close_price,
        low: p.low_price ?? p.close_price,
        close: p.close_price,
      }))
      candleSeries.setData(candleData)
      candleChart.timeScale().fitContent()
    }

    renderIndicatorChart(createChart, opts, { LineSeries, HistogramSeries })
  })
}

function renderIndicatorChart(createChart, opts, { LineSeries, HistogramSeries }) {
  if (!indicatorRef.value || indicators.value.length === 0) return

  if (indicatorChart) indicatorChart.remove()
  indicatorChart = createChart(indicatorRef.value, {
    ...opts,
    width: indicatorRef.value.clientWidth,
    height: 160,
  })

  if (selectedIndicator.value === 'rsi') {
    indicatorSeries = indicatorChart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1.5 })
    const data = indicators.value
      .filter((i) => i.rsi != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.rsi }))
    indicatorSeries.setData(data)
  } else if (selectedIndicator.value === 'macd') {
    indicatorSeries = indicatorChart.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 1.5 })
    const macdData = indicators.value
      .filter((i) => i.macd != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.macd }))
    indicatorSeries.setData(macdData)

    const signalSeries = indicatorChart.addSeries(LineSeries, { color: '#fca5a5', lineWidth: 1 })
    const signalData = indicators.value
      .filter((i) => i.macd_signal != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.macd_signal }))
    signalSeries.setData(signalData)
  } else if (selectedIndicator.value === 'volume') {
    indicatorSeries = indicatorChart.addSeries(HistogramSeries, {
      color: '#60a5fa',
      priceFormat: { type: 'volume' },
    })
    const volData = prices.value
      .filter((p) => p.volume != null)
      .map((p) => ({ time: toTimestamp(p.date), value: p.volume, color: '#60a5fa' }))
    indicatorSeries.setData(volData)
  }

  indicatorChart.timeScale().fitContent()
}

async function collectThis() {
  collecting.value = true
  try {
    await api.post(`/market/collect?ticker=${ticker}`)
    setTimeout(fetchData, 2000)
  } catch {
    // ignore
  } finally {
    collecting.value = false
  }
}

watch(selectedIndicator, () => {
  import('lightweight-charts').then((lc) => {
    const { createChart, CrosshairMode, LineSeries, HistogramSeries } = lc
    renderIndicatorChart(createChart, chartOpts(CrosshairMode), { LineSeries, HistogramSeries })
  })
})

onMounted(async () => {
  await fetchData()
  renderCharts()
})

onUnmounted(() => {
  if (candleChart) candleChart.remove()
  if (indicatorChart) indicatorChart.remove()
})
</script>

<style scoped>
.stock-detail {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ==========================================================================
   Header
   ========================================================================== */

.detail-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  text-decoration: none;
  transition: color var(--dur-fast) var(--ease-out);
  width: fit-content;
}

.back-link:hover {
  color: var(--accent);
}

.stock-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.stock-name {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  margin: 0;
}

.stock-ticker {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: var(--text-md);
  letter-spacing: var(--tracking-wide);
}

.badge {
  font-family: var(--font-mono);
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

.badge.kospi {
  background: var(--accent-bg);
  color: var(--accent);
}

.badge.kosdaq {
  background: var(--up-bg);
  color: var(--up-strong);
}

/* ==========================================================================
   Loading / Error
   ========================================================================== */

.loading {
  padding: var(--space-20);
  text-align: center;
  color: var(--text-muted);
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wider);
  font-size: var(--text-sm);
}

.error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-20);
  color: var(--text-secondary);
  font-size: var(--text-md);
}

.err-tag {
  font-family: var(--font-mono);
  background: var(--profit-bg);
  color: var(--profit);
  padding: 4px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
}

/* ==========================================================================
   Control bar (period selector)
   ========================================================================== */

.control-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.control-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.tab-group {
  display: inline-flex;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}

.tab-group.small {
  padding: 2px;
}

.tab-btn {
  padding: 6px var(--space-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.tab-group.small .tab-btn {
  padding: 5px var(--space-3);
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  background: var(--accent-bg);
  color: var(--accent);
}

/* ==========================================================================
   No data state
   ========================================================================== */

.no-data {
  background: var(--surface-1);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  padding: var(--space-12) var(--space-5);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.no-data-icon {
  color: var(--text-faint);
  margin-bottom: var(--space-2);
}

.no-data-icon svg {
  width: 40px;
  height: 40px;
}

.no-data-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.no-data-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.collect-btn {
  margin-top: var(--space-3);
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

.collect-btn svg {
  width: 14px;
  height: 14px;
}

.collect-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.collect-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ==========================================================================
   Chart stack
   ========================================================================== */

.chart-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.chart-block {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.chart-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.chart-meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wider);
}

.chart-container {
  width: 100%;
}

.chart-container.small {
  /* indicator chart smaller */
}

/* ==========================================================================
   Latest indicator values
   ========================================================================== */

.indicator-values {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.ind-head {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.ind-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
  padding: var(--space-5);
}

.ind-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.ind-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.ind-value {
  font-family: var(--font-mono);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.ind-value.overbought {
  color: var(--profit);
}

.ind-value.oversold {
  color: var(--loss);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 720px) {
  .ind-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .stock-name {
    font-size: var(--text-2xl);
  }
  .chart-head {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }
}
</style>
