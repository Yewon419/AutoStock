<template>
  <div class="ml-insight">
    <div v-if="loading" class="state-box state-loading">
      <span class="spinner"></span>
      <span>ML 인사이트 로드 중...</span>
    </div>
    <div v-else-if="error" class="state-box state-error" :title="error">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span>{{ error }}</span>
    </div>
    <div v-else-if="!insight?.has_data" class="state-box state-empty">
      아직 학습 결과가 없습니다. 먼저 mlModel 노드를 실행하세요.
    </div>

    <template v-else>
      <!-- ① 헤더 -->
      <div class="ins-header">
        <div class="meta-row">
          <div class="meta-item">
            <span class="ml-label">기준일</span>
            <span class="ml-val mono">{{ insight.date }}</span>
          </div>
          <div class="meta-item">
            <span class="ml-label">OOS 정확도</span>
            <span class="ml-val mono" :class="oosClass">
              {{ insight.oos_accuracy ?? '—' }}%
            </span>
          </div>
          <div class="meta-item">
            <span class="ml-label">학습 샘플</span>
            <span class="ml-val mono">
              {{ insight.train_samples?.toLocaleString() }}
            </span>
          </div>
          <div class="meta-item">
            <span class="ml-label">매수율</span>
            <span class="ml-val mono">{{ insight.positive_rate }}%</span>
          </div>
          <div class="meta-item">
            <span class="ml-label">종목</span>
            <span class="ml-val mono">{{ insight.ticker_count }}</span>
          </div>
        </div>
      </div>

      <!-- ② 시장 진단 -->
      <div class="ins-section">
        <div class="sec-title">REGIME · 시장 진단</div>
        <ul class="regime-list">
          <li v-for="(line, i) in insight.regime_summary" :key="i">{{ line }}</li>
        </ul>
      </div>

      <!-- ③ 시장 핵심 피처 -->
      <div class="ins-section">
        <div class="sec-title">DRIVERS · 시장 전반 핵심 피처</div>
        <div class="driver-chips">
          <span
            v-for="d in insight.top_drivers_market"
            :key="d"
            class="chip chip-driver"
          >{{ d }}</span>
        </div>
      </div>

      <!-- ④ Feature importance -->
      <div class="ins-section">
        <div class="sec-title">FEATURES · 피처 중요도 (13)</div>
        <div class="bars">
          <div
            v-for="f in insight.feature_importance"
            :key="f.indicator"
            class="bar-row"
          >
            <span class="bar-label">{{ featureLabel(f.indicator) }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(f.importance_pct) }"></div>
            </div>
            <span class="bar-val mono">{{ f.importance_pct }}%</span>
          </div>
        </div>
      </div>

      <!-- ⑤ Top 종목 인사이트 -->
      <div class="ins-section">
        <div class="sec-title">
          TICKERS · Top {{ insight.ticker_insights.length }} 인사이트
        </div>
        <div v-if="!insight.ticker_insights.length" class="state-box state-empty">
          종목 데이터 없음
        </div>
        <div v-else class="ticker-grid">
          <div
            v-for="ti in insight.ticker_insights"
            :key="ti.ticker"
            class="ticker-card"
          >
            <div class="tc-head">
              <span class="tc-ticker">{{ ti.ticker }}</span>
              <span class="tc-score" :class="scoreClass(ti.score)">
                {{ ti.score.toFixed(1) }}
              </span>
            </div>
            <div class="tc-summary">{{ ti.summary }}</div>
            <div class="tc-drivers">
              <div
                v-for="d in ti.top_drivers"
                :key="d.name"
                class="tc-driver"
              >
                <span class="tc-d-name">{{ d.label }}</span>
                <span class="tc-d-z mono" :class="d.z_score >= 0 ? 'pos' : 'neg'">
                  z={{ formatZ(d.z_score) }}
                </span>
                <span class="tc-d-imp mono">imp {{ d.importance_pct }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'

const props = defineProps({
  apiBase: { type: String, required: true },
  authToken: { type: String, required: true },
  topN: { type: Number, default: 20 },
})

const insight = ref(null)
const loading = ref(false)
const error = ref(null)

const FEATURE_LABELS = {
  RSI: 'RSI',
  MACD_hist_norm: 'MACD 히스토그램',
  Stoch_K: 'Stochastic %K',
  Stoch_D: 'Stochastic %D',
  ADX: 'ADX (추세 강도)',
  MA20_MA50: 'MA20/MA50 비율',
  ATR_norm: 'ATR 정규화 변동성',
  Boll_pos: '볼린저밴드 위치',
  RSI_3d_delta: 'RSI 3일 변화',
  MACD_hist_slope: 'MACD 5일 기울기',
  Vol_ratio: '거래량 / 20일 평균',
  Price_vs_MA20: 'MA20 대비 종가 (%)',
  BB_squeeze: '볼린저밴드 수축도',
}

function featureLabel(name) {
  return FEATURE_LABELS[name] || name
}

const maxImportance = computed(() => {
  const arr = insight.value?.feature_importance || []
  return arr.reduce((m, f) => Math.max(m, f.importance_pct), 0) || 1
})

function barWidth(pct) {
  return `${(pct / maxImportance.value) * 100}%`
}

function formatZ(z) {
  return (z >= 0 ? '+' : '') + z.toFixed(2)
}

function scoreClass(score) {
  if (score >= 60) return 'high'
  if (score >= 40) return 'mid'
  return 'low'
}

const oosClass = computed(() => {
  const v = insight.value?.oos_accuracy
  if (v == null) return ''
  if (v >= 60) return 'high'
  if (v >= 55) return 'mid'
  return 'low'
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`${props.apiBase}/ai/ml-insight?top_n=${props.topN}`, {
      headers: { Authorization: `Bearer ${props.authToken}` },
    })
    if (!res.ok) throw new Error(await res.text())
    insight.value = await res.json()
  } catch (e) {
    error.value = e.message || 'ML 인사이트 로드 실패'
  } finally {
    loading.value = false
  }
}

