<template>
  <div class="bot-canvas" v-if="!loading">
    <!-- 현재 전략 요약 -->
    <div class="canvas-summary">
      <div class="summary-block">
        <div class="block-title">
          <span>📋 strategy.conditions</span>
          <span class="block-count">{{ conditionsCount }}건</span>
        </div>
        <div v-if="conditionsCount === 0" class="block-empty">
          조건이 없습니다. AI 어시스턴트에게 도움을 요청하거나 노드 편집기를 사용하세요.
        </div>
        <table v-else class="conditions-table">
          <thead>
            <tr><th>지표</th><th>조건</th><th>값</th></tr>
          </thead>
          <tbody>
            <tr v-for="(c, i) in strategy.conditions" :key="i">
              <td class="indicator">{{ c.indicator }}</td>
              <td>{{ c.condition }}</td>
              <td>{{ formatValue(c) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="summary-block">
        <div class="block-title">
          <span>⚙️ risk_params</span>
        </div>
        <table class="risk-table">
          <tbody>
            <tr v-for="(v, k) in riskParams" :key="k">
              <td class="rk-key">{{ riskLabel(k) }}</td>
              <td class="rk-val">{{ v }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 다음 단계 안내 -->
    <div class="placeholder-area">
      <p class="ph-title">🚧 Phase 2A 스켈레톤</p>
      <ul>
        <li>Phase 2B — AI 대화 패널 + diff 미리보기 + [적용]/[되돌리기]</li>
        <li>Phase 2C — 변경 이력 + 알림함 (제안 자동 표시)</li>
        <li>후속 — 노드 편집 UI 임베드 (기존 CanvasView에서)</li>
      </ul>
    </div>
  </div>
  <div v-else class="loading">전략 정보 불러오는 중...</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  botId: { type: Number, required: true },
})

const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const loading = ref(true)
const strategy = ref({ conditions: [], risk_params: {} })
const bot = ref(null)

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function fetchBot() {
  const res = await fetch(`${API}/bots/${props.botId}`, { headers: headers() })
  if (res.ok) bot.value = await res.json()
}

async function fetchStrategy() {
  // 봇의 strategy_id로 strategy 단건 조회. 봇 1:1 모델이라 그 봇 전용.
  if (!bot.value?.strategy_id) return
  const res = await fetch(`${API}/strategies/${bot.value.strategy_id}`, { headers: headers() })
  if (res.ok) strategy.value = await res.json()
}

async function load() {
  loading.value = true
  await fetchBot()
  await fetchStrategy()
  loading.value = false
}

const conditionsCount = computed(() => strategy.value?.conditions?.length || 0)

const _RISK_KEYS = [
  'stop_loss_pct', 'take_profit_pct', 'max_drawdown_pct',
  'position_size_pct', 'max_positions', 'max_daily_trades',
  'trailing_stop_pct', 'confirm_bars',
]

const riskParams = computed(() => {
  if (!bot.value) return {}
  const r = {}
  for (const k of _RISK_KEYS) {
    const v = bot.value[k]
    if (v !== null && v !== undefined) r[k] = v
  }
  return r
})

function riskLabel(k) {
  return {
    stop_loss_pct: '손절 %',
    take_profit_pct: '익절 %',
    max_drawdown_pct: '최대낙폭 %',
    position_size_pct: '포지션 크기 %',
    max_positions: '최대 보유 종목',
    max_daily_trades: '일 최대 거래',
    trailing_stop_pct: '트레일링 스탑 %',
    confirm_bars: '연속 확인 봉',
  }[k] || k
}

function formatValue(c) {
  if (c.condition === 'between') return `${c.value} ~ ${c.value2}`
  return String(c.value ?? '')
}

watch(() => props.botId, () => load())
onMounted(() => load())
</script>

<style scoped>
.bot-canvas {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 0;
}

.canvas-summary {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.summary-block {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 16px;
}

.block-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #e5e7eb;
  font-weight: 600;
  margin-bottom: 12px;
}

.block-count {
  color: #9ca3af;
  font-weight: normal;
  font-size: 13px;
}

.block-empty {
  color: #6b7280;
  font-size: 13px;
  padding: 8px 0;
}

.conditions-table, .risk-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.conditions-table th,
.conditions-table td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: #d1d5db;
}

.conditions-table th {
  color: #9ca3af;
  font-weight: normal;
  font-size: 12px;
}

.conditions-table .indicator {
  color: #4f9eff;
  font-family: monospace;
}

.risk-table td {
  padding: 6px 0;
  color: #d1d5db;
}

.risk-table .rk-key {
  color: #9ca3af;
  font-size: 12px;
}

.risk-table .rk-val {
  text-align: right;
  font-family: monospace;
  color: #e5e7eb;
}

.placeholder-area {
  background: rgba(79, 158, 255, 0.05);
  border: 1px dashed rgba(79, 158, 255, 0.3);
  border-radius: 8px;
  padding: 16px;
  color: #9ca3af;
}

.ph-title {
  margin: 0 0 8px 0;
  color: #4f9eff;
  font-size: 13px;
  font-weight: 600;
}

.placeholder-area ul {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.7;
}

.loading {
  color: #6b7280;
  text-align: center;
  padding: 40px;
}
</style>
