<template>
  <div
    class="flow-node"
    :class="[`cat-${data.category}`, `st-${data.status || 'idle'}`, { selected }]"
    @click.stop="selectNode(id)"
  >
    <!-- Input handles (left) -->
    <Handle
      v-for="(h, i) in data.inputs || []"
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
      <span class="status-dot" :class="data.status || 'idle'"></span>
    </div>

    <!-- Body -->
    <div class="node-body">
      <div v-if="data.status === 'running'" class="body-running">
        <span class="mini-spinner"></span>
        <span>실행 중...</span>
      </div>
      <div
        v-else-if="data.status === 'error'"
        class="body-error"
        :title="data.error"
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
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <span>{{ data.error || '오류 발생' }}</span>
      </div>
      <div v-else-if="data.status === 'success' && data.result" class="body-result">
        <div v-for="(val, key) in previewResult" :key="key" class="result-row">
          <span class="rk">{{ key }}</span>
          <span class="rv">{{ val }}</span>
        </div>
      </div>
      <div v-else-if="isKnowledgeNode" class="body-kb">
        <div v-if="data.config.summary" class="kb-summary">{{ data.config.summary }}</div>
        <div v-else class="kb-summary kb-summary-empty">
          {{ data.config.kb_status === 'pending' ? '분석 대기 중…'
             : data.config.kb_status === 'ingesting' ? '본문 추출·요약 중…'
             : '요약 없음' }}
        </div>
        <div v-if="data.config.mentioned_tickers && data.config.mentioned_tickers.length"
             class="kb-tickers">
          <span v-for="t in data.config.mentioned_tickers.slice(0, 8)" :key="t"
                class="kb-ticker-chip">{{ t }}</span>
          <span v-if="data.config.mentioned_tickers.length > 8" class="kb-ticker-more">
            +{{ data.config.mentioned_tickers.length - 8 }}
          </span>
        </div>
      </div>
      <div v-else-if="conditionRows.length" class="body-config">
        <div v-for="(c, i) in conditionRows" :key="i" class="cfg-row">
          <span class="cfg-key">{{ c.indicator }}</span>
          <span class="cfg-val">{{ c.summary }}</span>
        </div>
      </div>
      <div v-else-if="configRows.length" class="body-config">
        <div v-for="r in configRows" :key="r.key" class="cfg-row">
          <span class="cfg-key">{{ r.label }}</span>
          <span class="cfg-val">{{ r.value }}</span>
        </div>
      </div>
      <div v-else class="body-idle">{{ data.description }}</div>
    </div>

    <!-- Footer -->
    <div class="node-footer">
      <button
        class="run-btn"
        type="button"
        :class="{ running: data.status === 'running' }"
        :disabled="data.status === 'running'"
        @click.stop="runNode(id)"
      >
        <svg
          v-if="data.status !== 'running'"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <polygon points="6 4 20 12 6 20 6 4" />
        </svg>
        <span>{{
          data.status === 'running'
            ? '...'
            : data.status === 'success'
              ? '재실행'
              : '실행'
        }}</span>
      </button>
    </div>

    <!-- Output handles (right) -->
    <Handle
      v-for="(h, i) in data.outputs || []"
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

const runNode = inject('runNode')
const selectNode = inject('selectNode')

function handlePos(idx, total) {
  const pct = total === 1 ? 50 : ((idx + 1) / (total + 1)) * 100
  return { top: `${pct}%` }
}

const PREVIEW_MAP = {
  news_count: '뉴스',
  kospi: 'KOSPI',
  vix: 'VIX',
  ticker_count: '종목수',
  latest_date: '기준일',
  avg_rsi: '평균RSI',
  top_tickers: 'ML상위',
  train_samples: '학습샘플',
  positive_rate: '매수율',
  tickers_count: '종목수(백테)',
  strategy_name: '전략명',
  confidence: '신뢰도',
  risk_level: '위험',
  strategy_id: '전략ID',
  total_return_pct: '수익률',
  win_rate: '승률',
  num_trades: '거래수',
  bot_name: '봇',
  account_label: '계좌',
}

const conditionRows = computed(() => {
  const conds = props.data?.config?.conditions
  if (!Array.isArray(conds)) return []
  return conds.map((c) => ({
    indicator: c.indicator,
    summary:
      c.condition === 'between'
        ? `${c.value} ~ ${c.value2}`
        : `${c.condition} ${c.value ?? ''}`.trim(),
  }))
})

// KB 노드는 outputs 첫 핸들이 'kb_tickers' — 충돌 안전
const isKnowledgeNode = computed(() => {
  return props.data?.outputs?.[0]?.id === 'kb_tickers'
})

const _CFG_LABELS = {
  stop_loss_pct: '손절',
  take_profit_pct: '익절',
  max_drawdown_pct: 'MDD',
  position_size_pct: '포지션',
  max_positions: '최대 종목',
  max_daily_trades: '일 거래',
  trailing_stop_pct: '트레일링',
  confirm_bars: '확인봉',
  bot_id: '봇 ID',
  auto_start: '자동시작',
  account_id: '계좌',
  mode: '모드',
  name: '이름',
  strategy_type: '타입',
  saved_id: '전략 ID',
  tickers_source: '종목소스',
}

