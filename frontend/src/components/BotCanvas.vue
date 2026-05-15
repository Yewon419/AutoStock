<template>
  <div class="bot-canvas" v-if="!loading">
    <div class="canvas-layout">
      <!-- 좌측: 현재 전략 + risk_params -->
      <div class="left-area">
        <div class="summary-block">
          <div class="block-title">
            <span>📋 strategy.conditions</span>
            <span class="block-count">{{ conditionsCount }}건</span>
          </div>
          <div v-if="conditionsCount === 0" class="block-empty">
            조건이 없습니다. 우측 AI 어시스턴트에게 도움을 요청하세요.
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
            <button class="btn-small" @click="undoLast" :disabled="undoing">
              {{ undoing ? '복원 중...' : '↶ 되돌리기' }}
            </button>
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

      <!-- 우측: AI 어시스턴트 -->
      <div class="right-area">
        <div class="assistant-block">
          <div class="block-title">
            <span>🤖 AI 튜닝 어시스턴트</span>
            <button class="btn-small" @click="autoGenerate" :disabled="generating">
              {{ generating ? '진단 중...' : '🔍 자동 진단' }}
            </button>
          </div>

          <!-- 대화 히스토리 -->
          <div class="chat-history" ref="chatHistoryEl">
            <div v-if="chatLog.length === 0" class="chat-empty">
              메시지를 보내거나 [자동 진단] 버튼을 눌러보세요.
            </div>
            <div v-for="(msg, i) in chatLog" :key="i" class="chat-msg" :class="`msg-${msg.role}`">
              <div class="msg-label">{{ msg.role === 'user' ? '나' : 'AI' }}</div>
              <div class="msg-body">{{ msg.content }}</div>
            </div>
          </div>

          <!-- 입력창 -->
          <div class="chat-input">
            <input
              v-model="userMessage"
              type="text"
              placeholder="이 봇을 어떻게 손볼지 물어보세요 (예: RSI 좀 더 보수적으로)"
              @keydown.enter="sendChat"
              :disabled="chatting"
            />
            <button @click="sendChat" :disabled="chatting || !userMessage.trim()">
              {{ chatting ? '...' : '보내기' }}
            </button>
          </div>

          <!-- 현재 제안 (diff) -->
          <div v-if="currentProposal" class="proposal">
            <div class="proposal-title">📝 변경 제안</div>
            <div v-if="currentProposal.diagnosis" class="proposal-diag">
              <strong>진단:</strong> {{ currentProposal.diagnosis }}
            </div>

            <div v-if="proposedRiskDiff.length" class="diff-block">
              <div class="diff-label">risk_params 변경 ({{ proposedRiskDiff.length }}건)</div>
              <table class="diff-table">
                <thead>
                  <tr><th>항목</th><th>현재</th><th>→</th><th>제안</th></tr>
                </thead>
                <tbody>
                  <tr v-for="d in proposedRiskDiff" :key="d.key">
                    <td>{{ riskLabel(d.key) }}</td>
                    <td class="v-before">{{ d.before }}</td>
                    <td class="arrow">→</td>
                    <td class="v-after">{{ d.after }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="currentProposal.proposed_conditions !== null && currentProposal.proposed_conditions !== undefined" class="diff-block">
              <div class="diff-label">strategy.conditions 변경 ({{ currentProposal.proposed_conditions.length }}건 전체 교체)</div>
              <table class="diff-table">
                <thead>
                  <tr><th>지표</th><th>조건</th><th>값</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(c, i) in currentProposal.proposed_conditions" :key="i">
                    <td class="indicator">{{ c.indicator }}</td>
                    <td>{{ c.condition }}</td>
                    <td>{{ formatValue(c) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="proposal-actions">
              <button class="btn-apply" @click="applyProposal" :disabled="applying">
                {{ applying ? '적용 중...' : '✓ 적용' }}
              </button>
              <button class="btn-dismiss" @click="dismissProposal" :disabled="applying">
                ✗ 기각
              </button>
            </div>
          </div>

          <div v-if="errorMessage" class="error-banner">⚠ {{ errorMessage }}</div>
        </div>
      </div>
    </div>

    <!-- 알림함: pending suggestions -->
    <div class="lower-section">
      <div class="summary-block">
        <div class="block-title">
          <span>🔔 튜닝 제안함</span>
          <span class="block-count">{{ pendingSuggestions.length }}건 대기</span>
        </div>
        <div v-if="pendingSuggestions.length === 0" class="block-empty">
          대기 중인 제안이 없습니다. 매일 08:30 자동 진단이 새 제안을 드롭합니다.
        </div>
        <div v-else class="suggestions-list">
          <div v-for="s in pendingSuggestions" :key="s.id" class="suggestion-row">
            <div class="sg-header">
              <span class="sg-date">{{ fmtDate(s.created_at) }}</span>
              <div class="sg-actions">
                <button class="btn-apply-sm" @click="applySuggestion(s)" :disabled="applyingSugg === s.id">
                  {{ applyingSugg === s.id ? '...' : '✓ 적용' }}
                </button>
                <button class="btn-dismiss-sm" @click="dismissSuggestion(s)">✗ 기각</button>
              </div>
            </div>
            <div class="sg-diag">{{ s.diagnosis_text }}</div>
            <div v-if="s.suggested_risk_params" class="sg-diff">
              risk_params: {{ JSON.stringify(s.suggested_risk_params) }}
            </div>
            <div v-if="s.suggested_conditions" class="sg-diff">
              conditions: {{ s.suggested_conditions.length }}건
            </div>
          </div>
        </div>
      </div>

      <!-- 변경 이력 -->
      <div class="summary-block">
        <div class="block-title">
          <span>📜 변경 이력</span>
          <span class="block-count">{{ history.length }}건</span>
        </div>
        <div v-if="history.length === 0" class="block-empty">
          변경 이력이 없습니다.
        </div>
        <div v-else class="history-list">
          <div v-for="h in history" :key="h.id" class="history-row">
            <div class="hist-header">
              <span class="hist-date">{{ fmtDate(h.applied_at) }}</span>
              <span class="hist-source" :class="`src-${h.source}`">{{ h.source }}</span>
            </div>
            <div v-if="h.llm_reasoning" class="hist-reason">{{ h.llm_reasoning }}</div>
            <div class="hist-diff">
              <span v-if="h.before_risk_params && h.after_risk_params">risk_params 변경</span>
              <span v-if="h.before_conditions !== null && h.after_conditions !== null">conditions 변경</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 노드 편집기 (기존 CanvasView 임베드) -->
    <div class="flow-section">
      <div class="flow-header">
        <span>🎨 노드 편집기</span>
        <button class="btn-small" @click="showFlow = !showFlow">
          {{ showFlow ? '접기 ▲' : '펼치기 ▼' }}
        </button>
      </div>
      <div v-show="showFlow" class="flow-container">
        <CanvasView :bot-id="botId" />
      </div>
    </div>
  </div>
  <div v-else class="loading">전략 정보 불러오는 중...</div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CanvasView from '@/views/CanvasView.vue'

const props = defineProps({
  botId: { type: Number, required: true },
})

const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const loading = ref(true)
const strategy = ref({ conditions: [], risk_params: {} })
const bot = ref(null)

const userMessage = ref('')
const chatLog = ref([])  // [{role: 'user'|'assistant', content: str}]
const currentProposal = ref(null)  // 마지막 LLM 응답
const chatting = ref(false)
const generating = ref(false)
const applying = ref(false)
const undoing = ref(false)
const errorMessage = ref('')
const chatHistoryEl = ref(null)
const history = ref([])
const pendingSuggestions = ref([])
const applyingSugg = ref(null)
const showFlow = ref(true)  // 노드 편집기 펼침 (기본 펼침)

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

function jsonHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function fetchBot() {
  const res = await fetch(`${API}/bots/${props.botId}`, { headers: headers() })
  if (res.ok) bot.value = await res.json()
}

async function fetchStrategy() {
  if (!bot.value?.strategy_id) return
  const res = await fetch(`${API}/strategies/${bot.value.strategy_id}`, { headers: headers() })
  if (res.ok) strategy.value = await res.json()
}

async function fetchHistory() {
  const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/history?limit=20`, { headers: headers() })
  if (res.ok) history.value = await res.json()
}

async function fetchSuggestions() {
  const res = await fetch(`${API}/trading/bots/${props.botId}/suggestions?status_filter=pending&limit=20`, { headers: headers() })
  if (res.ok) pendingSuggestions.value = await res.json()
}

async function load() {
  loading.value = true
  await fetchBot()
  await fetchStrategy()
  await Promise.all([fetchHistory(), fetchSuggestions()])
  loading.value = false
}

async function applySuggestion(s) {
  applyingSugg.value = s.id
  errorMessage.value = ''
  try {
    const body = {
      conditions: s.suggested_conditions,
      risk_params: s.suggested_risk_params,
      source: 'ai_suggestion',
      llm_reasoning: s.diagnosis_text,
      suggestion_id: s.id,
    }
    const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/apply-diff`, {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify(body),
    })
    await handleResponse(res)
    await load()
  } catch (e) {
    errorMessage.value = `제안 적용 실패: ${e.message}`
  } finally {
    applyingSugg.value = null
  }
}

async function dismissSuggestion(s) {
  try {
    await fetch(`${API}/trading/bots/${props.botId}/suggestions/${s.id}/dismiss`, {
      method: 'POST',
      headers: headers(),
    })
    await fetchSuggestions()
  } catch {
    /* 백그라운드 동작 */
  }
}

function fmtDate(s) {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function scrollChatToBottom() {
  await nextTick()
  if (chatHistoryEl.value) chatHistoryEl.value.scrollTop = chatHistoryEl.value.scrollHeight
}

async function handleResponse(res) {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

async function callTuning(endpoint, body) {
  errorMessage.value = ''
  const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/${endpoint}`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: body ? JSON.stringify(body) : '{}',
  })
  return handleResponse(res)
}

async function sendChat() {
  if (!userMessage.value.trim() || chatting.value) return
  const msg = userMessage.value.trim()
  chatLog.value.push({ role: 'user', content: msg })
  userMessage.value = ''
  await scrollChatToBottom()

  chatting.value = true
  try {
    const result = await callTuning('chat', { message: msg })
    chatLog.value.push({ role: 'assistant', content: result.reply })
    currentProposal.value = result
    await scrollChatToBottom()
  } catch (e) {
    errorMessage.value = `대화 실패: ${e.message}`
  } finally {
    chatting.value = false
  }
}

async function autoGenerate() {
  if (generating.value) return
  generating.value = true
  errorMessage.value = ''
  try {
    const result = await callTuning('ai-generate', null)
    chatLog.value.push({ role: 'user', content: '[자동 진단 요청]' })
    chatLog.value.push({ role: 'assistant', content: result.reply })
    currentProposal.value = result
    await scrollChatToBottom()
  } catch (e) {
    errorMessage.value = `자동 진단 실패: ${e.message}`
  } finally {
    generating.value = false
  }
}

async function applyProposal() {
  if (!currentProposal.value || applying.value) return
  applying.value = true
  errorMessage.value = ''
  try {
    const body = {
      conditions: currentProposal.value.proposed_conditions,
      risk_params: currentProposal.value.proposed_risk_params,
      source: 'ai_chat',
      llm_reasoning: currentProposal.value.diagnosis || currentProposal.value.reply,
      suggestion_id: currentProposal.value.suggestion_id,
    }
    const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/apply-diff`, {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify(body),
    })
    await handleResponse(res)
    currentProposal.value = null
    chatLog.value.push({ role: 'assistant', content: '✓ 적용 완료. 다음 사이클부터 새 설정 반영.' })
    await load()  // 새 상태 다시 로드
  } catch (e) {
    errorMessage.value = `적용 실패: ${e.message}`
  } finally {
    applying.value = false
  }
}

function dismissProposal() {
  if (currentProposal.value?.suggestion_id) {
    // suggestion 기각 API 호출 (백그라운드, 실패해도 무시)
    fetch(`${API}/trading/bots/${props.botId}/suggestions/${currentProposal.value.suggestion_id}/dismiss`, {
      method: 'POST',
      headers: headers(),
    }).catch(() => {})
  }
  currentProposal.value = null
}

async function undoLast() {
  if (undoing.value) return
  undoing.value = true
  errorMessage.value = ''
  try {
    const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/undo`, {
      method: 'POST',
      headers: jsonHeaders(),
    })
    await handleResponse(res)
    chatLog.value.push({ role: 'assistant', content: '↶ 마지막 변경 복원 완료.' })
    await load()
  } catch (e) {
    errorMessage.value = `복원 실패: ${e.message}`
  } finally {
    undoing.value = false
  }
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

const proposedRiskDiff = computed(() => {
  const prop = currentProposal.value?.proposed_risk_params
  if (!prop) return []
  const current = riskParams.value
  const diff = []
  for (const k of Object.keys(prop)) {
    const before = current[k]
    const after = prop[k]
    if (before === undefined || Number(before) !== Number(after)) {
      diff.push({ key: k, before: before ?? '(미설정)', after })
    }
  }
  return diff
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
  padding: 16px 0;
}

.canvas-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.left-area, .right-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-block, .assistant-block {
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

.block-empty, .chat-empty {
  color: #6b7280;
  font-size: 13px;
  padding: 8px 0;
}

.conditions-table, .risk-table, .diff-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.conditions-table th,
.conditions-table td,
.diff-table th,
.diff-table td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: #d1d5db;
}

.conditions-table th, .diff-table th {
  color: #9ca3af;
  font-weight: normal;
  font-size: 12px;
}

.indicator {
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

/* AI 어시스턴트 패널 */
.chat-history {
  max-height: 260px;
  min-height: 120px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.msg-label {
  font-size: 11px;
  color: #6b7280;
}

.msg-body {
  font-size: 13px;
  line-height: 1.55;
  color: #d1d5db;
  white-space: pre-wrap;
}

.msg-user .msg-body {
  color: #93c5fd;
}

.chat-input {
  display: flex;
  gap: 6px;
}

.chat-input input {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 13px;
}

.chat-input input:focus {
  outline: none;
  border-color: #4f9eff;
}

.chat-input button, .btn-small {
  background: #4f9eff;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 12px;
  cursor: pointer;
}

.chat-input button:disabled, .btn-small:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  padding: 4px 10px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.08);
  color: #d1d5db;
}

.btn-small:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
}

/* 제안 영역 */
.proposal {
  margin-top: 12px;
  background: rgba(79, 158, 255, 0.05);
  border: 1px solid rgba(79, 158, 255, 0.3);
  border-radius: 6px;
  padding: 12px;
}

.proposal-title {
  color: #4f9eff;
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 13px;
}

.proposal-diag {
  color: #d1d5db;
  font-size: 12px;
  line-height: 1.55;
  margin-bottom: 8px;
}

.diff-block {
  margin-top: 8px;
}

.diff-label {
  color: #9ca3af;
  font-size: 12px;
  margin-bottom: 4px;
}

.v-before {
  color: #f87171;
  text-decoration: line-through;
  font-family: monospace;
}

.v-after {
  color: #34d399;
  font-family: monospace;
}

.arrow {
  color: #6b7280;
  text-align: center;
  width: 20px;
}

.proposal-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.btn-apply {
  flex: 1;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
  font-size: 13px;
}

.btn-apply:hover:not(:disabled) { background: #15803d; }
.btn-apply:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-dismiss {
  background: rgba(255, 255, 255, 0.08);
  color: #d1d5db;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}

.btn-dismiss:hover:not(:disabled) { background: rgba(255, 255, 255, 0.15); }

.error-banner {
  margin-top: 8px;
  padding: 8px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 6px;
  color: #f87171;
  font-size: 12px;
}

.loading {
  color: #6b7280;
  text-align: center;
  padding: 40px;
}

/* 하단 섹션 (suggestions + history) */
.lower-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

.suggestions-list, .history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.suggestion-row, .history-row {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.sg-header, .hist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.sg-date, .hist-date {
  color: #9ca3af;
  font-size: 11px;
}

.sg-actions {
  display: flex;
  gap: 4px;
}

.btn-apply-sm {
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 11px;
  cursor: pointer;
}

.btn-apply-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-dismiss-sm {
  background: rgba(255, 255, 255, 0.08);
  color: #d1d5db;
  border: none;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 11px;
  cursor: pointer;
}

.sg-diag, .hist-reason {
  color: #d1d5db;
  line-height: 1.5;
  margin-bottom: 4px;
}

.sg-diff, .hist-diff {
  color: #9ca3af;
  font-size: 11px;
  font-family: monospace;
}

.hist-source {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: #9ca3af;
}

.hist-source.src-ai_chat { background: rgba(79, 158, 255, 0.15); color: #4f9eff; }
.hist-source.src-ai_suggestion { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.hist-source.src-manual { background: rgba(156, 163, 175, 0.15); color: #9ca3af; }

/* 노드 편집기 섹션 */
.flow-section {
  margin-top: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 16px;
}

.flow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #e5e7eb;
  font-weight: 600;
  margin-bottom: 12px;
}

.flow-container {
  position: relative;
  /* CanvasView가 height:100%이라 부모는 명시적 height 필요 (auto/min-height만으론 자식이 0으로 collapse) */
  height: 800px;
  border-radius: 6px;
  /* overflow visible — palette 드롭다운 메뉴가 toolbar 위로 펼쳐질 때 잘리지 않게 */
  overflow: visible;
  background: rgba(0, 0, 0, 0.2);
}

.flow-note {
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(248, 187, 113, 0.08);
  border-left: 2px solid rgba(248, 187, 113, 0.6);
  color: #fcd34d;
  font-size: 11px;
}
</style>
