<template>
  <div
    class="flow-node"
    :class="[`cat-${data.category}`, `st-${data.status || 'idle'}`, { selected }]"
    @click.stop="selectNode(id)"
  >
    <!-- Input handles (left) -->
    <Handle
      v-for="(h, i) in (data.inputs || [])"
      :key="`in-${h.id}`"
      type="target"
      :position="Position.Left"
      :id="h.id"
      :style="handlePos(i, data.inputs.length)"
      class="flow-handle handle-in"
    >
      <div class="handle-label handle-label-in">{{ h.label }}</div>
    </Handle>

    <!-- Header -->
    <div class="node-header">
      <span class="node-icon">{{ data.icon }}</span>
      <span class="node-title">{{ data.label }}</span>
      <span class="status-dot" :class="data.status || 'idle'" />
    </div>

    <!-- Body -->
    <div class="node-body">
      <div v-if="data.status === 'running'" class="body-running">
        <div class="mini-spinner" />
        <span>실행 중...</span>
      </div>
      <div v-else-if="data.status === 'error'" class="body-error" :title="data.error">
        ⚠ {{ data.error || '오류 발생' }}
      </div>
      <div v-else-if="data.status === 'success' && data.result" class="body-result">
        <div v-for="(val, key) in previewResult" :key="key" class="result-row">
          <span class="rk">{{ key }}</span>
          <span class="rv">{{ val }}</span>
        </div>
      </div>
      <div v-else class="body-idle">{{ data.description }}</div>
    </div>

    <!-- Footer -->
    <div class="node-footer">
      <button
        class="run-btn"
        :class="{ running: data.status === 'running' }"
        @click.stop="runNode(id)"
        :disabled="data.status === 'running'"
      >
        {{ data.status === 'running' ? '...' : data.status === 'success' ? '재실행' : '▶ 실행' }}
      </button>
    </div>

    <!-- Output handles (right) -->
    <Handle
      v-for="(h, i) in (data.outputs || [])"
      :key="`out-${h.id}`"
      type="source"
      :position="Position.Right"
      :id="h.id"
      :style="handlePos(i, data.outputs.length)"
      class="flow-handle handle-out"
    >
      <div class="handle-label handle-label-out">{{ h.label }}</div>
    </Handle>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps(['id', 'data', 'selected'])

const runNode    = inject('runNode')
const selectNode = inject('selectNode')

function handlePos(idx, total) {
  const pct = total === 1 ? 50 : ((idx + 1) / (total + 1)) * 100
  return { top: `${pct}%` }
}

const PREVIEW_MAP = {
  news_count: '뉴스', kospi: 'KOSPI', vix: 'VIX',
  ticker_count: '종목수', latest_date: '기준일', avg_rsi: '평균RSI',
  top_tickers: 'ML상위', train_samples: '학습샘플', positive_rate: '매수율', tickers_count: '종목수(백테)',
  strategy_name: '전략명', confidence: '신뢰도', risk_level: '위험', strategy_id: '전략ID',
  total_return_pct: '수익률', win_rate: '승률', num_trades: '거래수',
  bot_name: '봇', account_label: '계좌',
}

const previewResult = computed(() => {
  const r = props.data?.result
  if (!r) return {}
  const out = {}
  let count = 0
  for (const [k, label] of Object.entries(PREVIEW_MAP)) {
    if (r[k] !== undefined && count < 3) {
      let v = r[k]
      if (typeof v === 'number') {
        if (k.includes('pct') || k === 'win_rate' || k === 'positive_rate') v = v.toFixed(1) + '%'
        else if (k === 'confidence') v = v + '%'
        else if (k === 'train_samples') v = v.toLocaleString()
      }
      if (Array.isArray(v)) v = v.slice(0, 3).join(', ')
      out[label] = v
      count++
    }
  }
  return out
})
</script>

<style scoped>
.flow-node {
  width: 220px;
  border-radius: 10px;
  border: 1.5px solid #2a2d3e;
  background: #1a1d27;
  font-size: 12px;
  user-select: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  position: relative;
}

.flow-node.selected {
  box-shadow: 0 0 0 2px rgba(79, 158, 255, 0.5);
  border-color: #4f9eff;
}

/* Category top border */
.flow-node.cat-source     { border-top: 3px solid #0891b2; }
.flow-node.cat-strategy   { border-top: 3px solid #d97706; }
.flow-node.cat-processing { border-top: 3px solid #7c3aed; }
.flow-node.cat-output     { border-top: 3px solid #059669; }
.flow-node.cat-config     { border-top: 3px solid #b45309; }

/* Status glow */
.flow-node.st-running { box-shadow: 0 0 14px rgba(79, 158, 255, 0.35); }
.flow-node.st-success { border-color: rgba(16, 185, 129, 0.35); }
.flow-node.st-error   { border-color: rgba(239, 68, 68, 0.35); }

/* ── Header ── */
.node-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 14px 8px;
  border-bottom: 1px solid #2a2d3e;
}
.node-icon  { font-size: 15px; flex-shrink: 0; }
.node-title { flex: 1; font-weight: 600; color: #e5e7eb; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Status dot */
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.status-dot.idle    { background: #374151; }
.status-dot.running { background: #4f9eff; animation: pulse 1s infinite; }
.status-dot.success { background: #10b981; }
.status-dot.error   { background: #ef4444; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

/* ── Body ── */
.node-body {
  padding: 10px 14px;
  min-height: 46px;
  display: flex;
  align-items: flex-start;
}
.body-idle {
  color: #4b5563;
  font-size: 11px;
  line-height: 1.5;
}
.body-error {
  color: #f87171;
  font-size: 11px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.body-running {
  display: flex; align-items: center; gap: 8px;
  color: #60a5fa; font-size: 11px;
}
.mini-spinner {
  width: 12px; height: 12px; flex-shrink: 0;
  border: 2px solid #2a2d3e; border-top-color: #4f9eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.body-result { width: 100%; display: flex; flex-direction: column; gap: 4px; }
.result-row  { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.rk { color: #6b7280; font-size: 10px; flex-shrink: 0; }
.rv { color: #e5e7eb; font-size: 11px; font-weight: 600; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 120px; }

/* ── Footer ── */
.node-footer {
  padding: 6px 10px 9px;
  border-top: 1px solid #2a2d3e;
}
.run-btn {
  width: 100%;
  padding: 5px 0;
  border: 1px solid #2a2d3e;
  border-radius: 5px;
  background: #0f1117;
  color: #9ca3af;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.run-btn:hover:not(:disabled) { border-color: #4f9eff; color: #4f9eff; background: rgba(79,158,255,.08); }
.run-btn.running, .run-btn:disabled { opacity: 0.45; cursor: not-allowed; }

/* ── Handles ── */
.flow-handle {
  width: 11px !important;
  height: 11px !important;
  border-radius: 50% !important;
  border: 2px solid #1a1d27 !important;
}
.handle-in  { background: #0891b2 !important; left: -6px !important; }
.handle-out { background: #7c3aed !important; right: -6px !important; }
.cat-output .handle-in { background: #059669 !important; }

/* handle label — 기본 숨김, hover 시 노드 바깥쪽에 표시 */
.handle-label {
  position: absolute;
  font-size: 9px;
  color: #6b7280;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  background: #1a1d27;
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid #2a2d3e;
}
.flow-handle:hover .handle-label { opacity: 1; }
.handle-label-in  { left: 16px;  top: 50%; transform: translateY(-50%); }
.handle-label-out { right: 16px; top: 50%; transform: translateY(-50%); }
</style>
