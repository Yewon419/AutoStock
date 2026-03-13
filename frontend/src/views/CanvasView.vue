<template>
  <div class="canvas-view">

    <!-- ── 툴바 ── -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="toolbar-brand">✦ AI 캔버스</span>
        <div class="palette-group">
          <span class="palette-label">소스</span>
          <button v-for="t in SOURCE_TYPES" :key="t" @click="addNode(t)" class="palette-btn cat-source">
            {{ NODE_DEFS[t].icon }} {{ NODE_DEFS[t].label }}
          </button>
        </div>
        <div class="palette-group">
          <span class="palette-label">처리</span>
          <button v-for="t in PROCESSING_TYPES" :key="t" @click="addNode(t)" class="palette-btn cat-processing">
            {{ NODE_DEFS[t].icon }} {{ NODE_DEFS[t].label }}
          </button>
        </div>
        <div class="palette-group">
          <span class="palette-label">출력</span>
          <button v-for="t in OUTPUT_TYPES" :key="t" @click="addNode(t)" class="palette-btn cat-output">
            {{ NODE_DEFS[t].icon }} {{ NODE_DEFS[t].label }}
          </button>
        </div>
      </div>
      <div class="toolbar-right">
        <span class="save-status" :class="saveStatus">
          <span v-if="saveStatus === 'pending'">대기중...</span>
          <span v-else-if="saveStatus === 'saving'">저장중...</span>
          <span v-else-if="saveStatus === 'saved'">✓ 저장됨</span>
        </span>
        <button @click="runAll" class="btn-run-all">▶ 전체 실행</button>
        <button @click="saveLayout(true)" class="btn-toolbar">💾 저장</button>
        <button @click="clearCanvas" class="btn-toolbar btn-danger-soft">🗑 초기화</button>
      </div>
    </div>

    <!-- ── VueFlow 캔버스 ── -->
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :node-types="nodeTypes"
      :default-edge-options="edgeDefaults"
      :connection-mode="ConnectionMode.Loose"
      :min-zoom="0.25"
      :max-zoom="2"
      fit-view-on-init
      @node-click="onNodeClick"
      @connect="onConnect"
      @pane-click="onPaneClick"
      class="flow-canvas"
    >
      <template #default>
        <Background :gap="24" pattern-color="#1f2235" />
        <Controls />
        <MiniMap :node-color="miniMapColor" />

        <!-- 빈 캔버스 힌트 -->
        <div v-if="nodes.length === 0" class="canvas-hint">
          <div class="hint-icon">✦</div>
          <div class="hint-title">AI 어시스턴트에게 파이프라인 구성을 요청하거나</div>
          <div class="hint-sub">위 팔레트에서 노드를 추가하세요</div>
          <div class="hint-presets">
            <button v-for="p in CHAT_PRESETS" :key="p.label" @click="sendChat(p.msg)" class="hint-preset-btn">
              {{ p.label }}
            </button>
          </div>
        </div>
      </template>
    </VueFlow>

    <!-- ── 사이드 패널 ── -->
    <Transition name="slide-right">
      <div v-if="selectedNode" class="side-panel">
        <div class="panel-header">
          <div class="panel-title-row">
            <span class="panel-node-icon">{{ selectedNode.data.icon }}</span>
            <span class="panel-node-name">{{ selectedNode.data.label }}</span>
            <span class="panel-cat-badge" :class="`cat-${selectedNode.data.category}`">
              {{ { source: '소스', processing: '처리', output: '출력' }[selectedNode.data.category] }}
            </span>
          </div>
          <button @click="selectedNode = null" class="close-btn">✕</button>
        </div>

        <div class="panel-body">
          <!-- 상태 -->
          <div class="panel-section">
            <div class="section-label">상태</div>
            <div class="status-row">
              <span class="status-dot-lg" :class="selectedNode.data.status || 'idle'" />
              <span class="status-text">{{ STATUS_LABELS[selectedNode.data.status || 'idle'] }}</span>
            </div>
          </div>

          <!-- 설정 -->
          <div class="panel-section" v-if="editableConfig.length">
            <div class="section-label">설정</div>
            <div v-for="field in editableConfig" :key="field.key" class="config-row">
              <label class="config-label">{{ field.label }}</label>
              <!-- bot 선택 -->
              <template v-if="field.key === 'bot_id'">
                <select v-model="selectedNode.data.config.bot_id" class="config-input">
                  <option :value="null">봇 선택...</option>
                  <option v-for="b in botList" :key="b.id" :value="b.id" :disabled="b.status === 'RUNNING'">
                    {{ b.name }}{{ b.status === 'RUNNING' ? ' (실행중)' : '' }}
                  </option>
                </select>
                <button class="btn-new-bot" @click="openNewBotModal">+ 새 봇 생성</button>
              </template>
              <!-- tickers_source -->
              <select v-else-if="field.key === 'tickers_source'" v-model="selectedNode.data.config.tickers_source" class="config-input">
                <option value="ml_top">ML 상위 30개</option>
                <option value="volume_top">거래량 상위 100개</option>
              </select>
              <input v-else v-model="selectedNode.data.config[field.key]" class="config-input" />
            </div>
          </div>

          <!-- 포트 -->
          <div class="panel-section">
            <div class="section-label">포트</div>
            <div v-if="selectedNode.data.inputs.length" class="port-group">
              <span class="port-label-head">입력</span>
              <span v-for="h in selectedNode.data.inputs" :key="h.id" class="port-chip port-in">{{ h.label }}</span>
            </div>
            <div v-if="selectedNode.data.outputs.length" class="port-group">
              <span class="port-label-head">출력</span>
              <span v-for="h in selectedNode.data.outputs" :key="h.id" class="port-chip port-out">{{ h.label }}</span>
            </div>
          </div>

          <!-- 결과 -->
          <div class="panel-section" v-if="selectedNode.data.result">
            <div class="section-label">실행 결과</div>
            <pre class="result-json">{{ JSON.stringify(selectedNode.data.result, null, 2) }}</pre>
          </div>

          <button @click="runNode(selectedNode.id)" class="btn-run-full" :disabled="selectedNode.data.status === 'running'">
            {{ selectedNode.data.status === 'running' ? '실행 중...' : '▶ 실행' }}
          </button>
          <button @click="deleteNode(selectedNode.id)" class="btn-delete-node">🗑 노드 삭제</button>
        </div>
      </div>
    </Transition>

    <!-- ── AI 어시스턴트 ── -->
    <div class="chat-panel" :class="{ expanded: chatExpanded }">
      <div class="chat-toggle" @click="chatExpanded = !chatExpanded">
        <span>✦ AI 어시스턴트</span>
        <span class="chat-toggle-icon">{{ chatExpanded ? '▼' : '▲' }}</span>
      </div>

      <div v-if="chatExpanded" class="chat-body">
        <div class="chat-messages" ref="chatEl">
          <div v-for="(msg, i) in chatMessages" :key="i" class="chat-msg" :class="msg.role">
            <div class="msg-bubble">{{ msg.content }}</div>
          </div>
          <div v-if="chatLoading" class="chat-msg assistant">
            <div class="msg-bubble typing">
              <span class="dot" /><span class="dot" /><span class="dot" />
            </div>
          </div>
        </div>

        <div class="chat-presets">
          <button v-for="p in CHAT_PRESETS" :key="p.label" @click="sendChat(p.msg)" class="preset-btn">
            {{ p.label }}
          </button>
        </div>

        <div class="chat-input-row">
          <input
            v-model="chatInput"
            @keyup.enter="sendChat()"
            class="chat-input"
            placeholder="캔버스를 자연어로 제어하세요..."
          />
          <button @click="sendChat()" :disabled="chatLoading || !chatInput.trim()" class="chat-send">
            전송
          </button>
        </div>
      </div>
    </div>

  <!-- ── 새 봇 생성 미니 모달 ── -->
  <Teleport to="body">
    <div v-if="newBotModal.open" class="nb-overlay" @click.self="newBotModal.open = false">
      <div class="nb-modal">
        <div class="nb-header">
          <span>새 봇 생성</span>
          <button @click="newBotModal.open = false" class="nb-close">✕</button>
        </div>
        <div class="nb-body">
          <div class="nb-row">
            <label>봇 이름</label>
            <input v-model="newBotModal.name" class="nb-input" placeholder="예) AI 전략봇 1" />
          </div>
          <div class="nb-row">
            <label>모드</label>
            <select v-model="newBotModal.mode" class="nb-input">
              <option value="mock">모의투자</option>
              <option value="real">실거래</option>
            </select>
          </div>
          <p v-if="newBotModal.error" class="nb-error">{{ newBotModal.error }}</p>
        </div>
        <div class="nb-footer">
          <button @click="newBotModal.open = false" class="nb-btn-cancel">취소</button>
          <button @click="createAndSelectBot" :disabled="newBotModal.loading" class="nb-btn-ok">
            {{ newBotModal.loading ? '생성 중...' : '생성' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  </div>
</template>

<script setup>
import { ref, computed, provide, nextTick, onMounted, markRaw, watch } from 'vue'
import {
  VueFlow, ConnectionMode, useVueFlow,
  Panel,
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

import FlowNode from '@/components/canvas/FlowNode.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API  = 'http://localhost:8001/api/v1'

// ── 노드 타입 등록 ────────────────────────────────────────────────
const nodeTypes = {
  marketContext:  markRaw(FlowNode),
  techIndicators: markRaw(FlowNode),
  mlScores:       markRaw(FlowNode),
  mlModel:        markRaw(FlowNode),
  llmGenerator:   markRaw(FlowNode),
  backtest:       markRaw(FlowNode),
  botApply:       markRaw(FlowNode),
}

// ── 노드 정의 ─────────────────────────────────────────────────────
const SOURCE_TYPES     = ['marketContext', 'techIndicators', 'mlScores']
const PROCESSING_TYPES = ['mlModel', 'llmGenerator', 'backtest']
const OUTPUT_TYPES     = ['botApply']

const NODE_DEFS = {
  marketContext: {
    label: '시장 컨텍스트', icon: '🌐', category: 'source',
    description: '뉴스·지수·투자자동향 수집',
    inputs: [], outputs: [{ id: 'market_data', label: '시장 데이터' }],
    config: {}, apiPath: '/ai/market-context', apiMethod: 'GET',
  },
  techIndicators: {
    label: '기술 지표 DB', icon: '📊', category: 'source',
    description: 'RSI·MACD·볼린저 등 DB 조회',
    inputs: [], outputs: [{ id: 'indicator_data', label: '지표 데이터' }],
    config: {}, apiPath: '/ai/tech-indicators-summary', apiMethod: 'GET',
  },
  mlScores: {
    label: 'ML 스코어 캐시', icon: '🎯', category: 'source',
    description: '저장된 ML 스코어링 결과',
    inputs: [], outputs: [{ id: 'ml_scores', label: 'ML 스코어' }],
    config: {}, apiPath: '/ai/scores', apiMethod: 'GET',
  },
  mlModel: {
    label: 'ML 모델', icon: '🤖', category: 'processing',
    description: 'RandomForest 학습 및 종목 스코어링',
    inputs:  [{ id: 'indicator_data', label: '지표 데이터' }],
    outputs: [{ id: 'ml_scores', label: 'ML 스코어' }],
    config: {}, apiPath: '/ai/score', apiMethod: 'POST', async: true,
  },
  llmGenerator: {
    label: 'LLM 전략 생성', icon: '✦', category: 'processing',
    description: 'Claude AI 기반 전략 자동 생성',
    inputs: [
      { id: 'market_data', label: '시장 데이터' },
      { id: 'ml_scores',   label: 'ML 스코어'  },
    ],
    outputs: [{ id: 'strategy', label: '전략' }],
    config: {}, apiPath: '/ai/generate-strategy', apiMethod: 'POST', async: true,
  },
  backtest: {
    label: '백테스트', icon: '📈', category: 'processing',
    description: '전략 성과 시뮬레이션',
    inputs:  [{ id: 'strategy', label: '전략' }],
    outputs: [{ id: 'backtest_result', label: '백테스트 결과' }],
    config: { tickers_source: 'ml_top' },
    apiPath: '/ai/backtest-strategy', apiMethod: 'POST', async: true,
  },
  botApply: {
    label: '봇 적용', icon: '🎮', category: 'output',
    description: '생성된 전략을 봇에 적용',
    inputs:  [{ id: 'strategy', label: '전략' }],
    outputs: [],
    config: { bot_id: null }, apiPath: '/bots', apiMethod: 'PUT',
  },
}

const STATUS_LABELS = { idle: '대기', running: '실행 중', success: '완료', error: '오류' }

const CHAT_PRESETS = [
  { label: '풀 파이프라인',  msg: '풀 파이프라인 구성해줘 (ML + LLM + 백테스트)' },
  { label: '빠른 전략',     msg: 'ML 캐시와 LLM으로 빠른 전략 생성 파이프라인 만들어줘' },
  { label: 'ML만',         msg: 'ML 모델 학습 파이프라인만 만들어줘' },
  { label: '캔버스 설명',   msg: '현재 캔버스 구성을 설명해줘' },
]

// ── Canvas 상태 ───────────────────────────────────────────────────
const nodes = ref([])
const edges = ref([])
let nodeCounter = 0

const edgeDefaults = {
  style: { stroke: '#2a2d3e', strokeWidth: 2 },
  animated: false,
}

// ── 선택된 노드 / 봇 목록 ─────────────────────────────────────────
const selectedNode = ref(null)
const botList = ref([])

const newBotModal = ref({ open: false, name: '', mode: 'mock', loading: false, error: '' })

function openNewBotModal() {
  newBotModal.value = { open: true, name: '', mode: 'mock', loading: false, error: '' }
}

async function createAndSelectBot() {
  if (!newBotModal.value.name.trim()) {
    newBotModal.value.error = '봇 이름을 입력하세요'
    return
  }
  newBotModal.value.loading = true
  newBotModal.value.error = ''
  try {
    const res = await fetch(`${API}/bots`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({
        name: newBotModal.value.name.trim(),
        mode: newBotModal.value.mode,
        tickers: [],
        initial_cash: 10000000,
      }),
    })
    if (!res.ok) throw new Error('생성 실패')
    const bot = await res.json()
    botList.value.push(bot)
    if (selectedNode.value?.data?.config) {
      selectedNode.value.data.config.bot_id = bot.id
    }
    newBotModal.value.open = false
  } catch (e) {
    newBotModal.value.error = e.message
  } finally {
    newBotModal.value.loading = false
  }
}

const editableConfig = computed(() => {
  if (!selectedNode.value) return []
  const cfg = selectedNode.value.data.config || {}
  return Object.keys(cfg).map(k => ({
    key: k,
    label: { bot_id: '봇 선택', tickers_source: '종목 소스' }[k] || k,
  }))
})

// ── VueFlow 훅 ────────────────────────────────────────────────────
const { updateNode, findNode, removeNodes, removeEdges } = useVueFlow()

// ── 노드 데이터 업데이트 ──────────────────────────────────────────
function updateNodeData(nodeId, patch) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return
  const updated = { ...node, data: { ...node.data, ...patch } }
  nodes.value = nodes.value.map(n => n.id === nodeId ? updated : n)
  if (selectedNode.value?.id === nodeId) selectedNode.value = updated
}

// ── 노드 추가 ─────────────────────────────────────────────────────
function addNode(type, x, y) {
  const def = NODE_DEFS[type]
  if (!def) return
  const id = `${type}-${++nodeCounter}`
  const cx = x ?? 120 + (nodes.value.length % 4) * 220
  const cy = y ?? 160 + Math.floor(nodes.value.length / 4) * 160

  nodes.value = [...nodes.value, {
    id,
    type,
    position: { x: cx, y: cy },
    data: {
      ...def,
      inputs:  [...def.inputs],
      outputs: [...def.outputs],
      config:  { ...def.config },
      status: 'idle',
      result: null,
      error:  null,
    },
  }]
}

// ── 노드 삭제 ─────────────────────────────────────────────────────
function deleteNode(nodeId) {
  nodes.value = nodes.value.filter(n => n.id !== nodeId)
  edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)
  if (selectedNode.value?.id === nodeId) selectedNode.value = null
}

