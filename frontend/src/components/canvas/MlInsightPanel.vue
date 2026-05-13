<template>
  <div class="ml-insight">
    <div v-if="loading" class="state-loading">
      <span class="spinner" /> ML 인사이트 로드 중...
    </div>
    <div v-else-if="error" class="state-error" :title="error">⚠ {{ error }}</div>
    <div v-else-if="!insight?.has_data" class="state-empty">
      아직 학습 결과가 없습니다. 먼저 mlModel 노드를 실행하세요.
    </div>

    <template v-else>
      <!-- ① 헤더: 학습 메타 -->
      <div class="ins-header">
        <div class="meta-row">
          <span class="meta-item"><span class="ml-label">기준일</span><span class="ml-val">{{ insight.date }}</span></span>
          <span class="meta-item">
            <span class="ml-label">OOS 정확도</span>
            <span class="ml-val" :class="oosClass">{{ insight.oos_accuracy ?? '—' }}%</span>
          </span>
          <span class="meta-item"><span class="ml-label">학습 샘플</span><span class="ml-val">{{ insight.train_samples?.toLocaleString() }}</span></span>
          <span class="meta-item"><span class="ml-label">매수율</span><span class="ml-val">{{ insight.positive_rate }}%</span></span>
          <span class="meta-item"><span class="ml-label">종목</span><span class="ml-val">{{ insight.ticker_count }}</span></span>
        </div>
      </div>

      <!-- ② 시장 진단 -->
      <div class="ins-section">
        <div class="sec-title">📊 시장 진단</div>
        <ul class="regime-list">
          <li v-for="(line, i) in insight.regime_summary" :key="i">{{ line }}</li>
        </ul>
      </div>

      <!-- ③ 시장 핵심 피처 (top 3) -->
      <div class="ins-section">
        <div class="sec-title">🎯 시장 전반 핵심 피처</div>
        <div class="driver-chips">
          <span v-for="d in insight.top_drivers_market" :key="d" class="chip chip-driver">{{ d }}</span>
        </div>
      </div>

      <!-- ④ Feature importance 바차트 -->
      <div class="ins-section">
        <div class="sec-title">🧬 피처 중요도 (13개)</div>
        <div class="bars">
          <div v-for="f in insight.feature_importance" :key="f.indicator" class="bar-row">
            <span class="bar-label">{{ featureLabel(f.indicator) }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(f.importance_pct) }" />
            </div>
            <span class="bar-val">{{ f.importance_pct }}%</span>
          </div>
        </div>
      </div>

      <!-- ⑤ Top 종목 인사이트 카드 -->
      <div class="ins-section">
        <div class="sec-title">🏆 Top {{ insight.ticker_insights.length }} 종목 인사이트</div>
        <div v-if="!insight.ticker_insights.length" class="state-empty">종목 데이터 없음</div>
        <div v-else class="ticker-grid">
          <div v-for="ti in insight.ticker_insights" :key="ti.ticker" class="ticker-card">
            <div class="tc-head">
              <span class="tc-ticker">{{ ti.ticker }}</span>
              <span class="tc-score" :class="scoreClass(ti.score)">{{ ti.score.toFixed(1) }}</span>
            </div>
            <div class="tc-summary">{{ ti.summary }}</div>
            <div class="tc-drivers">
              <div v-for="d in ti.top_drivers" :key="d.name" class="tc-driver">
                <span class="tc-d-name">{{ d.label }}</span>
                <span class="tc-d-z" :class="d.z_score >= 0 ? 'pos' : 'neg'">z={{ formatZ(d.z_score) }}</span>
                <span class="tc-d-imp">imp {{ d.importance_pct }}%</span>
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
  font-size: 12px;
  color: #d1d5db;
}

.state-loading, .state-error, .state-empty {
  padding: 12px;
  background: #1f2330;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  text-align: center;
  color: #9ca3af;
}
.state-error { color: #ef4444; }
.spinner {
  display: inline-block;
  width: 10px; height: 10px;
  border: 2px solid #4f9eff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

.ins-header {
  background: #1f2330;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.ml-label { font-size: 10px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; }
.ml-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.ml-val.high { color: #10b981; }
.ml-val.mid  { color: #f59e0b; }
.ml-val.low  { color: #ef4444; }

.ins-section {
  margin-bottom: 12px;
}
.sec-title {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 600;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.regime-list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: #1f2330;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
}
.regime-list li {
  padding: 8px 12px;
  border-bottom: 1px solid #2a2d3e;
  color: #d1d5db;
  line-height: 1.4;
}
.regime-list li:last-child { border-bottom: none; }

.driver-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 11px;
  border: 1px solid #2a2d3e;
}
.chip-driver { background: rgba(79, 158, 255, 0.1); color: #93c5fd; border-color: rgba(79, 158, 255, 0.3); }

.bars { display: flex; flex-direction: column; gap: 4px; }
.bar-row {
  display: grid;
  grid-template-columns: 130px 1fr 44px;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.bar-label { color: #d1d5db; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track {
  height: 8px;
  background: #161922;
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f9eff, #93c5fd);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.bar-val { text-align: right; color: #9ca3af; font-variant-numeric: tabular-nums; }

.ticker-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
.ticker-card {
  background: #1f2330;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  padding: 10px;
}
.tc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.tc-ticker { font-weight: 600; color: #e5e7eb; font-size: 13px; font-variant-numeric: tabular-nums; }
.tc-score {
  font-weight: 700;
  font-size: 14px;
  padding: 2px 8px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}
.tc-score.high { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tc-score.mid  { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.tc-score.low  { background: rgba(156, 163, 175, 0.15); color: #9ca3af; }

.tc-summary {
  font-size: 11px;
  color: #d1d5db;
  margin-bottom: 8px;
  line-height: 1.4;
}

.tc-drivers { display: flex; flex-direction: column; gap: 3px; }
.tc-driver {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  padding: 3px 0;
}
.tc-d-name { color: #d1d5db; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tc-d-z {
  font-variant-numeric: tabular-nums;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.tc-d-z.pos { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }
.tc-d-z.neg { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; }
.tc-d-imp { color: #9ca3af; font-variant-numeric: tabular-nums; }
</style>
