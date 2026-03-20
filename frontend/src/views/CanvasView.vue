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
          <span class="palette-label">전략</span>
          <button v-for="t in STRATEGY_TYPES" :key="t" @click="addNode(t)" class="palette-btn cat-strategy">
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
              {{ { source: '소스', strategy: '전략', processing: '처리', output: '출력' }[selectedNode.data.category] }}
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

          <!-- 설정 (일반) -->
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
              <!-- strategy 노드: 전략 선택 -->
              <template v-else-if="field.key === 'strategy_id'">
                <select v-model="selectedNode.data.config.strategy_id" class="config-input">
                  <option :value="null">전략 선택...</option>
                  <optgroup label="스윙">
                    <option v-for="s in strategyList.filter(s=>s.strategy_type!=='scalping')" :key="s.id" :value="s.id">
                      {{ s.name }}
                    </option>
                  </optgroup>
                  <optgroup label="단타">
                    <option v-for="s in strategyList.filter(s=>s.strategy_type==='scalping')" :key="s.id" :value="s.id">
                      {{ s.name }}
                    </option>
                  </optgroup>
                </select>
              </template>
              <!-- tickers_source -->
              <select v-else-if="field.key === 'tickers_source'" v-model="selectedNode.data.config.tickers_source" class="config-input">
                <option value="ml_top">ML 상위 30개</option>
                <option value="volume_top">거래량 상위 100개</option>
              </select>
              <template v-else-if="field.key === 'account_id'">
                <select v-model="selectedNode.data.config.account_id" class="config-input">
                  <option :value="null">계좌 선택 (선택 안 하면 모의)</option>
                  <option v-for="a in accountList" :key="a.id" :value="a.id">
                    {{ a.owner_name }} — {{ a.broker }} ({{ a.account_type === 'real' ? '실계좌' : '모의' }})
                  </option>
                </select>
              </template>
              <template v-else-if="field.key === 'mode'">
                <select v-model="selectedNode.data.config.mode" class="config-input">
                  <option value="mock">Mock (백테스트)</option>
                  <option value="paper">Paper (모의 실시간)</option>
                  <option value="real">Real (실거래)</option>
                </select>
              </template>
              <template v-else-if="field.key === 'auto_start'">
                <label class="config-checkbox">
                  <input type="checkbox" v-model="selectedNode.data.config.auto_start" />
                  <span>전략 적용 즉시 봇 시작</span>
                </label>
              </template>
              <input v-else v-model="selectedNode.data.config[field.key]" class="config-input" />
            </div>
          </div>

          <!-- 전략 빌더 패널 (strategyBuilder 노드 전용) -->
          <div v-if="selectedNode?.type === 'strategyBuilder'" class="panel-section">
            <div class="section-label">전략 빌더</div>

            <!-- 타입 토글 -->
            <div class="builder-type-row">
              <button
                :class="['builder-type-btn', { active: selectedNode.data.config.strategy_type === 'swing' }]"
                @click="selectedNode.data.config.strategy_type = 'swing'"
              >📈 스윙</button>
              <button
                :class="['builder-type-btn', { active: selectedNode.data.config.strategy_type === 'scalping' }]"
                @click="selectedNode.data.config.strategy_type = 'scalping'"
              >⚡ 단타</button>
            </div>

            <!-- 전략명 -->
            <input
              v-model="selectedNode.data.config.name"
              class="config-input"
              placeholder="전략명 입력..."
              style="margin-bottom:8px"
            />

            <!-- 프리셋 -->
            <div class="builder-preset-wrap">
              <span class="config-label">프리셋</span>
              <div class="builder-presets">
                <button
                  v-for="p in builderPresets"
                  :key="p.name"
                  class="builder-preset-btn"
                  :title="p.description"
                  @click="applyBuilderPreset(p)"
                >{{ p.name }}</button>
              </div>
            </div>

            <!-- 조건 목록 -->
            <div class="config-label" style="margin-top:8px;margin-bottom:4px">조건 (AND)</div>
            <div v-for="(cond, idx) in selectedNode.data.config.conditions" :key="idx" class="builder-cond-row">
              <select v-model="cond.indicator" class="builder-sel-ind">
                <option v-for="ind in builderIndicators" :key="ind.key" :value="ind.key">{{ ind.label }}</option>
              </select>
              <select v-model="cond.condition" class="builder-sel-cond">
                <option v-for="ct in CANVAS_CONDITIONS" :key="ct.key" :value="ct.key">{{ ct.label }}</option>
              </select>
              <input v-model.number="cond.value" class="builder-val" type="number" placeholder="값" />
              <input v-if="cond.condition === 'between'" v-model.number="cond.value2" class="builder-val" type="number" placeholder="상한" />
              <button class="builder-rm" @click="selectedNode.data.config.conditions.splice(idx,1)">✕</button>
            </div>
            <button class="builder-add-btn" @click="addBuilderCondition">+ 조건 추가</button>

            <div v-if="selectedNode.data.config.saved_id" class="builder-saved-info">
              저장됨 (ID {{ selectedNode.data.config.saved_id }})
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
            <div class="msg-bubble">
              <details v-if="msg.thinking" class="thinking-block">
                <summary class="thinking-summary">💭 생각 과정 보기</summary>
                <pre class="thinking-content">{{ msg.thinking }}</pre>
              </details>
              {{ msg.content }}
            </div>
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
  marketContext:   markRaw(FlowNode),
  techIndicators:  markRaw(FlowNode),
  mlScores:        markRaw(FlowNode),
  accountConfig:   markRaw(FlowNode),
  strategy:        markRaw(FlowNode),
  strategyBuilder: markRaw(FlowNode),
  mlModel:         markRaw(FlowNode),
  llmGenerator:    markRaw(FlowNode),
  backtest:        markRaw(FlowNode),
  botApply:        markRaw(FlowNode),
}