// ── 연결 ─────────────────────────────────────────────────────────
function onConnect(params) {
  const id = `e-${params.source}-${params.sourceHandle}-${params.target}-${params.targetHandle}`
  if (edges.value.find(e => e.id === id)) return
  edges.value = [...edges.value, {
    id,
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle: params.targetHandle,
    style: { stroke: '#4b5563', strokeWidth: 2 },
    animated: false,
  }]
}

// ── 실행 ─────────────────────────────────────────────────────────
function headers(json = false) {
  const h = { Authorization: `Bearer ${auth.token}` }
  if (json) h['Content-Type'] = 'application/json'
  return h
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST', headers: headers(true),
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function pollTask(basePath, taskId) {
  while (true) {
    await new Promise(r => setTimeout(r, 3000))
    const res = await apiGet(`${basePath}/${taskId}`)
    if (res.status === 'completed') return res.result ?? res
    if (res.status === 'failed') throw new Error(res.error || '태스크 실패')
  }
}

// 연결된 상위 노드 결과 수집
function getInputResult(nodeId, handleId) {
  const edge = edges.value.find(e => e.target === nodeId && e.targetHandle === handleId)
  if (!edge) return null
  const src = nodes.value.find(n => n.id === edge.source)
  return src?.data?.result ?? null
}

// 출력 엣지 애니메이션 토글
function setOutEdgeAnimated(nodeId, animated) {
  edges.value = edges.value.map(e =>
    e.source === nodeId ? { ...e, animated, style: { ...e.style, stroke: animated ? '#4f9eff' : '#4b5563' } } : e
  )
}

async function runNode(nodeId) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return
  const def = NODE_DEFS[node.type]
  if (!def) return

  updateNodeData(nodeId, { status: 'running', error: null })

  try {
    let result

    // ── marketContext ──────────────────────────────────────────────
    if (node.type === 'marketContext') {
      const data = await apiGet('/ai/market-context')
      const ctx = data.context || data
      const indices = ctx.indices || {}
      result = {
        news_count: (ctx.news || []).length,
        kospi: indices.KOSPI?.close,
        vix:   indices.VIX?.close,
        sentiment: ctx.sentiment,
        raw: ctx,
      }
    }

    // ── techIndicators ─────────────────────────────────────────────
    else if (node.type === 'techIndicators') {
      result = await apiGet('/ai/tech-indicators-summary')
    }

    // ── mlScores ───────────────────────────────────────────────────
    else if (node.type === 'mlScores') {
      const data = await apiGet('/ai/scores')
      const scores = data.scores || {}
      const top = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 5)
      result = { top_tickers: top.length, top5: top.map(([t]) => t), meta: data.meta, raw: scores }
    }

    // ── mlModel ───────────────────────────────────────────────────
    else if (node.type === 'mlModel') {
      const res = await apiPost('/ai/score')
      result = await pollTask('/ai/score', res.task_id)
    }

    // ── llmGenerator ──────────────────────────────────────────────
    else if (node.type === 'llmGenerator') {
      const res = await apiPost('/ai/generate-strategy')
      const raw = await pollTask('/ai/generate-strategy', res.task_id)
      result = raw.status === 'ok' ? raw : raw
    }

    // ── backtest ──────────────────────────────────────────────────
    else if (node.type === 'backtest') {
      const strategyResult = getInputResult(nodeId, 'strategy')
      const strategyId = strategyResult?.strategy_id
      if (!strategyId) throw new Error('LLM 전략 생성 노드를 먼저 연결하고 실행하세요')
      const res = await apiPost('/ai/backtest-strategy', {
        strategy_id: strategyId,
        tickers_source: node.data.config.tickers_source || 'ml_top',
      })
      result = await pollTask('/ai/backtest-strategy', res.task_id)
    }

    // ── botApply ──────────────────────────────────────────────────
    else if (node.type === 'botApply') {
      const strategyResult = getInputResult(nodeId, 'strategy')
      const strategyId = strategyResult?.strategy_id
      if (!strategyId) throw new Error('전략 노드를 연결하고 실행하세요')
      const botId = node.data.config.bot_id
      if (!botId) throw new Error('사이드 패널에서 봇을 선택하세요')
      const bot = botList.value.find(b => b.id === botId)
      const res = await fetch(`${API}/bots/${botId}`, {
        method: 'PUT',
        headers: headers(true),
        body: JSON.stringify({ strategy_id: strategyId }),
      })
      if (!res.ok) {
        const isRunning = botList.value.find(b => b.id === botId)?.status === 'RUNNING'
        throw new Error(isRunning ? '실행 중인 봇은 변경할 수 없습니다. 봇을 먼저 정지하세요.' : '봇 적용 실패')
      }
      result = { bot_name: bot?.name || botId, strategy_id: strategyId, applied: true }
    }

    updateNodeData(nodeId, { status: 'success', result })
    setOutEdgeAnimated(nodeId, true)

  } catch (err) {
    updateNodeData(nodeId, { status: 'error', error: err.message })
  }
}

