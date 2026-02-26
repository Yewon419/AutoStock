<template>
  <div class="stock-detail">
    <!-- 헤더 -->
    <div class="detail-header">
      <RouterLink to="/market" class="back-link">← 목록으로</RouterLink>
      <div v-if="stock" class="stock-info">
        <h2 class="stock-name">{{ stock.company_name }}</h2>
        <span class="stock-ticker">{{ stock.ticker }}</span>
        <span class="badge" :class="stock.market_type.toLowerCase()">{{ stock.market_type }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading">로딩 중...</div>
    <div v-else-if="!stock" class="error">종목을 찾을 수 없습니다.</div>

    <template v-else>
      <!-- 기간 선택 -->
      <div class="period-tabs">
        <button
          v-for="p in periods"
          :key="p.days"
          class="period-btn"
          :class="{ active: selectedDays === p.days }"
          @click="setPeriod(p.days)"
        >
          {{ p.label }}
        </button>
      </div>

      <!-- 가격 없음 안내 -->
      <div v-if="prices.length === 0" class="no-data">
        <p>가격 데이터가 없습니다.</p>
        <p>주식 데이터 탭에서 수집 버튼을 눌러 데이터를 수집하거나, 특정 종목만 수집하려면 아래 버튼을 이용하세요.</p>
        <button class="collect-btn" :disabled="collecting" @click="collectThis">
          {{ collecting ? '수집 중...' : '이 종목 수집' }}
        </button>
      </div>

      <!-- 캔들 차트 -->
      <div v-else>
        <div class="chart-title">캔들 차트 (일봉)</div>
        <div ref="candleRef" class="chart-container"></div>

        <!-- 지표 선택 -->
        <div class="indicator-section">
          <div class="indicator-tabs">
            <button
              v-for="ind in indicatorList"
              :key="ind.key"
              class="ind-btn"
              :class="{ active: selectedIndicator === ind.key }"
              @click="selectedIndicator = ind.key"
            >
              {{ ind.label }}
            </button>
          </div>
          <div ref="indicatorRef" class="chart-container small"></div>
        </div>

        <!-- 최신 지표 수치 -->
        <div v-if="latestIndicator" class="indicator-values">
          <div class="ind-grid">
            <div class="ind-item" v-for="item in indicatorSummary" :key="item.label">
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
  { days: 30, label: '1개월' },
  { days: 90, label: '3개월' },
  { days: 180, label: '6개월' },
  { days: 365, label: '1년' },
]

const indicatorList = [
  { key: 'rsi', label: 'RSI' },
  { key: 'macd', label: 'MACD' },
  { key: 'volume', label: '거래량' },
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
  } catch (e) {
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
    const chartOpts = {
      layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
      crosshair: { mode: CrosshairMode?.Normal ?? 1 },
      timeScale: { borderColor: '#2a2d3e', timeVisible: true },
      rightPriceScale: { borderColor: '#2a2d3e' },
    }

    // 캔들 차트
    if (candleRef.value) {
      if (candleChart) candleChart.remove()
      candleChart = createChart(candleRef.value, {
        ...chartOpts,
        width: candleRef.value.clientWidth,
        height: 320,
      })
      candleSeries = candleChart.addSeries(CandlestickSeries, {
        upColor: '#ef4444',     // 한국: 빨강 = 상승
        downColor: '#3b82f6',   // 파랑 = 하락
        borderVisible: false,
        wickUpColor: '#ef4444',
        wickDownColor: '#3b82f6',
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

    // 지표 차트
    renderIndicatorChart(createChart, chartOpts, { LineSeries, HistogramSeries })
  })
}

function renderIndicatorChart(createChart, chartOpts, { LineSeries, HistogramSeries }) {
  if (!indicatorRef.value || indicators.value.length === 0) return

  if (indicatorChart) indicatorChart.remove()
  indicatorChart = createChart(indicatorRef.value, {
    ...chartOpts,
    width: indicatorRef.value.clientWidth,
    height: 150,
  })

  if (selectedIndicator.value === 'rsi') {
    indicatorSeries = indicatorChart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1.5 })
    const data = indicators.value
      .filter((i) => i.rsi != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.rsi }))
    indicatorSeries.setData(data)

  } else if (selectedIndicator.value === 'macd') {
    indicatorSeries = indicatorChart.addSeries(LineSeries, { color: '#4f9eff', lineWidth: 1.5 })
    const macdData = indicators.value
      .filter((i) => i.macd != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.macd }))
    indicatorSeries.setData(macdData)

    const signalSeries = indicatorChart.addSeries(LineSeries, { color: '#f87171', lineWidth: 1 })
    const signalData = indicators.value
      .filter((i) => i.macd_signal != null)
      .map((i) => ({ time: toTimestamp(i.date), value: i.macd_signal }))
    signalSeries.setData(signalData)

  } else if (selectedIndicator.value === 'volume') {
    indicatorSeries = indicatorChart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
    })
    const volData = prices.value
      .filter((p) => p.volume != null)
      .map((p) => ({ time: toTimestamp(p.date), value: p.volume, color: '#3b82f6' }))
    indicatorSeries.setData(volData)
  }

  indicatorChart.timeScale().fitContent()
}