// ── 노드 정의 ─────────────────────────────────────────────────────
const SOURCE_TYPES     = ['marketContext', 'techIndicators', 'mlScores', 'accountConfig']
const STRATEGY_TYPES   = ['strategy', 'strategyBuilder']
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
  accountConfig: {
    label: '계좌 설정', icon: '🏦', category: 'source',
    description: '브로커 계좌 및 매매 모드 설정',
    inputs: [], outputs: [{ id: 'account_config', label: '계좌 설정' }],
    config: { account_id: null, mode: 'mock' }, apiPath: null,
  },
  strategy: {
    label: '기존 전략', icon: '📋', category: 'strategy',
    description: 'DB에서 전략 선택',
    inputs: [], outputs: [{ id: 'strategy', label: '전략' }],
    config: { strategy_id: null }, apiPath: null,
  },
  strategyBuilder: {
    label: '전략 빌더', icon: '🔧', category: 'strategy',
    description: '조건 직접 설정 후 저장',
    inputs: [], outputs: [{ id: 'strategy', label: '전략' }],
    config: {
      name: '',
      strategy_type: 'swing',
      conditions: [{ indicator: 'rsi', condition: 'below', value: 30, value2: null }],
      saved_id: null,
    }, apiPath: null,
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
    inputs:  [{ id: 'strategy', label: '전략' }, { id: 'account_config', label: '계좌 설정' }],
    outputs: [],
    config: { bot_id: null, auto_start: true }, apiPath: '/bots', apiMethod: 'PUT',
  },
}

const STATUS_LABELS = { idle: '대기', running: '실행 중', success: '완료', error: '오류' }