async function runAll() {
  // 소스 → 처리 → 출력 순으로 실행
  const ordered = [
    ...nodes.value.filter(n => n.data.category === 'source'),
    ...nodes.value.filter(n => n.data.category === 'processing'),
    ...nodes.value.filter(n => n.data.category === 'output'),
  ]
  for (const node of ordered) {
    await runNode(node.id)
  }
}

// ── 이벤트 ───────────────────────────────────────────────────────
function onNodeClick({ node }) {
  selectedNode.value = nodes.value.find(n => n.id === node.id) || null
}

function onPaneClick() {
  selectedNode.value = null
}

// ── Canvas 조작 ───────────────────────────────────────────────────
async function clearCanvas() {
  if (nodes.value.length && !confirm('캔버스를 초기화하시겠습니까?')) return
  nodes.value = []
  edges.value = []
  selectedNode.value = null
  await saveLayout(false)
}

// ── 저장 상태 표시 ────────────────────────────────────────────────
const saveStatus = ref('')  // '' | 'saving' | 'saved' | 'error'
let saveTimer = null

function _localSave(payload) {
  try {
    localStorage.setItem('autostock-canvas', JSON.stringify(payload))
  } catch { /* ignore */ }
}

async function _remoteSave(payload) {
  try {
    await fetch(`${API}/ai/canvas-state`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify(payload),
    })
  } catch { /* ignore — localStorage가 fallback */ }
}