async function collectThis() {
  collecting.value = true
  try {
    await api.post(`/market/collect?ticker=${ticker}`)
    setTimeout(fetchData, 2000)
  } catch (e) {
    // ignore
  } finally {
    collecting.value = false
  }
}

watch(selectedIndicator, () => {
  import('lightweight-charts').then((lc) => {
    const { createChart, LineSeries, HistogramSeries } = lc
    const chartOpts = {
      layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
      timeScale: { borderColor: '#2a2d3e', timeVisible: true },
      rightPriceScale: { borderColor: '#2a2d3e' },
    }
    renderIndicatorChart(createChart, chartOpts, { LineSeries, HistogramSeries })
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
  max-width: 1000px;
}

.detail-header {
  margin-bottom: 20px;
}

.back-link {
  color: #6b7280;
  text-decoration: none;
  font-size: 13px;
  display: inline-block;
  margin-bottom: 12px;
}

.back-link:hover {
  color: #4f9eff;
}

.stock-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stock-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
}

.stock-ticker {
  font-family: monospace;
  color: #6b7280;
  font-size: 14px;
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.badge.kospi { background: #1e3a5f; color: #4f9eff; }
.badge.kosdaq { background: #1e3b2a; color: #4ade80; }

.loading, .error {
  padding: 60px;
  text-align: center;
  color: #6b7280;
}

.period-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
}

.period-btn {
  padding: 6px 14px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.period-btn:hover, .period-btn.active {
  border-color: #4f9eff;
  color: #4f9eff;
  background: #1e3a5f;
}

.no-data {
  padding: 60px;
  text-align: center;
  color: #6b7280;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  line-height: 2;
}

.collect-btn {
  margin-top: 16px;
  padding: 8px 20px;
  background: #1e3a5f;
  border: 1px solid #4f9eff;
  border-radius: 8px;
  color: #4f9eff;
  font-size: 14px;
  cursor: pointer;
}

.chart-title {
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.chart-container {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 16px;
}

.chart-container.small {
  margin-bottom: 0;
}

.indicator-section {
  margin-top: 16px;
}

.indicator-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.ind-btn {
  padding: 5px 12px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.ind-btn:hover, .ind-btn.active {
  border-color: #f59e0b;
  color: #f59e0b;
  background: #2a1f0a;
}

.indicator-values {
  margin-top: 16px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  padding: 20px;
}

.ind-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.ind-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ind-label {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ind-value {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}

.ind-value.overbought { color: #ef4444; }
.ind-value.oversold { color: #3b82f6; }
</style>