defineExpose({ reload: load })

onMounted(load)
</script>

<style scoped>
.ml-insight {
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--tracking-wide);
}

/* ==========================================================================
   State boxes (loading / error / empty)
   ========================================================================== */

.state-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.state-error {
  color: var(--profit);
  background: var(--profit-bg);
  border-color: rgba(239, 68, 68, 0.3);
}

.state-error svg {
  width: 14px;
  height: 14px;
}

.spinner {
  display: inline-block;
  width: 11px;
  height: 11px;
  border: 2px solid var(--accent);
  border-top-color: transparent;
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ==========================================================================
   Header (meta)
   ========================================================================== */

.ins-header {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-5);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 80px;
}

.ml-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
  font-weight: 500;
}

.ml-val {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
}

.ml-val.high {
  color: var(--up-strong);
}
.ml-val.mid {
  color: var(--accent);
}
.ml-val.low {
  color: var(--profit);
}

/* ==========================================================================
   Section
   ========================================================================== */

.ins-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sec-title {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

/* ==========================================================================
   Regime list
   ========================================================================== */

.regime-list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.regime-list li {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-faint);
  color: var(--text-secondary);
  line-height: var(--leading-snug);
  font-size: var(--text-xs);
}

.regime-list li:last-child {
  border-bottom: none;
}

/* ==========================================================================
   Driver chips
   ========================================================================== */

.driver-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.chip {
  display: inline-block;
  padding: 4px var(--space-3);
  border-radius: var(--radius-full);
  font-family: var(--font-mono);
  font-size: 10.5px;
  border: 1px solid;
  letter-spacing: var(--tracking-wide);
  font-weight: 600;
}

.chip-driver {
  background: rgba(96, 165, 250, 0.1);
  color: var(--info);
  border-color: rgba(96, 165, 250, 0.3);
}

/* ==========================================================================
   Bar chart (feature importance)
   ========================================================================== */

.bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.bar-row {
  display: grid;
  grid-template-columns: 130px 1fr 48px;
  align-items: center;
  gap: var(--space-2);
  font-size: 11px;
}

.bar-label {
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  height: 7px;
  background: var(--bg-base);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--info), rgba(96, 165, 250, 0.6));
  border-radius: var(--radius-xs);
  transition: width var(--dur-slow) var(--ease-out);
}

.bar-val {
  text-align: right;
  color: var(--text-muted);
}

/* ==========================================================================
   Ticker cards
   ========================================================================== */

.ticker-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
}

.ticker-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  transition: border-color var(--dur-fast) var(--ease-out);
}

.ticker-card:hover {
  border-color: var(--border-strong);
}

.tc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.tc-ticker {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--tracking-wide);
}

.tc-score {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: var(--text-md);
  padding: 3px 9px;
  border-radius: var(--radius-xs);
  font-variant-numeric: tabular-nums;
}

.tc-score.high {
  background: var(--up-bg);
  color: var(--up-strong);
}

.tc-score.mid {
  background: var(--accent-bg);
  color: var(--accent);
}

.tc-score.low {
  background: var(--surface-2);
  color: var(--text-muted);
}

.tc-summary {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
  line-height: var(--leading-snug);
}

.tc-drivers {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.tc-driver {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: var(--space-2);
  align-items: center;
  font-size: 11px;
  padding: 3px 0;
}

.tc-d-name {
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tc-d-z {
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-weight: 600;
}

.tc-d-z.pos {
  background: var(--profit-bg);
  color: var(--profit-soft);
}

.tc-d-z.neg {
  background: var(--loss-bg);
  color: var(--loss-soft);
}

.tc-d-imp {
  color: var(--text-muted);
}
</style>