function _buildPayload() {
  // 저장 시 실행 결과(result)는 제외 — 재실행 유도 / 용량 절약
  const cleanNodes = nodes.value.map(n => ({
    ...n,
    data: { ...n.data, status: 'idle', result: null, error: null },
  }))
  return { nodes: cleanNodes, edges: edges.value }
}

async function saveLayout(manual = false) {
  const payload = _buildPayload()
  _localSave(payload)
  saveStatus.value = 'saving'
  await _remoteSave(payload)
  saveStatus.value = 'saved'
  if (manual) {
    setTimeout(() => { saveStatus.value = '' }, 2000)
  }
}

function _scheduleAutoSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveLayout(false), 1500)
}

async function loadLayout() {
  try {
    // 1순위: 백엔드 Redis
    const res = await fetch(`${API}/ai/canvas-state`, { headers: headers() })
    if (res.ok) {
      const data = await res.json()
      if (data.nodes?.length) {
        nodes.value = data.nodes
        edges.value = data.edges || []
        nodeCounter = Math.max(0, ...nodes.value.map(n => parseInt(n.id.split('-').pop()) || 0))
        return
      }
    }
  } catch { /* ignore */ }

  // 2순위: localStorage fallback
  try {
    const saved = localStorage.getItem('autostock-canvas')
    if (!saved) return
    const { nodes: n, edges: e } = JSON.parse(saved)
    nodes.value = n || []
    edges.value = e || []
    nodeCounter = Math.max(0, ...nodes.value.map(n => parseInt(n.id.split('-').pop()) || 0))
  } catch { /* ignore */ }
}