const configRows = computed(() => {
  const cfg = props.data?.config
  if (!cfg || typeof cfg !== 'object') return []
  return Object.entries(cfg)
    .filter(([k, v]) => k !== 'conditions' && v !== null && v !== undefined && v !== '')
    .slice(0, 8)
    .map(([k, v]) => ({
      key: k,
      label: _CFG_LABELS[k] || k,
      value: typeof v === 'boolean' ? (v ? '예' : '아니오') : String(v),
    }))
})

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
  width: 240px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--glass-bg-strong);
  backdrop-filter: blur(8px) saturate(140%);
  -webkit-backdrop-filter: blur(8px) saturate(140%);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  user-select: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.flow-node.selected {
  box-shadow: 0 0 0 2px var(--accent-border);
  border-color: var(--accent);
}

/* ==========================================================================
   Category accents (top border)
   ========================================================================== */

.flow-node.cat-source {
  border-top: 2px solid var(--info);
}
.flow-node.cat-strategy {
  border-top: 2px solid var(--accent);
}
.flow-node.cat-processing {
  border-top: 2px solid var(--violet);
}
.flow-node.cat-output {
  border-top: 2px solid var(--up-strong);
}
.flow-node.cat-config {
  border-top: 2px solid var(--accent-dim);
}

/* ==========================================================================
   Status glows
   ========================================================================== */

.flow-node.st-running {
  box-shadow: 0 0 14px rgba(96, 165, 250, 0.35);
}

.flow-node.st-success {
  border-color: rgba(34, 197, 94, 0.35);
}

.flow-node.st-error {
  border-color: rgba(239, 68, 68, 0.35);
}

/* ==========================================================================
   Header
   ========================================================================== */

.node-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) 7px;
  border-bottom: 1px solid var(--border-faint);
}

.node-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.node-title {
  flex: 1;
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.status-dot.idle {
  background: var(--text-faint);
}

.status-dot.running {
  background: var(--info);
  animation: nodePulse 1s infinite;
}

.status-dot.success {
  background: var(--up-strong);
  box-shadow: 0 0 6px var(--up-strong);
}

.status-dot.error {
  background: var(--profit);
  box-shadow: 0 0 6px var(--profit);
}

@keyframes nodePulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

/* ==========================================================================
   Body
   ========================================================================== */

.node-body {
  padding: var(--space-2) var(--space-3);
  min-height: 46px;
  display: flex;
  align-items: flex-start;
}

.body-idle {
  color: var(--text-muted);
  font-size: 11px;
  line-height: var(--leading-snug);
}

.body-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  color: var(--profit);
  font-size: 11px;
  line-height: var(--leading-snug);
}

.body-error svg {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  margin-top: 1px;
}

.body-error span {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.body-running {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--info);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: var(--tracking-wide);
}

.mini-spinner {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border: 2px solid var(--border);
  border-top-color: var(--info);
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.body-result,
.body-config {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.body-kb {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kb-summary {
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-secondary);
  max-height: 64px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.kb-summary-empty { color: var(--text-muted); font-style: italic; }
.kb-tickers {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 2px;
}
.kb-ticker-chip {
  padding: 1px 5px;
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: 3px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
}
.kb-ticker-more {
  padding: 1px 5px;
  color: var(--text-muted);
  font-size: 9px;
}

.result-row,
.cfg-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-2);
}

.rk,
.cfg-key {
  color: var(--text-muted);
  font-size: 10px;
  flex-shrink: 0;
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wide);
}

.cfg-key {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rv,
.cfg-val {
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 130px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* ==========================================================================
   Footer
   ========================================================================== */

.node-footer {
  padding: 6px var(--space-2) 8px;
  border-top: 1px solid var(--border-faint);
}

.run-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  padding: 5px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.run-btn svg {
  width: 9px;
  height: 9px;
}

.run-btn:hover:not(:disabled) {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.run-btn.running,
.run-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ==========================================================================
   Handles
   ========================================================================== */

.flow-handle {
  width: 10px !important;
  height: 10px !important;
  border-radius: 50% !important;
  border: 2px solid rgba(20, 24, 34, 0.95) !important;
}

.handle-in {
  background: rgba(96, 165, 250, 0.85) !important;
  left: -5px !important;
}

.handle-out {
  background: rgba(167, 139, 250, 0.85) !important;
  right: -5px !important;
}

.cat-output .handle-in {
  background: rgba(34, 197, 94, 0.85) !important;
}

.handle-label {
  position: absolute;
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--text-tertiary);
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--dur-fast) var(--ease-out);
  background: var(--glass-bg-strong);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.flow-handle:hover .handle-label {
  opacity: 1;
}

.handle-label-in {
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
}

.handle-label-out {
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
}
</style>
