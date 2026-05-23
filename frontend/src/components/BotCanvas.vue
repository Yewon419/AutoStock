<template>
  <div v-if="!loading" class="bot-canvas">
    <div class="canvas-layout">
      <!-- 좌측: 현재 전략 + risk_params -->
      <div class="left-area">
        <div class="block">
          <div class="block-head">
            <span class="block-title">STRATEGY · 조건</span>
            <span class="block-count">{{ conditionsCount }}건</span>
          </div>
          <div v-if="conditionsCount === 0" class="block-empty">
            조건이 없습니다. 우측 AI 어시스턴트에게 도움을 요청하세요.
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>지표</th>
                <th>조건</th>
                <th class="th-num">값</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in strategy.conditions" :key="i">
                <td class="indicator">{{ c.indicator }}</td>
                <td>{{ c.condition }}</td>
                <td class="td-num">{{ formatValue(c) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="block">
          <div class="block-head">
            <span class="block-title">RISK · 파라미터</span>
            <button
              class="btn-ghost-sm"
              type="button"
              :disabled="undoing"
              @click="undoLast"
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
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
              <span>{{ undoing ? 'UNDOING' : '되돌리기' }}</span>
            </button>
          </div>
          <table class="risk-table">
            <tbody>
              <tr v-for="(v, k) in riskParams" :key="k">
                <td class="rk-key">{{ riskLabel(k) }}</td>
                <td class="rk-val mono">{{ v }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 우측: AI 어시스턴트 -->
      <div class="right-area">
        <div class="block assistant-block">
          <div class="block-head">
            <span class="block-title">
              <svg
                class="block-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
                <path d="M19 3v3" />
                <path d="M17.5 4.5h3" />
              </svg>
              AI · 튜닝 어시스턴트
            </span>
            <button
              class="btn-llm-sm"
              type="button"
              :disabled="generating"
              @click="autoGenerate"
            >
              <svg
                :class="{ spin: generating }"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path v-if="!generating" d="M21 12a9 9 0 1 1-9-9" />
                <path v-if="!generating" d="M21 4v6h-6" />
                <path v-else d="M21 12a9 9 0 1 1-6-8.5" />
              </svg>
              <span>{{ generating ? 'DIAGNOSING' : '자동 진단' }}</span>
            </button>
          </div>

          <!-- 대화 히스토리 -->
          <div ref="chatHistoryEl" class="chat-history">
            <div v-if="chatLog.length === 0" class="chat-empty">
              메시지를 보내거나 자동 진단을 실행하세요.
            </div>
            <div
              v-for="(msg, i) in chatLog"
              :key="i"
              class="chat-msg"
              :class="`msg-${msg.role}`"
            >
              <div class="msg-label">{{ msg.role === 'user' ? '나' : 'AI' }}</div>
              <div class="msg-body">{{ msg.content }}</div>
            </div>
            <div v-if="chatting || generating" class="chat-msg msg-assistant chat-thinking">
              <div class="msg-label">AI</div>
              <div class="msg-body">
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span class="thinking-label">
                  {{ generating ? '자동 진단 중...' : '응답 생성 중...' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 입력 -->
          <div class="chat-input">
            <input
              v-model="userMessage"
              type="text"
              placeholder="이 봇을 어떻게 손볼지 물어보세요 (예: RSI 더 보수적으로)"
              :disabled="chatting"
              @keydown.enter="sendChat"
            />
            <button
              type="button"
              :disabled="chatting || !userMessage.trim()"
              @click="sendChat"
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
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              <span>{{ chatting ? '...' : '보내기' }}</span>
            </button>
          </div>

          <!-- 현재 제안 -->
          <div v-if="currentProposal" class="proposal">
            <div class="proposal-head">
              <span class="proposal-tag">PROPOSAL</span>
              <span class="proposal-title">변경 제안</span>
            </div>
            <div v-if="currentProposal.diagnosis" class="proposal-diag">
              <span class="diag-label">DIAGNOSIS</span>
              <span class="diag-text">{{ currentProposal.diagnosis }}</span>
            </div>

            <div v-if="proposedRiskDiff.length" class="diff-block">
              <div class="diff-label">
                risk_params 변경 · {{ proposedRiskDiff.length }}건
              </div>
              <table class="diff-table">
                <thead>
                  <tr>
                    <th>항목</th>
                    <th class="th-num">현재</th>
                    <th>→</th>
                    <th class="th-num">제안</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in proposedRiskDiff" :key="d.key">
                    <td>{{ riskLabel(d.key) }}</td>
                    <td class="td-num v-before">{{ d.before }}</td>
                    <td class="arrow">→</td>
                    <td class="td-num v-after">{{ d.after }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div
              v-if="currentProposal.proposed_conditions !== null && currentProposal.proposed_conditions !== undefined"
              class="diff-block"
            >
              <div class="diff-label">
                strategy.conditions 변경 · {{ currentProposal.proposed_conditions.length }}건 전체 교체
              </div>
              <table class="diff-table">
                <thead>
                  <tr>
                    <th>지표</th>
                    <th>조건</th>
                    <th class="th-num">값</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(c, i) in currentProposal.proposed_conditions" :key="i">
                    <td class="indicator">{{ c.indicator }}</td>
                    <td>{{ c.condition }}</td>
                    <td class="td-num">{{ formatValue(c) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="proposal-actions">
              <button
                class="btn-apply"
                type="button"
                :disabled="applying"
                @click="applyProposal"
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
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>{{ applying ? 'APPLYING' : '적용' }}</span>
              </button>
              <button
                class="btn-ghost-sm"
                type="button"
                :disabled="applying"
                @click="dismissProposal"
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
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                <span>기각</span>
              </button>
            </div>
          </div>

          <div v-if="errorMessage" class="msg msg-fail">
            <span class="msg-tag">ERR</span>
            <span>{{ errorMessage }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 하단: 튜닝 제안함 + 변경 이력 -->
    <div class="lower-section">
      <div class="block">
        <div class="block-head">
          <span class="block-title">PENDING · 튜닝 제안함</span>
          <span class="block-count">{{ pendingSuggestions.length }}건 대기</span>
        </div>
        <div v-if="pendingSuggestions.length === 0" class="block-empty">
          대기 중인 제안이 없습니다. 매일 08:30 자동 진단이 새 제안을 드롭합니다.
        </div>
        <div v-else class="suggestions-list">
          <div v-for="s in pendingSuggestions" :key="s.id" class="suggestion-row">
            <div class="sg-header">
              <span class="sg-date mono">{{ fmtDate(s.created_at) }}</span>
              <div class="sg-actions">
                <button
                  class="btn-apply-sm"
                  type="button"
                  :disabled="applyingSugg === s.id"
                  @click="applySuggestion(s)"
                >{{ applyingSugg === s.id ? '...' : '적용' }}</button>
                <button
                  class="btn-dismiss-sm"
                  type="button"
                  @click="dismissSuggestion(s)"
                >기각</button>
              </div>
            </div>
            <div class="sg-diag">{{ s.diagnosis_text }}</div>
            <div v-if="s.suggested_risk_params" class="sg-diff mono">
              risk_params: {{ JSON.stringify(s.suggested_risk_params) }}
            </div>
            <div v-if="s.suggested_conditions" class="sg-diff mono">
              conditions: {{ s.suggested_conditions.length }}건
            </div>
          </div>
        </div>
      </div>

      <div class="block">
        <div class="block-head">
          <span class="block-title">HISTORY · 변경 이력</span>
          <span class="block-count">{{ history.length }}건</span>
        </div>
        <div v-if="history.length === 0" class="block-empty">
          변경 이력이 없습니다.
        </div>
        <div v-else class="history-list">
          <div v-for="h in history" :key="h.id" class="history-row">
            <div class="hist-header">
              <span class="hist-date mono">{{ fmtDate(h.applied_at) }}</span>
              <span class="hist-source" :class="`src-${h.source}`">{{ h.source }}</span>
            </div>
            <div v-if="h.llm_reasoning" class="hist-reason">{{ h.llm_reasoning }}</div>
            <div class="hist-diff mono">
              <span v-if="h.before_risk_params && h.after_risk_params">
                risk_params 변경
              </span>
              <span
                v-if="h.before_conditions !== null && h.after_conditions !== null"
              >
                conditions 변경
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 노드 편집기 -->
    <div class="flow-section">
      <div class="flow-header">
        <span class="block-title">CANVAS · 노드 편집기</span>
        <button
          class="btn-ghost-sm"
          type="button"
          @click="showFlow = !showFlow"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
            :class="{ 'rot-180': showFlow }"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
          <span>{{ showFlow ? '접기' : '펼치기' }}</span>
        </button>
      </div>
      <div v-show="showFlow" class="flow-container">
        <CanvasView :bot-id="botId" />
      </div>
    </div>
  </div>
  <div v-else class="loading">LOADING · 전략 정보 불러오는 중...</div>
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
const chatLog = ref([])
const currentProposal = ref(null)
const chatting = ref(false)
const generating = ref(false)
const applying = ref(false)
const undoing = ref(false)
const errorMessage = ref('')
const chatHistoryEl = ref(null)
const history = ref([])
const pendingSuggestions = ref([])
const applyingSugg = ref(null)
const showFlow = ref(true)

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

async function fetchChatHistory() {
  const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/chat-history?limit=200`, { headers: headers() })
  if (res.ok) {
    const rows = await res.json()
    chatLog.value = rows.map((r) => ({ role: r.role, content: r.content }))
  }
}

async function load() {
  loading.value = true
  await fetchBot()
  await fetchStrategy()
  await Promise.all([fetchHistory(), fetchSuggestions(), fetchChatHistory()])
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
    /* 백그라운드 */
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
  await scrollChatToBottom()
  try {
    const result = await callTuning('chat', { message: msg })
    chatLog.value.push({ role: 'assistant', content: result.reply })
    currentProposal.value = hasProposalChanges(result) ? result : null
    await scrollChatToBottom()
  } catch (e) {
    errorMessage.value = `대화 실패: ${e.message}`
  } finally {
    chatting.value = false
  }
}

function hasProposalChanges(result) {
  return result && (result.proposed_conditions != null || result.proposed_risk_params != null)
}

async function autoGenerate() {
  if (generating.value) return
  generating.value = true
  errorMessage.value = ''
  await scrollChatToBottom()
  try {
    const result = await callTuning('ai-generate', null)
    chatLog.value.push({ role: 'user', content: '[자동 진단 요청]' })
    chatLog.value.push({ role: 'assistant', content: result.reply })
    currentProposal.value = hasProposalChanges(result) ? result : null
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
    chatLog.value.push({
      role: 'assistant',
      content: '✓ 적용 완료. 다음 사이클부터 새 설정 반영.',
    })
    await load()
  } catch (e) {
    errorMessage.value = `적용 실패: ${e.message}`
  } finally {
    applying.value = false
  }
}

function dismissProposal() {
  if (currentProposal.value?.suggestion_id) {
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
  padding: var(--space-3) 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.canvas-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.left-area,
.right-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ==========================================================================
   Block (shared card pattern)
   ========================================================================== */

.block {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.assistant-block {
  border-color: var(--violet-border);
}

.block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.assistant-block .block-head {
  background: var(--violet-bg);
}

.block-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.block-icon {
  width: 13px;
  height: 13px;
  color: var(--violet);
}

.block-count {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.block-empty,
.chat-empty {
  padding: var(--space-5) var(--space-4);
  text-align: center;
  color: var(--text-faint);
  font-size: var(--text-sm);
}

/* ==========================================================================
   Tables
   ========================================================================== */

.data-table,
.risk-table,
.diff-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.data-table th,
.diff-table th {
  padding: var(--space-2) var(--space-4);
  text-align: left;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--bg-base);
  border-bottom: 1px solid var(--border-faint);
}

.data-table th.th-num,
.diff-table th.th-num {
  text-align: right;
}

.data-table td,
.diff-table td {
  padding: var(--space-2) var(--space-4);
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-faint);
}

.data-table td.td-num,
.diff-table td.td-num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.data-table tbody tr:last-child td,
.diff-table tbody tr:last-child td {
  border-bottom: none;
}

.indicator {
  font-family: var(--font-mono);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
}

.risk-table {
  padding: var(--space-2) 0;
}

.risk-table td {
  padding: 6px var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.risk-table tr:last-child td {
  border-bottom: none;
}

.risk-table .rk-key {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

.risk-table .rk-val {
  text-align: right;
  color: var(--text-primary);
  font-weight: 600;
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--tracking-wide);
}

/* ==========================================================================
   Buttons
   ========================================================================== */

.btn-ghost-sm,
.btn-llm-sm {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px var(--space-2);
  border-radius: var(--radius-sm);
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

.btn-ghost-sm svg,
.btn-llm-sm svg {
  width: 11px;
  height: 11px;
}

.btn-ghost-sm {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}

.btn-ghost-sm:hover:not(:disabled) {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-ghost-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-llm-sm {
  background: var(--violet-bg);
  border: 1px solid var(--violet-border);
  color: var(--violet);
}

.btn-llm-sm:hover:not(:disabled) {
  background: rgba(167, 139, 250, 0.2);
  border-color: var(--violet);
}

.btn-llm-sm:disabled {
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

.rot-180 {
  transform: rotate(180deg);
  transition: transform var(--dur-fast) var(--ease-out);
}

/* ==========================================================================
   Chat
   ========================================================================== */

.chat-history {
  max-height: 280px;
  min-height: 140px;
  overflow-y: auto;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border-faint);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.msg-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-faint);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.msg-user .msg-label {
  color: var(--accent);
}

.msg-assistant .msg-label {
  color: var(--violet);
}

.msg-body {
  font-size: var(--text-sm);
  line-height: var(--leading-loose);
  color: var(--text-secondary);
  white-space: pre-wrap;
}

.msg-user .msg-body {
  color: var(--text-primary);
}

.chat-thinking .msg-body {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
}

.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--violet);
  display: inline-block;
  animation: thinking-bounce 1.2s infinite ease-in-out;
}

.thinking-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.thinking-dot:nth-child(3) {
  animation-delay: 0.3s;
}

.thinking-label {
  margin-left: 4px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

@keyframes thinking-bounce {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.chat-input {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.chat-input input {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px var(--space-3);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-sm);
  outline: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.chat-input input:hover {
  border-color: var(--border-strong);
}

.chat-input input:focus {
  border-color: var(--violet);
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.15);
}

.chat-input input::placeholder {
  color: var(--text-faint);
}

.chat-input button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--violet);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 8px var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.chat-input button svg {
  width: 12px;
  height: 12px;
}

.chat-input button:hover:not(:disabled) {
  background: var(--violet-strong);
  transform: translateY(-1px);
}

.chat-input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==========================================================================
   Proposal
   ========================================================================== */

.proposal {
  background: var(--violet-bg);
  border-top: 1px solid var(--violet-border);
  padding: var(--space-4);
}

.proposal-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.proposal-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  padding: 3px 7px;
  background: var(--violet);
  color: #fff;
  border-radius: var(--radius-xs);
}

.proposal-title {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--violet);
  letter-spacing: var(--tracking-tight);
}

.proposal-diag {
  background: var(--bg-base);
  border-left: 2px solid var(--violet);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-loose);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.diag-label {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--violet);
  letter-spacing: var(--tracking-wider);
}

.diag-text {
  color: var(--text-secondary);
}

.diff-block {
  margin-top: var(--space-3);
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.diff-label {
  padding: var(--space-2) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.diff-table {
  margin: 0;
}

.v-before {
  color: var(--profit);
  text-decoration: line-through;
}

.v-after {
  color: var(--up-strong);
}

.arrow {
  font-family: var(--font-mono);
  color: var(--text-muted);
  text-align: center;
  width: 30px;
}

.proposal-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.btn-apply {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  flex: 1;
  padding: 9px var(--space-3);
  background: var(--up-strong);
  color: #fff;
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
    transform var(--dur-fast) var(--ease-out);
}

.btn-apply svg {
  width: 13px;
  height: 13px;
}

.btn-apply:hover:not(:disabled) {
  background: #16a34a;
  transform: translateY(-1px);
}

.btn-apply:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.msg {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: 0;
  font-size: var(--text-sm);
  border-top: 1px solid;
  margin: 0;
}

.msg-fail {
  background: var(--profit-bg);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--profit-soft);
}

.msg-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.08);
}

/* ==========================================================================
   Loading
   ========================================================================== */

.loading {
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-16);
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wider);
  font-size: var(--text-sm);
}

/* ==========================================================================
   Lower section (suggestions + history)
   ========================================================================== */

.lower-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.suggestions-list,
.history-list {
  display: flex;
  flex-direction: column;
  max-height: 320px;
  overflow-y: auto;
}

.suggestion-row,
.history-row {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  font-size: var(--text-sm);
}

.suggestion-row:last-child,
.history-row:last-child {
  border-bottom: none;
}

.sg-header,
.hist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.sg-date,
.hist-date {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.sg-actions {
  display: flex;
  gap: var(--space-1);
}

.btn-apply-sm {
  background: var(--up-bg);
  color: var(--up-strong);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: var(--radius-xs);
  padding: 3px var(--space-2);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.btn-apply-sm:hover:not(:disabled) {
  background: rgba(34, 197, 94, 0.2);
}

.btn-apply-sm:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-dismiss-sm {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  padding: 3px var(--space-2);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.btn-dismiss-sm:hover {
  border-color: var(--border-strong);
  color: var(--text-secondary);
}

.sg-diag,
.hist-reason {
  color: var(--text-secondary);
  line-height: var(--leading-loose);
  margin-bottom: 4px;
  font-size: var(--text-sm);
}

.sg-diff,
.hist-diff {
  color: var(--text-muted);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

.hist-source {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.hist-source.src-ai_chat {
  background: var(--violet-bg);
  color: var(--violet);
}

.hist-source.src-ai_suggestion {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
}

.hist-source.src-manual {
  background: var(--surface-2);
  color: var(--text-tertiary);
}

/* ==========================================================================
   Flow section (node editor embed)
   ========================================================================== */

.flow-section {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.flow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.flow-container {
  position: relative;
  height: 800px;
  overflow: visible;
  background: var(--bg-base);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 1024px) {
  .canvas-layout {
    grid-template-columns: 1fr;
  }
  .lower-section {
    grid-template-columns: 1fr;
  }
}
</style>