// ── AI 어시스턴트 ─────────────────────────────────────────────────
const chatExpanded = ref(true)
const chatInput    = ref('')
const chatLoading  = ref(false)
const chatMessages = ref([
  { role: 'assistant', content: '안녕하세요! 저는 AutoStock 캔버스 AI 어시스턴트입니다. 아래 프리셋을 눌러 파이프라인을 자동 구성하거나, 자유롭게 요청해보세요.' },
])
const chatEl = ref(null)

function miniMapColor(node) {
  return { source: '#0891b2', processing: '#7c3aed', output: '#059669' }[node.data?.category] ?? '#4b5563'
}

async function sendChat(msg) {
  const text = (msg || chatInput.value).trim()
  if (!text) return
  chatInput.value = ''
  chatMessages.value.push({ role: 'user', content: text })
  chatLoading.value = true
  await scrollChat()

  try {
    const canvasState = {
      nodes: nodes.value.map(n => ({ id: n.id, type: n.type, status: n.data?.status })),
      edges: edges.value.map(e => ({ source: e.source, target: e.target, source_type: nodes.value.find(n => n.id === e.source)?.type, target_type: nodes.value.find(n => n.id === e.target)?.type })),
    }
    const res = await fetch(`${API}/ai/canvas-assistant`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ message: text, canvas: canvasState }),
    })
    const data = await res.json()
    chatMessages.value.push({ role: 'assistant', content: data.reply || '처리 완료' })
    if (data.commands?.length) applyCommands(data.commands)
  } catch (err) {
    chatMessages.value.push({ role: 'assistant', content: `오류: ${err.message}` })
  } finally {
    chatLoading.value = false
    await scrollChat()
  }
}