const CHAT_PRESETS = [
  { label: '📊 데이터 분석 후 자동 최적화', msg: '지금 시장 데이터랑 백테스트 결과 분석해서 현재 전략 최적화해줘' },
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

// ── 전략 관련 상수 ────────────────────────────────────────────────
const CANVAS_CONDITIONS = [
  { key: 'above',        label: '초과(>)' },
  { key: 'below',        label: '미만(<)' },
  { key: 'between',      label: '사이' },
  { key: 'golden_cross', label: '골든↑' },
  { key: 'dead_cross',   label: '데드↓' },
]

const _SWING_INDICATORS = [
  { key: 'rsi', label: 'RSI' }, { key: 'macd', label: 'MACD' },
  { key: 'macd_signal', label: 'MACD Signal' }, { key: 'macd_histogram', label: 'MACD Hist' },
  { key: 'stoch_k', label: 'Stoch %K' }, { key: 'stoch_d', label: 'Stoch %D' },
  { key: 'bollinger_upper', label: 'BB 상단' }, { key: 'bollinger_middle', label: 'BB 중단' }, { key: 'bollinger_lower', label: 'BB 하단' },
  { key: 'ma_20', label: 'MA 20' }, { key: 'ma_50', label: 'MA 50' }, { key: 'ma_200', label: 'MA 200' },
  { key: 'adx', label: 'ADX' }, { key: 'obv', label: 'OBV' }, { key: 'atr', label: 'ATR' },
  { key: 'volume_ratio', label: '거래량 비율' }, { key: 'opening_gap', label: '시가 갭(%)' },
]
const _SCALPING_INDICATORS = [
  { key: 'rsi', label: 'RSI' }, { key: 'macd', label: 'MACD' },
  { key: 'macd_histogram', label: 'MACD Hist' },
  { key: 'bollinger_upper', label: 'BB 상단' }, { key: 'bollinger_lower', label: 'BB 하단' },
  { key: 'ma_5', label: 'MA 5' }, { key: 'ma_10', label: 'MA 10' }, { key: 'ma_20', label: 'MA 20' },
  { key: 'volume_ratio', label: '거래량 비율' }, { key: 'opening_gap', label: '시가 갭(%)' },
  { key: 'vwap', label: 'VWAP' }, { key: 'price_vs_vwap', label: 'VWAP 대비(%)' },
  { key: 'atr', label: 'ATR' }, { key: 'ma5_minus_ma10', label: 'MA5-MA10' }, { key: 'ma5_minus_ma20', label: 'MA5-MA20' },
]
const _SWING_PRESETS = [
  { name: 'RSI 과매도', description: 'RSI 30 이하', strategy_type: 'swing',
    conditions: [{ indicator: 'rsi', condition: 'below', value: 30, value2: null }] },
  { name: 'MACD 골든크로스', description: 'MACD 0선 돌파', strategy_type: 'swing',
    conditions: [{ indicator: 'macd', condition: 'golden_cross', value: 0, value2: null }] },
  { name: '강세장 눌림목', description: 'ADX>25 + RSI 40~60', strategy_type: 'swing',
    conditions: [{ indicator: 'adx', condition: 'above', value: 25, value2: null }, { indicator: 'rsi', condition: 'between', value: 40, value2: 60 }] },
  { name: '스토캐스틱 반전', description: 'Stoch K/D 모두 20 이하', strategy_type: 'swing',
    conditions: [{ indicator: 'stoch_k', condition: 'below', value: 20, value2: null }, { indicator: 'stoch_d', condition: 'below', value: 20, value2: null }] },
]
const _SCALPING_PRESETS = [
  { name: '★ 과매도+거래량', description: 'RSI<35 + 거래량 2배', strategy_type: 'scalping',
    conditions: [{ indicator: 'rsi', condition: 'below', value: 35, value2: null }, { indicator: 'volume_ratio', condition: 'above', value: 2.0, value2: null }] },
  { name: 'VWAP 위+거래량', description: '가격>VWAP + 거래량 1.5배', strategy_type: 'scalping',
    conditions: [{ indicator: 'price_vs_vwap', condition: 'above', value: 0, value2: null }, { indicator: 'volume_ratio', condition: 'above', value: 1.5, value2: null }] },
  { name: 'MACD Hist 반전', description: 'MACD Hist 골든크로스', strategy_type: 'scalping',
    conditions: [{ indicator: 'macd_histogram', condition: 'golden_cross', value: 0, value2: null }, { indicator: 'volume_ratio', condition: 'above', value: 1.5, value2: null }] },
  { name: 'MA5↑MA20+VWAP', description: 'MA크로스 + VWAP 위', strategy_type: 'scalping',
    conditions: [{ indicator: 'ma5_minus_ma20', condition: 'golden_cross', value: 0, value2: null }, { indicator: 'price_vs_vwap', condition: 'above', value: 0, value2: null }] },
]

const builderIndicators = computed(() =>
  selectedNode.value?.data?.config?.strategy_type === 'scalping' ? _SCALPING_INDICATORS : _SWING_INDICATORS
)
const builderPresets = computed(() =>
  selectedNode.value?.data?.config?.strategy_type === 'scalping' ? _SCALPING_PRESETS : _SWING_PRESETS
)

function applyBuilderPreset(preset) {
  if (!selectedNode.value) return
  selectedNode.value.data.config.name = preset.name
  selectedNode.value.data.config.conditions = preset.conditions.map(c => ({ ...c }))
}
function addBuilderCondition() {
  if (!selectedNode.value) return
  selectedNode.value.data.config.conditions.push({ indicator: 'rsi', condition: 'below', value: null, value2: null })
}

// ── 선택된 노드 / 봇 목록 / 전략 목록 ────────────────────────────
const selectedNode = ref(null)
const botList = ref([])
const strategyList = ref([])
const accountList = ref([])

async function fetchStrategies() {
  try {
    const res = await fetch(`${API}/strategies`, { headers: headers() })
    strategyList.value = await res.json()
  } catch { /* ignore */ }
}

async function fetchAccounts() {
  try {
    const res = await fetch(`${API}/accounts`, { headers: headers() })
    accountList.value = await res.json()
  } catch { /* ignore */ }
}

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
  // strategyBuilder has dedicated panel — no generic config fields
  if (selectedNode.value.type === 'strategyBuilder') return []
  const cfg = selectedNode.value.data.config || {}
  return Object.keys(cfg).map(k => ({
    key: k,
    label: { bot_id: '봇 선택', tickers_source: '종목 소스', strategy_id: '전략 선택', auto_start: '적용 후 자동 시작', account_id: '계좌', mode: '매매 모드' }[k] || k,
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

function _checkAuth(res) {
  if (res.status === 401) throw new Error('로그인이 만료됐습니다. 다시 로그인해주세요.')
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`, { headers: headers() })
  _checkAuth(res)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST', headers: headers(true),
    body: body ? JSON.stringify(body) : undefined,
  })
  _checkAuth(res)
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

    // ── accountConfig ──────────────────────────────────────────────
    if (node.type === 'accountConfig') {
      const { account_id, mode } = node.data.config
      const account = accountList.value.find(a => a.id === account_id)
      result = { account_id: account_id || null, mode: mode || 'mock', account_label: account ? `${account.owner_name} (${account.broker})` : '모의' }
    }

    // ── marketContext ──────────────────────────────────────────────
    else if (node.type === 'marketContext') {
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

    // ── strategy (기존 전략 선택) ──────────────────────────────────
    else if (node.type === 'strategy') {
      const stratId = node.data.config.strategy_id
      if (!stratId) throw new Error('사이드 패널에서 전략을 선택하세요')
      const s = await apiGet(`/strategies/${stratId}`)
      result = {
        strategy_id: s.id,
        strategy_name: s.name,
        strategy_type: s.strategy_type,
        conditions: s.conditions,
        confidence: s.ai_confidence,
      }
    }

    // ── strategyBuilder (전략 빌더) ────────────────────────────────
    else if (node.type === 'strategyBuilder') {
      const cfg = node.data.config
      if (!cfg.name?.trim()) throw new Error('전략명을 입력하세요')
      if (!cfg.conditions?.length) throw new Error('조건을 1개 이상 추가하세요')
      const body = {
        name: cfg.name.trim(),
        strategy_type: cfg.strategy_type || 'swing',
        conditions: cfg.conditions,
        description: `캔버스 빌더: ${cfg.name}`,
      }
      let s
      if (cfg.saved_id) {
        // 업데이트
        const res = await fetch(`${API}/strategies/${cfg.saved_id}`, {
          method: 'PUT', headers: headers(true), body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error(await res.text())
        s = await res.json()
      } else {
        s = await apiPost('/strategies', body)
        node.data.config.saved_id = s.id
        await fetchStrategies()
      }
      result = {
        strategy_id: s.id,
        strategy_name: s.name,
        strategy_type: s.strategy_type,
        conditions: s.conditions,
      }
    }

    // ── botApply ──────────────────────────────────────────────────
    else if (node.type === 'botApply') {
      const strategyResult = getInputResult(nodeId, 'strategy')
      if (!strategyResult) throw new Error('전략 노드를 연결한 후 먼저 실행하세요')
      const strategyId = strategyResult.strategy_id
      if (!strategyId) throw new Error(
        strategyResult.status === 'gated'
          ? `LLM 전략이 품질 기준 미달로 저장되지 않았습니다 (${strategyResult.reason || '기준 미달'})`
          : '전략 결과에 strategy_id가 없습니다. 전략 노드를 재실행하세요'
      )
      // account_config 입력 노드에서 계좌/모드 가져오기
      const accountCfg = getInputResult(nodeId, 'account_config')
      const botMode = accountCfg?.mode || 'mock'
      const botAccountId = accountCfg?.account_id || null

      let botId = node.data.config.bot_id
      if (!botId) {
        // 봇 미지정 시 전략명 기반 봇 자동 생성
        const botName = `${strategyResult.strategy_name || '자동생성'} 봇`
        const createBody = { name: botName, mode: botMode, tickers: [], initial_cash: 10000000 }
        if (botAccountId) createBody.account_id = botAccountId
        const createRes = await fetch(`${API}/bots`, {
          method: 'POST',
          headers: headers(true),
          body: JSON.stringify(createBody),
        })
        _checkAuth(createRes)
        if (!createRes.ok) {
          const body = await createRes.json().catch(() => ({}))
          throw new Error(body.detail || '봇 자동 생성 실패')
        }
        const newBot = await createRes.json()
        botId = newBot.id
        node.data.config.bot_id = botId
        botList.value.push(newBot)
      }
      const bot = botList.value.find(b => b.id === botId)
      if (bot?.status === 'RUNNING') throw new Error('실행 중인 봇은 변경할 수 없습니다. 봇을 먼저 정지하세요.')
      const putBody = { strategy_id: strategyId }
      if (accountCfg) {
        putBody.mode = botMode
        if (botAccountId) putBody.account_id = botAccountId
      }
      const res = await fetch(`${API}/bots/${botId}`, {
        method: 'PUT',
        headers: headers(true),
        body: JSON.stringify(putBody),
      })
      _checkAuth(res)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `봇 적용 실패 (${res.status})`)
      }

      // auto_start가 켜져 있으면 봇 시작 (명시적으로 false가 아닌 한 기본 실행)
      if (node.data.config.auto_start !== false) {
        const startRes = await fetch(`${API}/bots/${botId}/start`, {
          method: 'POST',
          headers: headers(true),
        })
        _checkAuth(startRes)
        if (!startRes.ok) {
          const body = await startRes.json().catch(() => ({}))
          throw new Error(body.detail || `봇 시작 실패 (${startRes.status})`)
        }
        await fetchBotList()
      }

      const finalBot = botList.value.find(b => b.id === botId)
      result = { bot_name: finalBot?.name || botId, strategy_id: strategyId, applied: true, started: node.data.config.auto_start !== false, auto_created: !node.data.config.bot_id || node.data.config.bot_id === botId }
    }

    updateNodeData(nodeId, { status: 'success', result })
    setOutEdgeAnimated(nodeId, true)

  } catch (err) {
    updateNodeData(nodeId, { status: 'error', error: err.message })
  }
}

async function runAll() {
  // 소스 → 전략 → 처리 → 출력 순으로 실행
  const ordered = [
    ...nodes.value.filter(n => n.data.category === 'source'),
    ...nodes.value.filter(n => n.data.category === 'strategy'),
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
  return { source: '#0891b2', strategy: '#d97706', processing: '#7c3aed', output: '#059669' }[node.data?.category] ?? '#4b5563'
}

// 인사이트 데이터가 필요한 키워드
const INSIGHT_KEYWORDS = ['데이터', '분석', '최적화', '업데이트', '현황', '지금', '현재', '추천', '제안', '어때', '맞아', '봐줘', '확인']

async function fetchInsights() {
  try {
    const res = await fetch(`${API}/ai/canvas-insights`, { headers: headers() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
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
      nodes: nodes.value.map(n => ({
        id: n.id, type: n.type, status: n.data?.status,
        ...(n.data?.error ? { error: n.data.error } : {}),
      })),
      edges: edges.value.map(e => ({ source: e.source, target: e.target, source_type: nodes.value.find(n => n.id === e.source)?.type, target_type: nodes.value.find(n => n.id === e.target)?.type })),
    }

    // 데이터 분석/최적화 관련 요청이면 실시간 인사이트 포함
    const needsInsights = INSIGHT_KEYWORDS.some(k => text.includes(k))
    const insights = needsInsights ? await fetchInsights() : null

    const res = await fetch(`${API}/ai/canvas-assistant`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ message: text, canvas: canvasState, insights }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(res.status === 401 ? '로그인이 만료됐습니다. 다시 로그인해주세요.' : err.detail || `서버 오류 (${res.status})`)
    }
    const data = await res.json()
    chatMessages.value.push({ role: 'assistant', content: data.reply || '(응답 없음)', thinking: data.thinking || null })
    if (data.commands?.length) {
      const runCmds = data.commands.filter(c => c.type === 'run_node')
      if (runCmds.length) {
        chatMessages.value.push({ role: 'assistant', content: `▶ ${runCmds.map(c => c.node_type).join(' → ')} 순서로 실행합니다...` })
        await scrollChat()
      }
      await applyCommands(data.commands)
      if (runCmds.length) {
        chatMessages.value.push({ role: 'assistant', content: '✓ 실행 완료' })
        await scrollChat()
      }
    }
  } catch (err) {
    chatMessages.value.push({ role: 'assistant', content: `오류: ${err.message}` })
  } finally {
    chatLoading.value = false
    await scrollChat()
  }
}

async function applyCommands(commands) {
  // botApply의 기존 bot_id 보존 (AI가 remove 후 re-add 해도 유지)
  const prevBotId = nodes.value.find(n => n.type === 'botApply')?.data?.config?.bot_id ?? null

  for (const cmd of commands) {
    if (cmd.type === 'clear') {
      nodes.value = []
      edges.value = []
      selectedNode.value = null

    } else if (cmd.type === 'add_node') {
      addNode(cmd.node_type, cmd.x, cmd.y)
      const newNode = nodes.value[nodes.value.length - 1]
      // strategyBuilder: AI가 내려준 name을 config에 반영
      if (cmd.node_type === 'strategyBuilder' && cmd.name && newNode) {
        newNode.data.config.name = cmd.name
      }
      // botApply 재추가 시 기존 bot_id 복원
      if (cmd.node_type === 'botApply' && prevBotId && newNode) {
        newNode.data.config.bot_id = prevBotId
      }

    } else if (cmd.type === 'connect') {
      const src = nodes.value.find(n => n.type === cmd.source_type)
      const tgt = nodes.value.find(n => n.type === cmd.target_type)
      if (src && tgt) {
        // handle 미지정 시 NODE_DEFS의 첫 번째 output/input handle로 fallback
        const srcHandle = cmd.source_handle ?? NODE_DEFS[src.type]?.outputs?.[0]?.id
        const tgtHandle = cmd.target_handle ?? NODE_DEFS[tgt.type]?.inputs?.[0]?.id
        onConnect({
          source: src.id, sourceHandle: srcHandle,
          target: tgt.id, targetHandle: tgtHandle,
        })
      }

    } else if (cmd.type === 'update_config') {
      // 기존 노드 설정을 AI가 직접 업데이트
      const node = nodes.value.find(n => n.type === cmd.node_type)
      if (node && cmd.config) {
        Object.assign(node.data.config, cmd.config)
        // selectedNode도 동기화
        if (selectedNode.value?.id === node.id) {
          selectedNode.value = nodes.value.find(n => n.id === node.id) || null
        }
      }

    } else if (cmd.type === 'remove_node') {
      const node = nodes.value.find(n => n.type === cmd.node_type)
      if (node) deleteNode(node.id)

    } else if (cmd.type === 'run_node') {
      const node = nodes.value.find(n => n.type === cmd.node_type)
      if (node) {
        // 이전 run_node 완료 후 순차 실행 (await) — 선행 노드 결과가 다음 노드에 전달되도록
        await runNode(node.id)
        const updated = nodes.value.find(n => n.id === node.id)
        if (updated?.data?.status === 'error') {
          chatMessages.value.push({
            role: 'assistant',
            content: `⚠ ${cmd.node_type} 실행 실패: ${updated.data.error}`,
          })
          await scrollChat()
          break  // 실패하면 이후 명령 중단
        }
      }
    }
  }

  // ── 사후 검증: botApply 보장 ──────────────────────────────────
  const hasBotApply = nodes.value.some(n => n.type === 'botApply')
  if (!hasBotApply && nodes.value.length > 0) {
    addNode('botApply', 860, 200)
    const botNode = nodes.value[nodes.value.length - 1]
    if (prevBotId) botNode.data.config.bot_id = prevBotId
    // 전략 output을 가진 노드와 자동 연결
    const stratSrc = nodes.value.find(n =>
      NODE_DEFS[n.type]?.outputs?.some(o => o.id === 'strategy') && n.type !== 'botApply'
    )
    if (stratSrc && botNode) {
      onConnect({ source: stratSrc.id, sourceHandle: 'strategy', target: botNode.id, targetHandle: 'strategy' })
    }
    chatMessages.value.push({ role: 'assistant', content: '⚠ botApply 노드가 없어서 자동으로 추가했습니다.' })
  }

  // ── 사후 검증: 고립 노드 감지 ────────────────────────────────
  const isolated = nodes.value.filter(n =>
    !edges.value.some(e => e.source === n.id || e.target === n.id)
  )
  if (isolated.length > 0) {
    chatMessages.value.push({
      role: 'assistant',
      content: `⚠ 연결되지 않은 노드: ${isolated.map(n => NODE_DEFS[n.type]?.label || n.type).join(', ')} — 수동으로 연결하거나 다시 최적화를 요청해주세요.`,
    })
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
async function fetchBotList() {
  try {
    const res = await fetch(`${API}/bots`, { headers: headers() })
    botList.value = await res.json()
  } catch { /* ignore */ }
}

onMounted(async () => {
  loadLayout()
  await fetchBotList()
  fetchStrategies()
  fetchAccounts()
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
.palette-btn.cat-strategy   { background: rgba(217,119,6,.12); color: #fbbf24; border-color: rgba(217,119,6,.25); }
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
.cat-strategy   { background: rgba(217,119,6,.15); color: #fbbf24; }
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
.config-checkbox { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px; color: #d1d5db; }
.config-checkbox input[type="checkbox"] { accent-color: #4f9eff; width: 14px; height: 14px; cursor: pointer; }

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
.thinking-block { margin-bottom: 8px; border: 1px solid rgba(167,139,250,.25); border-radius: 6px; overflow: hidden; }
.thinking-summary { padding: 5px 8px; font-size: 11px; color: #a78bfa; cursor: pointer; user-select: none; list-style: none; }
.thinking-summary::-webkit-details-marker { display: none; }
.thinking-summary:hover { background: rgba(167,139,250,.1); }
.thinking-content { margin: 0; padding: 8px; font-size: 11px; color: #9ca3af; white-space: pre-wrap; word-break: break-word; line-height: 1.5; max-height: 300px; overflow-y: auto; border-top: 1px solid rgba(167,139,250,.15); }

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

/* ── 전략 빌더 ── */
.builder-type-row { display: flex; gap: 6px; margin-bottom: 10px; }
.builder-type-btn {
  flex: 1; padding: 5px 0;
  background: #0f1117; border: 1px solid #2a2d3e;
  border-radius: 6px; color: #6b7280; font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.builder-type-btn.active { border-color: #fbbf24; color: #fbbf24; background: rgba(217,119,6,.1); }
.builder-type-btn:not(.active):hover { border-color: #4b5563; color: #9ca3af; }

.builder-preset-wrap { margin-bottom: 2px; }
.builder-presets { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.builder-preset-btn {
  padding: 3px 10px;
  background: rgba(217,119,6,.08); border: 1px solid rgba(217,119,6,.25);
  border-radius: 20px; color: #fbbf24; font-size: 11px; cursor: pointer;
  transition: all 0.15s;
}
.builder-preset-btn:hover { background: rgba(217,119,6,.18); }

.builder-cond-row { display: flex; align-items: center; gap: 4px; margin-bottom: 6px; }
.builder-sel-ind {
  flex: 2; background: #0f1117; border: 1px solid #2a2d3e; border-radius: 5px;
  color: #e5e7eb; font-size: 11px; padding: 5px 6px; outline: none;
}
.builder-sel-cond {
  flex: 1.5; background: #0f1117; border: 1px solid #2a2d3e; border-radius: 5px;
  color: #e5e7eb; font-size: 11px; padding: 5px 4px; outline: none;
}
.builder-val {
  flex: 1; background: #0f1117; border: 1px solid #2a2d3e; border-radius: 5px;
  color: #e5e7eb; font-size: 11px; padding: 5px 6px; outline: none;
  min-width: 0;
}
.builder-val:focus, .builder-sel-ind:focus, .builder-sel-cond:focus { border-color: #fbbf24; }
.builder-rm {
  background: none; border: none; color: #6b7280; font-size: 12px; cursor: pointer;
  padding: 2px 4px; flex-shrink: 0; transition: color 0.15s;
}
.builder-rm:hover { color: #ef4444; }

.builder-add-btn {
  width: 100%; padding: 5px 0; margin-top: 2px;
  background: none; border: 1px dashed #2a2d3e;
  border-radius: 5px; color: #6b7280; font-size: 11px; cursor: pointer;
  transition: all 0.15s;
}
.builder-add-btn:hover { border-color: #fbbf24; color: #fbbf24; }

.builder-saved-info {
  margin-top: 8px; padding: 4px 8px;
  background: rgba(16,185,129,.08); border: 1px solid rgba(16,185,129,.2);
  border-radius: 5px; color: #10b981; font-size: 11px;
}
</style>
