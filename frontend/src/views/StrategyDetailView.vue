<template>
  <div class="strategy-detail">
    <RouterLink to="/strategies" class="back-link">← 전략 목록</RouterLink>

    <div v-if="!strategy" class="loading">로딩 중...</div>
    <template v-else>
      <!-- 전략 헤더 -->
      <div class="strategy-header">
        <h2 class="strategy-name">{{ strategy.name }}</h2>
        <p v-if="strategy.description" class="strategy-desc">{{ strategy.description }}</p>
      </div>

      <!-- 조건 목록 -->
      <div class="section">
        <h3 class="section-title">매수 조건 (모두 충족 시)</h3>
        <div class="conditions-list">
          <div v-for="(c, idx) in strategy.conditions" :key="idx" class="condition-item">
            <span class="cond-num">{{ idx + 1 }}</span>
            <span class="cond-indicator">{{ indicatorLabel(c.indicator) }}</span>
            <span class="cond-op">{{ conditionLabel(c.condition) }}</span>
            <span class="cond-value">
              {{ c.value != null ? c.value : '' }}
              {{ c.value2 != null ? ' ~ ' + c.value2 : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 백테스트 설정 -->
      <div class="section">
        <h3 class="section-title">백테스트 설정</h3>
        <div class="bt-form">
          <div class="form-row">
            <div class="field">
              <label>종목 코드 (쉼표 구분)</label>
              <input v-model="btForm.tickersRaw" type="text" placeholder="005930, 000660, 035420" />
            </div>
          </div>
          <div class="form-row">
            <div class="field">
              <label>시작일</label>
              <input v-model="btForm.start_date" type="date" />
            </div>
            <div class="field">
              <label>종료일</label>
              <input v-model="btForm.end_date" type="date" />
            </div>
          </div>
          <div class="form-row">
            <div class="field">
              <label>초기 자본 (원)</label>
              <input v-model.number="btForm.initial_capital" type="number" />
            </div>
            <div class="field">
              <label>손절 (%)</label>
              <input v-model.number="btForm.stop_loss_pct" type="number" placeholder="예: 5" />
            </div>
            <div class="field">
              <label>익절 (%)</label>
              <input v-model.number="btForm.take_profit_pct" type="number" placeholder="예: 10" />
            </div>
          </div>
          <p v-if="btError" class="bt-error">{{ btError }}</p>
          <button class="run-btn" :disabled="running" @click="runBacktest">
            {{ running ? '실행 중...' : '백테스트 실행' }}
          </button>
        </div>
      </div>

      <!-- 백테스트 결과 -->
      <div v-if="result" class="section result-section">
        <div class="result-header">
          <h3 class="section-title">백테스트 결과</h3>
          <div class="grade-badge" :class="'grade-' + result.summary.grade">
            {{ result.summary.grade }}
            <span class="grade-score">{{ result.summary.total_score }}점</span>
          </div>
        </div>

        <!-- 요약 카드 -->
        <div class="summary-grid">
          <div class="summary-card" v-for="m in summaryMetrics" :key="m.label">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value" :class="m.cls">{{ m.value }}</div>
          </div>
        </div>

        <!-- 자산 곡선 차트 -->
        <div v-if="result.equity_curve.length > 0" class="chart-section">
          <div class="chart-title">포트폴리오 자산 곡선</div>
          <div ref="equityRef" class="chart-container"></div>
        </div>

        <!-- 거래 내역 -->
        <div v-if="sellTrades.length > 0" class="trades-section">
          <h4 class="trades-title">거래 내역 (매도 {{ sellTrades.length }}건)</h4>
          <div class="table-wrap">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>매수일</th>
                  <th>매도일</th>
                  <th>매수가</th>
                  <th>매도가</th>
                  <th>수익률</th>
                  <th>손익</th>
                  <th>사유</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(t, idx) in sellTrades" :key="idx" :class="t.pnl >= 0 ? 'win' : 'loss'">
                  <td class="ticker-col"><StockLink :ticker="t.ticker" /></td>
                  <td>{{ t.buy_date }}</td>
                  <td>{{ t.date }}</td>
                  <td>{{ t.buy_price?.toLocaleString() }}</td>
                  <td>{{ t.price?.toLocaleString() }}</td>
                  <td :class="t.return_pct >= 0 ? 'pos' : 'neg'">
                    {{ t.return_pct >= 0 ? '+' : '' }}{{ t.return_pct }}%
                  </td>
                  <td :class="t.pnl >= 0 ? 'pos' : 'neg'">
                    {{ t.pnl >= 0 ? '+' : '' }}{{ t.pnl?.toLocaleString() }}
                  </td>
                  <td class="reason-col">{{ reasonLabel(t.reason) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 종목별 성과 -->
        <div v-if="Object.keys(result.per_ticker).length > 0" class="per-ticker-section">
          <h4 class="trades-title">종목별 성과</h4>
          <div class="table-wrap">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>최종 자산</th>
                  <th>수익률</th>
                  <th>거래 수</th>
                  <th>승률</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(v, ticker) in result.per_ticker" :key="ticker">
                  <td class="ticker-col"><StockLink :ticker="String(ticker)" /></td>
                  <td>{{ v.final_value?.toLocaleString() }}원</td>
                  <td :class="v.total_return_pct >= 0 ? 'pos' : 'neg'">
                    {{ v.total_return_pct >= 0 ? '+' : '' }}{{ v.total_return_pct }}%
                  </td>
                  <td>{{ v.num_trades }}건</td>
                  <td>{{ v.win_rate }}%</td>
                </tr>
              </tbody>
            </table>
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
import StockLink from '@/components/StockLink.vue'

const route = useRoute()
const strategyId = route.params.id

const INDICATORS = [
  { key: 'rsi', label: 'RSI' }, { key: 'macd', label: 'MACD' },
  { key: 'macd_signal', label: 'MACD Signal' }, { key: 'macd_histogram', label: 'MACD Histogram' },
  { key: 'stoch_k', label: 'Stoch %K' }, { key: 'stoch_d', label: 'Stoch %D' },
  { key: 'bollinger_upper', label: 'Bollinger Upper' }, { key: 'bollinger_middle', label: 'Bollinger Middle' },
  { key: 'bollinger_lower', label: 'Bollinger Lower' },
  { key: 'ma_20', label: 'MA 20' }, { key: 'ma_50', label: 'MA 50' }, { key: 'ma_200', label: 'MA 200' },
  { key: 'adx', label: 'ADX' }, { key: 'obv', label: 'OBV' },
]
const CONDITIONS = [
  { key: 'above', label: '이상 (>)' }, { key: 'below', label: '이하 (<)' },
  { key: 'between', label: '사이' }, { key: 'golden_cross', label: '골든크로스 ↑' },
  { key: 'dead_cross', label: '데드크로스 ↓' },
]
const REASONS = { stop_loss: '손절', take_profit: '익절', end_of_period: '기간종료' }

function indicatorLabel(key) { return INDICATORS.find(i => i.key === key)?.label ?? key }
function conditionLabel(key) { return CONDITIONS.find(c => c.key === key)?.label ?? key }
function reasonLabel(key) { return REASONS[key] ?? key }

const strategy = ref(null)
const running = ref(false)
const btError = ref('')
const result = ref(null)
const equityRef = ref(null)
let equityChart = null

// 기본 날짜: 1년 전 ~ 오늘
const today = new Date()
const oneYearAgo = new Date(today)
oneYearAgo.setFullYear(today.getFullYear() - 1)

const btForm = ref({
  tickersRaw: '',
  start_date: oneYearAgo.toISOString().split('T')[0],
  end_date: today.toISOString().split('T')[0],
  initial_capital: 10_000_000,
  stop_loss_pct: null,
  take_profit_pct: null,
})

const sellTrades = computed(() =>
  result.value ? result.value.trades.filter(t => t.type === 'SELL') : []
)

const summaryMetrics = computed(() => {
  if (!result.value) return []
  const s = result.value.summary
  const fmt = (v, suffix = '') => v != null ? `${v}${suffix}` : '-'
  const fmtMoney = v => v != null ? `${v.toLocaleString()}원` : '-'
  return [
    { label: '총 수익률', value: fmt(s.total_return_pct, '%'), cls: s.total_return_pct >= 0 ? 'pos' : 'neg' },
    { label: '연환산 수익률', value: fmt(s.annualized_return_pct, '%'), cls: s.annualized_return_pct >= 0 ? 'pos' : 'neg' },
    { label: '최대 낙폭', value: fmt(s.max_drawdown_pct, '%'), cls: 'neg' },
    { label: '샤프 비율', value: fmt(s.sharpe_ratio), cls: '' },
    { label: '변동성', value: fmt(s.volatility_pct, '%'), cls: '' },
    { label: '승률', value: fmt(s.win_rate, '%'), cls: '' },
    { label: '거래 수', value: fmt(s.num_trades, '건'), cls: '' },
    { label: '최종 자산', value: fmtMoney(s.final_value), cls: '' },
  ]
})

let pollTimer = null

async function runBacktest() {
  btError.value = ''
  result.value = null

  const tickers = btForm.value.tickersRaw
    .split(',').map(t => t.trim()).filter(Boolean)
  if (tickers.length === 0) { btError.value = '종목 코드를 입력하세요'; return }
  if (!btForm.value.start_date || !btForm.value.end_date) { btError.value = '날짜를 입력하세요'; return }

  running.value = true
  try {
    const payload = {
      tickers,
      start_date: btForm.value.start_date,
      end_date: btForm.value.end_date,
      initial_capital: btForm.value.initial_capital,
      stop_loss_pct: btForm.value.stop_loss_pct || null,
      take_profit_pct: btForm.value.take_profit_pct || null,
      transaction_cost: 0.003,
    }
    const { task_id } = await api.post(`/strategies/${strategyId}/backtest`, payload)
    pollResult(task_id)
  } catch (e) {
    btError.value = e.message
    running.value = false
  }
}

function pollResult(taskId) {
  if (pollTimer) clearInterval(pollTimer)
  const deadline = Date.now() + 300000
  pollTimer = setInterval(async () => {
    if (Date.now() > deadline) {
      clearInterval(pollTimer)
      running.value = false
      btError.value = '백테스트 타임아웃 (5분 초과)'
      return
    }
    try {
      const data = await api.get(`/strategies/${strategyId}/backtest/${taskId}`)
      if (data.status === 'completed') {
        clearInterval(pollTimer)
        running.value = false
        result.value = data.result
      } else if (data.status === 'failed') {
        clearInterval(pollTimer)
        running.value = false
        btError.value = `백테스트 실패: ${data.error}`
      }
    } catch {
      clearInterval(pollTimer)
      running.value = false
      btError.value = '결과 조회 중 오류가 발생했습니다'
    }
  }, 2000)
}

watch(result, (val) => {
  if (!val || !val.equity_curve.length) return
  setTimeout(() => renderEquityChart(val.equity_curve), 100)
})

function renderEquityChart(curve) {
  if (!equityRef.value) return
  import('lightweight-charts').then(({ createChart, LineSeries }) => {
    if (equityChart) equityChart.remove()
    equityChart = createChart(equityRef.value, {
      width: equityRef.value.clientWidth,
      height: 260,
      layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
      timeScale: { borderColor: '#2a2d3e', timeVisible: true },
      rightPriceScale: { borderColor: '#2a2d3e' },
    })
    const series = equityChart.addSeries(LineSeries, { color: '#4f9eff', lineWidth: 2 })
    const data = curve.map(p => ({
      time: Math.floor(new Date(p.date).getTime() / 1000),
      value: p.value,
    }))
    series.setData(data)
    equityChart.timeScale().fitContent()
  })
}

onMounted(async () => {
  try {
    strategy.value = await api.get(`/strategies/${strategyId}`)
  } catch {
    strategy.value = null
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (equityChart) equityChart.remove()
})
</script>

<style scoped>
.strategy-detail { max-width: 1000px; }

.back-link { color: #6b7280; text-decoration: none; font-size: 13px; display: inline-block; margin-bottom: 16px; }
.back-link:hover { color: #4f9eff; }

.loading { padding: 60px; text-align: center; color: #6b7280; }

.strategy-header { margin-bottom: 28px; }
.strategy-name { font-size: 24px; font-weight: 700; margin-bottom: 6px; }
.strategy-desc { color: #6b7280; font-size: 14px; }

.section { margin-bottom: 32px; }
.section-title {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  margin-bottom: 14px;
}

.conditions-list { display: flex; flex-direction: column; gap: 8px; }
.condition-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
}
.cond-num {
  width: 22px; height: 22px;
  background: #1e3a5f;
  color: #4f9eff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
}
.cond-indicator { font-weight: 600; color: #e5e7eb; }
.cond-op { color: #6b7280; font-size: 13px; }
.cond-value { color: #4f9eff; font-family: monospace; }

/* 백테스트 폼 */
.bt-form {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  padding: 20px;
}
.form-row { display: flex; gap: 12px; margin-bottom: 12px; }
.field { flex: 1; }
.field label { display: block; font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.field input {
  width: 100%;
  padding: 9px 12px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 7px;
  color: #e5e7eb;
  font-size: 13px;
  box-sizing: border-box;
  outline: none;
}
.field input:focus { border-color: #4f9eff; }

.bt-error { color: #f87171; font-size: 13px; margin-bottom: 12px; }
.run-btn {
  padding: 10px 28px;
  background: #4f9eff;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.run-btn:hover:not(:disabled) { background: #3b8af0; }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 결과 섹션 */
.result-section { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 10px; padding: 24px; }
.result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }

.grade-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 28px;
  font-weight: 900;
}
.grade-S { background: #1a2f1a; color: #4ade80; border: 1px solid #22c55e; }
.grade-A { background: #1e3a5f; color: #4f9eff; border: 1px solid #3b82f6; }
.grade-B { background: #2a2000; color: #fbbf24; border: 1px solid #f59e0b; }
.grade-C { background: #2a1a00; color: #fb923c; border: 1px solid #f97316; }
.grade-D, .grade-F { background: #2a1010; color: #f87171; border: 1px solid #ef4444; }
.grade-score { font-size: 14px; font-weight: 400; }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.summary-card {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 14px;
}
.metric-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.metric-value { font-size: 18px; font-weight: 700; color: #e5e7eb; }

.chart-section { margin-bottom: 24px; }
.chart-title { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.chart-container {
  width: 100%;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  overflow: hidden;
}

.trades-section, .per-ticker-section { margin-top: 20px; }
.trades-title { font-size: 13px; color: #9ca3af; margin-bottom: 10px; }
.table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid #2a2d3e; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trades-table th {
  padding: 10px 12px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  border-bottom: 1px solid #2a2d3e;
  background: #0f1117;
}
.trades-table td { padding: 10px 12px; border-bottom: 1px solid #1e2130; }
.trades-table tr:last-child td { border-bottom: none; }
.trades-table tr.win td { background: rgba(74, 222, 128, 0.03); }
.trades-table tr.loss td { background: rgba(96, 165, 250, 0.05); }
.ticker-col { font-family: monospace; color: #9ca3af; }
.reason-col { color: #6b7280; }
.pos { color: #ef4444; }  /* 한국: 빨강=수익 */
.neg { color: #3b82f6; }  /* 파랑=손실 */
</style>