function applyCommands(commands) {
  for (const cmd of commands) {
    if (cmd.type === 'clear') {
      nodes.value = []
      edges.value = []
      selectedNode.value = null

    } else if (cmd.type === 'add_node') {
      addNode(cmd.node_type, cmd.x, cmd.y)

    } else if (cmd.type === 'connect') {
      const src = nodes.value.find(n => n.type === cmd.source_type)
      const tgt = nodes.value.find(n => n.type === cmd.target_type)
      if (src && tgt) {
        onConnect({
          source: src.id, sourceHandle: cmd.source_handle,
          target: tgt.id, targetHandle: cmd.target_handle,
        })
      }

    } else if (cmd.type === 'remove_node') {
      const node = nodes.value.find(n => n.type === cmd.node_type)
      if (node) deleteNode(node.id)

    } else if (cmd.type === 'run_node') {
      const node = nodes.value.find(n => n.type === cmd.node_type)
      if (node) setTimeout(() => runNode(node.id), 800)
    }
  }
}

async function scrollChat() {
  await nextTick()
  if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
}

// ── 자동저장: nodes/edges 변경 감지 ──────────────────────────────
watch([nodes, edges], () => {
  if (nodes.value.length > 0 || edges.value.length > 0) {
    saveStatus.value = 'pending'
    _scheduleAutoSave()
  }
}, { deep: true })

// ── Provide (FlowNode에서 inject) ─────────────────────────────────
provide('runNode',   runNode)
provide('selectNode', (id) => {
  selectedNode.value = nodes.value.find(n => n.id === id) || null
})

// ── 초기화 ────────────────────────────────────────────────────────
onMounted(async () => {
  loadLayout()
  try {
    const res = await fetch(`${API}/bots`, { headers: headers() })
    botList.value = await res.json()
  } catch { /* ignore */ }
})
</script>

<style scoped>
.canvas-view {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #0f1117;
  overflow: hidden;
}

/* ── 툴바 ── */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  height: 48px;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3e;
  flex-shrink: 0;
  gap: 12px;
  overflow-x: auto;
}

.toolbar-brand {
  font-size: 14px;
  font-weight: 700;
  color: #a78bfa;
  flex-shrink: 0;
  margin-right: 8px;
}

.toolbar-left  { display: flex; align-items: center; gap: 8px; flex: 1; }
.toolbar-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.palette-group { display: flex; align-items: center; gap: 4px; border-left: 1px solid #2a2d3e; padding-left: 8px; }
.palette-label { font-size: 10px; color: #4b5563; text-transform: uppercase; letter-spacing: 0.05em; flex-shrink: 0; }

.palette-btn {
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid transparent;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.palette-btn.cat-source     { background: rgba(8,145,178,.12); color: #22d3ee; border-color: rgba(8,145,178,.25); }
.palette-btn.cat-processing { background: rgba(124,58,237,.12); color: #a78bfa; border-color: rgba(124,58,237,.25); }
.palette-btn.cat-output     { background: rgba(5,150,105,.12); color: #34d399; border-color: rgba(5,150,105,.25); }
.palette-btn:hover { opacity: 0.8; }

.btn-run-all {
  padding: 6px 14px;
  background: linear-gradient(135deg, #2563eb, #4f9eff);
  border: none; border-radius: 6px;
  color: #fff; font-size: 12px; font-weight: 700;
  cursor: pointer;
}
.btn-run-all:hover { opacity: 0.85; }

.btn-toolbar {
  padding: 5px 12px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-toolbar:hover { border-color: #4f9eff; color: #4f9eff; }
.btn-danger-soft:hover { border-color: #ef4444; color: #ef4444; }

.save-status {
  font-size: 11px;
  min-width: 56px;
  text-align: right;
  transition: color 0.2s;
}
.save-status.pending { color: #6b7280; }
.save-status.saving  { color: #4f9eff; }
.save-status.saved   { color: #10b981; }

/* ── 캔버스 ── */
.flow-canvas { flex: 1; background: #0f1117; }

/* VueFlow 배경 색상 덮어쓰기 */
:deep(.vue-flow__background) { background: #0f1117 !important; }
:deep(.vue-flow__edge-path) { stroke: #4b5563; }
:deep(.vue-flow__edge.animated .vue-flow__edge-path) { animation: dashdraw .5s linear infinite; }
:deep(.vue-flow__controls) { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 8px; }
:deep(.vue-flow__controls button) { background: #1a1d27; color: #9ca3af; border-color: #2a2d3e; }
:deep(.vue-flow__controls button:hover) { background: #2a2d3e; }
:deep(.vue-flow__minimap) { background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 8px; }

/* ── 빈 캔버스 힌트 ── */
.canvas-hint {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}
.canvas-hint * { pointer-events: auto; }
.hint-icon   { font-size: 32px; color: #2a2d3e; margin-bottom: 12px; }
.hint-title  { font-size: 14px; color: #4b5563; margin-bottom: 4px; }
.hint-sub    { font-size: 12px; color: #374151; margin-bottom: 16px; }
.hint-presets { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.hint-preset-btn {
  padding: 6px 14px;
  background: rgba(167,139,250,.1);
  border: 1px solid rgba(167,139,250,.3);
  border-radius: 20px;
  color: #a78bfa;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.hint-preset-btn:hover { background: rgba(167,139,250,.2); }

/* ── 사이드 패널 ── */
.side-panel {
  position: absolute;
  right: 0; top: 0; bottom: 0;
  width: 300px;
  background: #1a1d27;
  border-left: 1px solid #2a2d3e;
  display: flex;
  flex-direction: column;
  z-index: 10;
  overflow: hidden;
}

.panel-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 16px 18px;
  border-bottom: 1px solid #2a2d3e;
  flex-shrink: 0;
}
.panel-title-row { display: flex; align-items: center; gap: 8px; }
.panel-node-icon { font-size: 18px; }
.panel-node-name { font-size: 14px; font-weight: 700; color: #e5e7eb; }
.panel-cat-badge {
  font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 999px;
}
.cat-source     { background: rgba(8,145,178,.15); color: #22d3ee; }
.cat-processing { background: rgba(124,58,237,.15); color: #a78bfa; }
.cat-output     { background: rgba(5,150,105,.15);  color: #34d399; }

.close-btn { background: none; border: none; color: #6b7280; font-size: 16px; cursor: pointer; padding: 0; }

.panel-body { flex: 1; overflow-y: auto; padding: 16px 18px; display: flex; flex-direction: column; gap: 16px; }

.panel-section {}
.section-label { font-size: 10px; font-weight: 700; color: #4b5563; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }

.status-row { display: flex; align-items: center; gap: 8px; }
.status-dot-lg { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.status-dot-lg.idle    { background: #4b5563; }
.status-dot-lg.running { background: #4f9eff; animation: pulse2 1s infinite; }
.status-dot-lg.success { background: #10b981; }
.status-dot-lg.error   { background: #ef4444; }
@keyframes pulse2 { 0%,100% { opacity:1; } 50% { opacity:.3; } }
.status-text { font-size: 13px; color: #e5e7eb; }

.config-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.config-label { font-size: 11px; color: #6b7280; }
.config-input {
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 6px;
  color: #e5e7eb; font-size: 13px; padding: 6px 10px; outline: none;
  transition: border-color 0.15s;
}
.config-input:focus { border-color: #4f9eff; }

.port-group { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.port-label-head { font-size: 10px; color: #4b5563; width: 24px; flex-shrink: 0; }
.port-chip { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.port-in  { background: rgba(8,145,178,.15); color: #22d3ee; }
.port-out { background: rgba(124,58,237,.15); color: #a78bfa; }

.result-json {
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 6px;
  padding: 10px 12px; font-size: 11px; color: #9ca3af;
  overflow: auto; max-height: 200px; white-space: pre-wrap; word-break: break-all;
}

.btn-run-full {
  width: 100%; padding: 9px 0;
  background: linear-gradient(135deg, #1d4ed8, #4f9eff);
  border: none; border-radius: 7px; color: #fff;
  font-size: 13px; font-weight: 700; cursor: pointer;
  transition: opacity 0.15s;
}
.btn-run-full:hover:not(:disabled) { opacity: 0.85; }
.btn-run-full:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-delete-node {
  width: 100%; padding: 8px 0; margin-top: 4px;
  background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.25);
  border-radius: 7px; color: #ef4444; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn-delete-node:hover { background: rgba(239,68,68,.2); }

/* 사이드 패널 애니메이션 */
.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.2s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(100%); }

/* ── AI 채팅 ── */
.chat-panel {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: #1a1d27;
  border-top: 1px solid #2a2d3e;
  z-index: 20;
  transition: height 0.2s ease;
}

.chat-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 18px;
  cursor: pointer;
  font-size: 13px; font-weight: 600; color: #a78bfa;
  user-select: none;
}
.chat-toggle:hover { background: rgba(167,139,250,.06); }
.chat-toggle-icon { font-size: 10px; color: #6b7280; }

.chat-body { display: flex; flex-direction: column; gap: 10px; padding: 0 16px 14px; }

.chat-messages {
  max-height: 180px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 8px;
  padding: 4px 0;
}

.chat-msg { display: flex; }
.chat-msg.user     { justify-content: flex-end; }
.chat-msg.assistant { justify-content: flex-start; }

.msg-bubble {
  max-width: 80%; padding: 8px 12px; border-radius: 10px;
  font-size: 12px; line-height: 1.5;
}
.user .msg-bubble     { background: rgba(79,158,255,.2); color: #e5e7eb; border-radius: 10px 10px 2px 10px; }
.assistant .msg-bubble { background: rgba(167,139,250,.12); color: #d1d5db; border-radius: 10px 10px 10px 2px; }

.typing { display: flex; align-items: center; gap: 4px; padding: 10px 14px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #a78bfa; animation: bounce .8s infinite; }
.dot:nth-child(2) { animation-delay: .15s; }
.dot:nth-child(3) { animation-delay: .3s; }
@keyframes bounce { 0%,80%,100% { transform: scale(0.6); } 40% { transform: scale(1); } }

.chat-presets { display: flex; flex-wrap: wrap; gap: 6px; }
.preset-btn {
  padding: 4px 12px;
  background: rgba(167,139,250,.08); border: 1px solid rgba(167,139,250,.2);
  border-radius: 20px; color: #a78bfa; font-size: 11px; cursor: pointer;
  transition: all 0.15s;
}
.preset-btn:hover { background: rgba(167,139,250,.18); border-color: #a78bfa; }

.chat-input-row { display: flex; gap: 8px; }
.chat-input {
  flex: 1; background: #0f1117; border: 1px solid #2a2d3e;
  border-radius: 8px; color: #e5e7eb; font-size: 13px; padding: 8px 12px;
  outline: none; transition: border-color 0.15s;
}
.chat-input:focus { border-color: #a78bfa; }
.chat-send {
  padding: 8px 16px; background: linear-gradient(135deg, #7c3aed, #a855f7);
  border: none; border-radius: 8px; color: #fff; font-size: 13px;
  font-weight: 700; cursor: pointer; transition: opacity 0.15s;
}
.chat-send:hover:not(:disabled) { opacity: 0.85; }
.chat-send:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── 새 봇 생성 버튼 ── */
.btn-new-bot {
  margin-top: 6px;
  width: 100%;
  padding: 5px 0;
  background: none;
  border: 1px dashed #4f9eff;
  border-radius: 5px;
  color: #4f9eff;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-new-bot:hover { background: rgba(79,158,255,.08); }

/* ── 새 봇 생성 미니 모달 ── */
.nb-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}
.nb-modal {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  width: 320px;
  overflow: hidden;
}
.nb-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #2a2d3e;
  font-weight: 600; font-size: 14px; color: #e5e7eb;
}
.nb-close {
  background: none; border: none; color: #6b7280;
  font-size: 14px; cursor: pointer; padding: 2px 6px;
}
.nb-close:hover { color: #e5e7eb; }
.nb-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.nb-row { display: flex; flex-direction: column; gap: 4px; }
.nb-row label { font-size: 11px; color: #6b7280; }
.nb-input {
  background: #0f1117; border: 1px solid #2a2d3e;
  border-radius: 6px; color: #e5e7eb; font-size: 13px;
  padding: 6px 10px; outline: none;
}
.nb-input:focus { border-color: #4f9eff; }
.nb-error { color: #ef4444; font-size: 11px; margin: 0; }
.nb-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid #2a2d3e;
}
.nb-btn-cancel {
  padding: 6px 14px; background: none;
  border: 1px solid #2a2d3e; border-radius: 6px;
  color: #6b7280; font-size: 12px; cursor: pointer;
}
.nb-btn-cancel:hover { border-color: #4f9eff; color: #4f9eff; }
.nb-btn-ok {
  padding: 6px 14px;
  background: #4f9eff; border: none; border-radius: 6px;
  color: #fff; font-size: 12px; font-weight: 600; cursor: pointer;
}
.nb-btn-ok:hover:not(:disabled) { background: #3b82f6; }
.nb-btn-ok:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
