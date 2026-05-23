<template>
  <div class="canvas-view">

    <!-- ── 툴바 ── -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="toolbar-brand">
          <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
            <path d="M19 3v3" />
            <path d="M17.5 4.5h3" />
          </svg>
          <span>AI CANVAS</span>
        </span>

        <!-- 캔버스 선택 (전역 모드에서만. 봇 모드면 봇 1:1 캔버스라 list 불필요) -->
        <div v-if="!props.botId" class="canvas-selector" :class="{ open: showCanvasMenu }" @click.stop>
          <button class="canvas-sel-btn" @click="showCanvasMenu = !showCanvasMenu">
            <span class="canvas-sel-name">{{ currentCanvasName }}</span>
            <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          <div class="canvas-menu">
            <div
              v-for="c in canvasList" :key="c.id"
              class="canvas-menu-item" :class="{ active: c.id === currentCanvasId }"
            >
              <span
                v-if="renamingId !== c.id"
                class="canvas-item-name"
                @click="switchCanvas(c.id); showCanvasMenu = false"
              >{{ c.name }}</span>
              <input
                v-else
                class="canvas-rename-input"
                v-model="renameValue"
                @keydown.enter="confirmRename"
                @keydown.esc="renamingId = null"
                @blur="confirmRename"
                ref="renameInputEl"
              />
              <span class="canvas-item-actions">
                <button class="canvas-item-btn" @click.stop="startRename(c)" title="이름 변경" aria-label="이름 변경">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 20h9" />
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
                  </svg>
                </button>
                <button class="canvas-item-btn danger" @click.stop="deleteCanvas(c.id)" title="삭제" aria-label="삭제">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </span>
            </div>
            <button class="canvas-new-btn" @click="createCanvas(); showCanvasMenu = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>새 캔버스</span>
            </button>
          </div>
        </div>

        <div
          v-for="grp in PALETTE_GROUPS" :key="grp.cat"
          class="palette-dropdown"
          :class="[`cat-${grp.cat}`, { open: openPalette === grp.cat }]"
          @click.stop="openPalette = openPalette === grp.cat ? null : grp.cat"
        >
          <button class="palette-cat-btn" :class="`cat-${grp.cat}`">
            <span>{{ grp.label }}</span>
            <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          <div class="palette-menu">
            <button
              v-for="t in grp.types" :key="t"
              @click="addNode(t); openPalette = null"
              class="palette-menu-item" :class="`cat-${grp.cat}`"
            >
              <span class="palette-emoji">{{ NODE_DEFS[t].icon }}</span>
              <span class="palette-label">{{ NODE_DEFS[t].label }}</span>
            </button>
          </div>
        </div>
      </div>
      <div class="toolbar-right">
        <span class="save-status" :class="saveStatus">
          <span v-if="saveStatus === 'pending'">대기중</span>
          <span v-else-if="saveStatus === 'saving'">저장중</span>
          <span v-else-if="saveStatus === 'saved'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            저장됨
          </span>
        </span>
        <button @click="fitToNodes" class="btn-ghost" title="모든 노드가 보이게 화면 맞춤">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
          <span>FIT</span>
        </button>
        <button @click="runAll" class="btn-primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          <span>RUN ALL</span>
        </button>
        <button @click="saveLayout(true)" class="btn-ghost" title="저장">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
          <span>SAVE</span>
        </button>
        <button @click="clearCanvas" class="btn-ghost btn-danger" title="초기화">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
          </svg>
          <span>CLEAR</span>
        </button>
      </div>
    </div>

    <!-- ── 연결 오류 토스트 ── -->
    <Transition name="fade">
      <div v-if="connectionError" class="conn-error-toast">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
        </svg>
        <span>{{ connectionError }}</span>
      </div>
    </Transition>

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
        <Background :gap="24" pattern-color="#1c2128" />
        <Controls />
        <MiniMap :node-color="miniMapColor" />

        <!-- 빈 캔버스 힌트 -->
        <div v-if="nodes.length === 0" class="canvas-hint">
          <div class="hint-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
              <path d="M19 3v3" />
              <path d="M17.5 4.5h3" />
            </svg>
          </div>
          <div class="hint-eyebrow">EMPTY CANVAS</div>
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
          <div class="panel-head-text">
            <span class="panel-eyebrow" :class="`cat-${selectedNode.data.category}`">
              {{ { source: 'SOURCE', strategy: 'STRATEGY', processing: 'PROCESSING', output: 'OUTPUT', config: 'CONFIG' }[selectedNode.data.category] }}
              <span class="panel-eyebrow-kr">
                · {{ { source: '소스', strategy: '전략', processing: '처리', output: '출력', config: '설정' }[selectedNode.data.category] }}
              </span>
            </span>
            <div class="panel-title-row">
              <span class="panel-node-icon">{{ selectedNode.data.icon }}</span>
              <h3 class="panel-node-name">{{ selectedNode.data.label }}</h3>
            </div>
          </div>
          <button @click="selectedNode = null" class="close-btn" aria-label="닫기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div class="panel-body">
          <!-- 상태 -->
          <div class="panel-section">
            <div class="section-label">STATUS · 상태</div>
            <div class="status-row">
              <span class="status-dot-lg" :class="selectedNode.data.status || 'idle'" />
              <span class="status-text">{{ STATUS_LABELS[selectedNode.data.status || 'idle'] }}</span>
            </div>
            <div v-if="selectedNode.data.error" class="status-error">
              {{ selectedNode.data.error }}
            </div>
          </div>

          <!-- 설정 (일반) -->
          <div class="panel-section" v-if="editableConfig.length">
            <div class="section-label">CONFIG · 설정</div>
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
                <button class="btn-new-bot" @click="openNewBotModal">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  <span>새 봇 생성</span>
                </button>
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
            <div class="section-label">BUILDER · 전략 빌더</div>

            <!-- 타입 토글 -->
            <div class="builder-type-row">
              <button
                :class="['builder-type-btn', { active: selectedNode.data.config.strategy_type === 'swing' }]"
                @click="selectedNode.data.config.strategy_type = 'swing'"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="3 17 9 11 13 15 21 7" />
                  <polyline points="14 7 21 7 21 14" />
                </svg>
                <span>스윙</span>
              </button>
              <button
                :class="['builder-type-btn', { active: selectedNode.data.config.strategy_type === 'scalping' }]"
                @click="selectedNode.data.config.strategy_type = 'scalping'"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
                <span>단타</span>
              </button>
            </div>

            <!-- 전략명 -->
            <input
              v-model="selectedNode.data.config.name"
              class="config-input"
              placeholder="전략명 입력..."
              style="margin-bottom: var(--space-3)"
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
            <div class="config-label" style="margin-top: var(--space-3); margin-bottom: var(--space-1)">조건 (AND)</div>
            <div v-for="(cond, idx) in selectedNode.data.config.conditions" :key="idx" class="builder-cond-row">
              <select v-model="cond.indicator" class="builder-sel-ind">
                <option v-for="ind in builderIndicators" :key="ind.key" :value="ind.key">{{ ind.label }}</option>
              </select>
              <select v-model="cond.condition" class="builder-sel-cond">
                <option v-for="ct in CANVAS_CONDITIONS" :key="ct.key" :value="ct.key">{{ ct.label }}</option>
              </select>
              <input v-model.number="cond.value" class="builder-val" type="number" placeholder="값" />
              <input v-if="cond.condition === 'between'" v-model.number="cond.value2" class="builder-val" type="number" placeholder="상한" />
              <button class="builder-rm" @click="selectedNode.data.config.conditions.splice(idx,1)" aria-label="제거">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <button class="builder-add-btn" @click="addBuilderCondition">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>조건 추가</span>
            </button>

            <div v-if="selectedNode.data.config.saved_id" class="builder-saved-info">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>저장됨 · ID {{ selectedNode.data.config.saved_id }}</span>
            </div>
          </div>

          <!-- 포트 -->
          <div class="panel-section">
            <div class="section-label">PORTS · 포트</div>
            <div v-if="selectedNode.data.inputs.length" class="port-group">
              <span class="port-label-head">IN</span>
              <span v-for="h in selectedNode.data.inputs" :key="h.id" class="port-chip port-in">{{ h.label }}</span>
            </div>
            <div v-if="selectedNode.data.outputs.length" class="port-group">
              <span class="port-label-head">OUT</span>
              <span v-for="h in selectedNode.data.outputs" :key="h.id" class="port-chip port-out">{{ h.label }}</span>
            </div>
          </div>

          <!-- ML 인사이트 (mlModel 노드 성공 시) -->
          <div
            class="panel-section"
            v-if="selectedNode.type === 'mlModel' && selectedNode.data.status === 'success'"
          >
            <div class="section-label">ML INSIGHT · 인사이트</div>
            <MlInsightPanel :api-base="API" :auth-token="auth.token" :top-n="20" />
          </div>

          <!-- 결과 -->
          <div class="panel-section" v-if="selectedNode.data.result">
            <div class="section-label">
              {{ selectedNode.type === 'mlModel' ? 'RAW · 원시 결과 (디버그)' : 'RESULT · 실행 결과' }}
            </div>
            <details v-if="selectedNode.type === 'mlModel'" class="raw-result-details">
              <summary>펼쳐서 보기</summary>
              <pre class="result-json">{{ JSON.stringify(selectedNode.data.result, null, 2) }}</pre>
            </details>
            <pre v-else class="result-json">{{ JSON.stringify(selectedNode.data.result, null, 2) }}</pre>
          </div>

          <div class="panel-actions">
            <button @click="runNode(selectedNode.id)" class="btn-run-full" :disabled="selectedNode.data.status === 'running'">
              <svg v-if="selectedNode.data.status !== 'running'" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <svg v-else class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 12a9 9 0 1 1-6-8.5" />
              </svg>
              <span>{{ selectedNode.data.status === 'running' ? 'RUNNING' : 'RUN' }}</span>
            </button>
            <button @click="deleteNode(selectedNode.id)" class="btn-delete-node">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6M14 11v6" />
              </svg>
              <span>노드 삭제</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── AI 어시스턴트 ── -->
    <div class="chat-panel" :class="{ expanded: chatExpanded }">
      <div class="chat-toggle" @click="chatExpanded = !chatExpanded">
        <span class="chat-toggle-title">
          <svg class="chat-toggle-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
            <path d="M19 3v3" />
            <path d="M17.5 4.5h3" />
          </svg>
          <span>AI · 어시스턴트</span>
        </span>
        <svg class="chat-toggle-caret" :class="{ open: chatExpanded }" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      <div v-if="chatExpanded" class="chat-body">
        <div class="chat-messages" ref="chatEl">
          <div v-for="(msg, i) in chatMessages" :key="i" class="chat-msg" :class="msg.role">
            <div class="msg-label">{{ msg.role === 'user' ? '나' : 'AI' }}</div>
            <div class="msg-bubble">
              <details v-if="msg.thinking" class="thinking-block">
                <summary class="thinking-summary">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                  </svg>
                  <span>생각 과정 보기</span>
                </summary>
                <pre class="thinking-content">{{ msg.thinking }}</pre>
              </details>
              {{ msg.content }}
            </div>
          </div>
          <div v-if="chatLoading" class="chat-msg assistant">
            <div class="msg-label">AI</div>
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
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            <span>전송</span>
          </button>
        </div>
      </div>
    </div>

  <!-- ── 새 봇 생성 미니 모달 ── -->
  <Teleport to="body">
    <div v-if="newBotModal.open" class="nb-overlay" @click.self="newBotModal.open = false">
      <div class="nb-modal" role="dialog" aria-modal="true">
        <div class="nb-header">
          <div class="nb-head-text">
            <span class="nb-eyebrow">NEW BOT · 봇 생성</span>
            <h3 class="nb-title">새 봇 만들기</h3>
          </div>
          <button @click="newBotModal.open = false" class="nb-close" aria-label="닫기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
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
            <span>{{ newBotModal.loading ? '생성 중...' : '생성' }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  </div>
</template>

<script setup>
import { ref, computed, provide, nextTick, onMounted, onUnmounted, markRaw, watch } from 'vue'
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
import MlInsightPanel from '@/components/canvas/MlInsightPanel.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API  = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

// ── 노드 타입 등록 ────────────────────────────────────────────────
const nodeTypes = {
  marketContext:    markRaw(FlowNode),
  techIndicators:   markRaw(FlowNode),
  mlScores:         markRaw(FlowNode),
  accountConfig:    markRaw(FlowNode),
  riskParams:       markRaw(FlowNode),
  strategy:         markRaw(FlowNode),
  strategyBuilder:  markRaw(FlowNode),
  mlModel:          markRaw(FlowNode),
  llmGenerator:     markRaw(FlowNode),
  backtest:         markRaw(FlowNode),
  strategyOptimize: markRaw(FlowNode),
  botApply:         markRaw(FlowNode),
}

// ── 노드 정의 ─────────────────────────────────────────────────────
const SOURCE_TYPES     = ['marketContext', 'techIndicators', 'mlScores']
const CONFIG_TYPES     = ['accountConfig', 'riskParams']
const STRATEGY_TYPES   = ['strategy', 'strategyBuilder']
const PROCESSING_TYPES = ['mlModel', 'llmGenerator', 'backtest', 'strategyOptimize']
const OUTPUT_TYPES     = ['botApply']

const PALETTE_GROUPS = [
  { cat: 'source',     label: '소스', types: SOURCE_TYPES },
  { cat: 'strategy',   label: '전략', types: STRATEGY_TYPES },
  { cat: 'processing', label: '처리', types: PROCESSING_TYPES },
  { cat: 'output',     label: '출력', types: OUTPUT_TYPES },
  { cat: 'config',     label: '설정', types: CONFIG_TYPES },
]

const openPalette = ref(null)

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
    label: '계좌 설정', icon: '🏦', category: 'config',
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
  riskParams: {
    label: '리스크 파라미터', icon: '🛡️', category: 'config',
    description: 'SL/TP/MDD/포지션 크기 등 봇 리스크 설정',
    inputs: [], outputs: [{ id: 'risk_params', label: '리스크 파라미터' }],
    config: {
      stop_loss_pct: 5.0,
      take_profit_pct: 10.0,
      max_drawdown_pct: 10.0,
      position_size_pct: 10.0,
      max_positions: 4,
      max_daily_trades: 10,
      trailing_stop_pct: null,
      confirm_bars: 1,
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
  strategyOptimize: {
    label: '전략 최적화', icon: '⚡', category: 'processing',
    description: 'Grid Search로 파라미터 최적화 → DB 업데이트',
    inputs:  [
      { id: 'strategy',         label: '전략' },
      { id: 'backtest_result',  label: '백테스트 결과 (선택)' },
    ],
    outputs: [{ id: 'strategy', label: '최적화 전략' }],
    config: { tickers_source: 'ml_top' },
    apiPath: '/ai/optimize-and-update', apiMethod: 'POST', async: true,
  },
  botApply: {
    label: '봇 적용', icon: '🎮', category: 'output',
    description: '생성된 전략을 봇에 적용',
    inputs:  [
      { id: 'strategy', label: '전략' },
      { id: 'tickers', label: '매매 종목' },
      { id: 'account_config', label: '계좌 설정' },
      { id: 'risk_params', label: '리스크 파라미터' },
    ],
    outputs: [],
    config: { bot_id: null, auto_start: true }, apiPath: '/bots', apiMethod: 'PUT',
  },
}

const STATUS_LABELS = { idle: '대기', running: '실행 중', success: '완료', error: '오류' }

const CHAT_PRESETS = [
  { label: '📊 데이터 분석 후 자동 최적화', msg: '지금 시장 데이터랑 백테스트 결과 분석해서 현재 전략 최적화해줘' },
  { label: '풀 파이프라인',   msg: '풀 파이프라인 구성해줘 (ML + LLM + 최적화)' },
  { label: '빠른 전략',      msg: 'ML 캐시와 LLM으로 빠른 전략 생성 파이프라인 만들어줘' },
  { label: '백테스트+최적화', msg: '전략빌더로 전략 만들고 백테스트 후 최적화까지 하는 파이프라인 구성해줘' },
  { label: 'ML만',          msg: 'ML 모델 학습 파이프라인만 만들어줘' },
  { label: '캔버스 설명',    msg: '현재 캔버스 구성을 설명해줘' },
]

// ── Canvas 상태 ───────────────────────────────────────────────────
const nodes = ref([])
const edges = ref([])
let nodeCounter = 0

// ── 다중 캔버스 ────────────────────────────────────────────────────
const props = defineProps({
  botId: { type: Number, required: false, default: null },
})

const canvasList      = ref([])
const currentCanvasId = ref('default')
const showCanvasMenu  = ref(false)
const renamingId      = ref(null)
const renameValue     = ref('')
const renameInputEl   = ref(null)

const currentCanvasName = computed(
  () => canvasList.value.find(c => c.id === currentCanvasId.value)?.name ?? '캔버스'
)

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
const { updateNode, findNode, removeNodes, removeEdges, fitView } = useVueFlow()

function fitToNodes() {
  if (nodes.value.length) fitView({ padding: 0.2, duration: 300 })
}

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

// ── 연결 허용 규칙 ────────────────────────────────────────────────
// 'sourceNodeType:sourceHandle' → 연결 가능한 'targetNodeType:targetHandle' 목록
const VALID_CONNECTIONS = {
  'marketContext:market_data':       ['llmGenerator:market_data'],
  'techIndicators:indicator_data':   ['mlModel:indicator_data'],
  'mlScores:ml_scores':              ['llmGenerator:ml_scores'],
  'mlModel:ml_scores':               ['llmGenerator:ml_scores', 'botApply:tickers'],
  'llmGenerator:strategy':           ['backtest:strategy', 'strategyOptimize:strategy', 'botApply:strategy', 'botApply:tickers'],
  'strategy:strategy':               ['backtest:strategy', 'strategyOptimize:strategy', 'botApply:strategy'],
  'strategyBuilder:strategy':        ['backtest:strategy', 'strategyOptimize:strategy', 'botApply:strategy'],
  'backtest:backtest_result':        ['strategyOptimize:backtest_result', 'botApply:tickers'],
  'strategyOptimize:strategy':       ['botApply:strategy', 'botApply:tickers'],
  'accountConfig:account_config':    ['botApply:account_config'],
  'riskParams:risk_params':          ['botApply:risk_params'],
}

const connectionError = ref(null)

// ── 연결 ─────────────────────────────────────────────────────────
function onConnect(params) {
  const srcNode = nodes.value.find(n => n.id === params.source)
  const tgtNode = nodes.value.find(n => n.id === params.target)
  if (!srcNode || !tgtNode) return

  const key = `${srcNode.type}:${params.sourceHandle}`
  const allowed = VALID_CONNECTIONS[key] ?? []
  const targetKey = `${tgtNode.type}:${params.targetHandle}`

  if (!allowed.includes(targetKey)) {
    const srcLabel = NODE_DEFS[srcNode.type]?.label ?? srcNode.type
    const tgtLabel = NODE_DEFS[tgtNode.type]?.label ?? tgtNode.type
    connectionError.value = `연결 불가: ${srcLabel} [${params.sourceHandle}] → ${tgtLabel} [${params.targetHandle}]`
    setTimeout(() => { connectionError.value = null }, 4000)
    return
  }

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

async function pollTask(basePath, taskId, timeoutMs = 300000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 3000))
    const res = await apiGet(`${basePath}/${taskId}`)
    if (res.status === 'completed') return res.result ?? res
    if (res.status === 'failed') throw new Error(res.error || '태스크 실패')
  }
  throw new Error('태스크 타임아웃 (5분 초과)')
}

// 연결된 상위 노드 결과 수집
function getInputResult(nodeId, handleId) {
  // targetHandle 정확히 일치하는 엣지 우선
  let edge = edges.value.find(e => e.target === nodeId && e.targetHandle === handleId)
  // 못 찾으면 같은 핸들명을 출력하는 소스 노드 중 연결된 것 검색 (핸들 미설정 대비)
  if (!edge) edge = edges.value.find(e => e.target === nodeId && e.sourceHandle === handleId)
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
      const allSorted = Object.keys(scores).sort((a, b) => (scores[b] || 0) - (scores[a] || 0))
      result = { top_tickers: allSorted.length, top5: allSorted.slice(0, 5), tickers: allSorted, meta: data.meta, raw: scores }
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
      if (raw.status === 'gated') throw new Error(`전략 품질 기준 미달: ${raw.gate_reason || '조건 미충족'}`)
      if (raw.status === 'error') throw new Error(raw.message || 'LLM 전략 생성 실패')
      result = raw
    }

    // ── backtest ──────────────────────────────────────────────────
    else if (node.type === 'backtest') {
      const strategyResult = getInputResult(nodeId, 'strategy')
      const strategyId = strategyResult?.strategy_id
      if (!strategyId) throw new Error('전략 노드를 먼저 연결하고 실행하세요 (llmGenerator, strategyBuilder, strategy 중 하나)')
      const res = await apiPost('/ai/backtest-strategy', {
        strategy_id: strategyId,
        tickers_source: node.data.config.tickers_source || 'ml_top',
      })
      result = await pollTask('/ai/backtest-strategy', res.task_id)
    }

    // ── strategyOptimize ──────────────────────────────────────────
    else if (node.type === 'strategyOptimize') {
      const strategyResult = getInputResult(nodeId, 'strategy')
      const strategyId = strategyResult?.strategy_id
      if (!strategyId) throw new Error('전략 노드를 먼저 연결하고 실행하세요 (llmGenerator, strategyBuilder, strategy 중 하나)')
      const res = await apiPost('/ai/optimize-and-update', {
        strategy_id: strategyId,
        tickers_source: node.data.config.tickers_source || 'ml_top',
      })
      result = await pollTask('/ai/optimize-and-update', res.task_id)
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

    // ── botApply (봇 모드: 연결된 strategyBuilder·riskParams를 그 봇에 직접 적용) ──
    else if (node.type === 'botApply' && props.botId !== null) {
      const stratEdge = edges.value.find(e => e.target === nodeId && e.targetHandle === 'strategy')
      const riskEdge  = edges.value.find(e => e.target === nodeId && e.targetHandle === 'risk_params')
      const stratSrc = stratEdge ? nodes.value.find(n => n.id === stratEdge.source) : null
      const riskSrc  = riskEdge ? nodes.value.find(n => n.id === riskEdge.source) : null

      const conditions = Array.isArray(stratSrc?.data?.config?.conditions)
        ? stratSrc.data.config.conditions
        : null
      const riskParams = (riskSrc?.data?.config && typeof riskSrc.data.config === 'object')
        ? { ...riskSrc.data.config }
        : null

      if (!conditions && !riskParams) {
        throw new Error('전략 빌더 또는 리스크 파라미터 노드를 [봇 적용]에 연결하세요')
      }

      const res = await fetch(`${API}/trading/bots/${props.botId}/strategy/apply-diff`, {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          conditions,
          risk_params: riskParams,
          source: 'manual',
          llm_reasoning: '캔버스 노드 편집 적용',
        }),
      })
      _checkAuth(res)
      if (!res.ok) {
        const b = await res.json().catch(() => ({}))
        throw new Error(b.detail || `봇 적용 실패 (${res.status})`)
      }
      await res.json()
      result = {
        bot_name: `봇 #${props.botId}`,
        applied: true,
        num_trades: conditions ? conditions.length : 0,
      }
      // 봇·전략 상태 갱신
      await fetchBotList()
    }

    // ── botApply ──────────────────────────────────────────────────
    else if (node.type === 'botApply') {
      let strategyResult = getInputResult(nodeId, 'strategy')

      // strategy 노드가 미실행 상태면 config에서 직접 읽어 처리
      if (!strategyResult) {
        const stratEdge = edges.value.find(e => e.target === nodeId && (e.targetHandle === 'strategy' || e.sourceHandle === 'strategy'))
        const srcNode = stratEdge ? nodes.value.find(n => n.id === stratEdge.source) : null
        if (srcNode?.type === 'strategy' && srcNode.data?.config?.strategy_id) {
          const s = await apiGet(`/strategies/${srcNode.data.config.strategy_id}`)
          strategyResult = { strategy_id: s.id, strategy_name: s.name, strategy_type: s.strategy_type, conditions: s.conditions }
        } else if (srcNode && !srcNode.data?.result) {
          const srcLabel = NODE_DEFS[srcNode.type]?.label || srcNode.type
          throw new Error(`'${srcLabel}' 노드를 먼저 실행하세요 (연결은 됐지만 결과가 없습니다)`)
        }
      }

      if (!strategyResult) throw new Error('전략 노드를 연결한 후 실행하세요 (strategy 노드 선택 후 ▶ 실행)')
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

      // tickers 입력 노드에서 매매 종목 가져오기
      const tickersInput = getInputResult(nodeId, 'tickers')
      let botTickers = []
      if (tickersInput) {
        if (Array.isArray(tickersInput.tickers)) {
          // mlScores, mlModel, backtest 모두 tickers 배열 반환
          botTickers = tickersInput.tickers
        } else if (tickersInput.raw && typeof tickersInput.raw === 'object') {
          // fallback: mlScores raw { TICKER: score } 형태
          botTickers = Object.keys(tickersInput.raw).sort((a, b) => (tickersInput.raw[b] || 0) - (tickersInput.raw[a] || 0))
        }
      }
      if (botTickers.length === 0) {
        throw new Error('매매 종목이 비어있습니다. mlModel, backtest, 또는 strategyOptimize 노드를 [매매 종목] 핸들에 연결하고 먼저 실행하세요.')
      }

      let botId = node.data.config.bot_id
      if (!botId) {
        // 봇 미지정 시 전략명 기반 봇 자동 생성
        const botName = `${strategyResult.strategy_name || '자동생성'} 봇`
        // 전략 타입(scalping|swing)을 봇에 그대로 전파 — 미전달 시 백엔드 default가 swing이라
        // 단타 전략으로 만든 봇이 스윙 엔진에서 돌아가는 버그 발생.
        const botType = strategyResult.strategy_type === 'scalping' ? 'scalping' : 'swing'
        const createBody = {
          name: botName,
          mode: botMode,
          tickers: botTickers,
          initial_cash: 10000000,
          bot_type: botType,
        }
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
      if (botTickers.length > 0) putBody.tickers = botTickers
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
  // 설정·소스 → 전략 → 처리 → 출력 순으로 실행
  const ordered = [
    ...nodes.value.filter(n => n.data.category === 'config'),
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

function _localSave(canvasId, payload) {
  try {
    localStorage.setItem(`autostock-canvas:${canvasId}`, JSON.stringify(payload))
  } catch { /* ignore */ }
}

const INITIAL_CHAT = [{ role: 'assistant', content: '안녕하세요! 저는 AutoStock 캔버스 AI 어시스턴트입니다. 아래 프리셋을 눌러 파이프라인을 자동 구성하거나, 자유롭게 요청해보세요.' }]

function _saveChatMessages(canvasId) {
  try {
    localStorage.setItem(`autostock-chat:${canvasId}`, JSON.stringify(chatMessages.value))
  } catch { /* ignore */ }
}

function _loadChatMessages(canvasId) {
  try {
    const saved = localStorage.getItem(`autostock-chat:${canvasId}`)
    chatMessages.value = saved ? JSON.parse(saved) : [...INITIAL_CHAT]
  } catch {
    chatMessages.value = [...INITIAL_CHAT]
  }
}

async function _remoteSave(canvasId, payload) {
  try {
    await fetch(`${API}/ai/canvas-state`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ ...payload, canvas_id: canvasId }),
    })
  } catch { /* ignore — localStorage가 fallback */ }
}

function _buildPayload() {
  const cleanNodes = nodes.value.map(n => ({
    ...n,
    data: { ...n.data, status: 'idle', result: null, error: null },
  }))
  return { nodes: cleanNodes, edges: edges.value }
}

async function saveLayout(manual = false) {
  const payload = _buildPayload()
  _localSave(currentCanvasId.value, payload)
  saveStatus.value = 'saving'
  await _remoteSave(currentCanvasId.value, payload)
  saveStatus.value = 'saved'
  if (manual) {
    setTimeout(() => { saveStatus.value = '' }, 2000)
  }
}

function _scheduleAutoSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveLayout(false), 1500)
}

async function loadLayout(canvasId) {
  const cid = canvasId || currentCanvasId.value
  try {
    // 1순위: 백엔드 Redis
    const res = await fetch(`${API}/ai/canvas-state?canvas_id=${cid}`, { headers: headers() })
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
    const saved = localStorage.getItem(`autostock-canvas:${cid}`)
      || (cid === 'default' ? localStorage.getItem('autostock-canvas') : null)
    if (!saved) { nodes.value = []; edges.value = []; return }
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
const chatMessages = ref([...INITIAL_CHAT])
const chatEl = ref(null)

function miniMapColor(node) {
  return { source: '#60a5fa', strategy: '#f59e0b', processing: '#a78bfa', output: '#22c55e', config: '#d97706' }[node.data?.category] ?? '#52525b'
}

// 인사이트 데이터가 필요한 키워드
const INSIGHT_KEYWORDS = ['데이터', '분석', '최적화', '업데이트', '현황', '지금', '현재', '추천', '제안', '어때', '맞아', '봐줘', '확인']
const BOT_KEYWORDS    = ['전략', '봇', '성과', '손익', '수익', '손절', '포지션', '분석', '어때', '봐줘', '확인', '점검', '진단', '조건', '문제']

async function fetchInsights() {
  try {
    const res = await fetch(`${API}/ai/canvas-insights`, { headers: headers() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

async function fetchBotContext(botIds) {
  if (!botIds?.length) return null
  try {
    const res = await fetch(`${API}/ai/bot-context?bot_ids=${botIds.join(',')}`, { headers: headers() })
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

    // botApply 노드에 봇이 설정돼 있고 봇/전략 관련 질문이면 성과 컨텍스트 포함
    const botApplyNode = nodes.value.find(n => n.type === 'botApply')
    const configuredBotId = botApplyNode?.data?.config?.bot_id
    const needsBotContext = configuredBotId && BOT_KEYWORDS.some(k => text.includes(k))
    const botContext = needsBotContext ? await fetchBotContext([configuredBotId]) : null

    const res = await fetch(`${API}/ai/canvas-assistant`, {
      method: 'POST',
      headers: headers(true),
      body: JSON.stringify({ message: text, canvas: canvasState, insights, bot_context: botContext }),
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

async function fetchCanvasList() {
  try {
    const res = await fetch(`${API}/ai/canvases`, { headers: headers() })
    if (res.ok) canvasList.value = await res.json()
  } catch { /* ignore */ }
}

async function switchCanvas(id) {
  _saveChatMessages(currentCanvasId.value)  // 현재 채팅 저장
  await saveLayout()                         // 현재 캔버스 저장
  currentCanvasId.value = id
  localStorage.setItem('autostock-last-canvas', id)
  nodes.value = []
  edges.value = []
  selectedNode.value = null
  _loadChatMessages(id)
  await loadLayout(id)
}

async function createCanvas() {
  const name = `캔버스 ${canvasList.value.length + 1}`
  const res = await fetch(`${API}/ai/canvases`, {
    method: 'POST', headers: headers(true),
    body: JSON.stringify({ name }),
  })
  if (!res.ok) return
  const newCanvas = await res.json()
  canvasList.value.push(newCanvas)
  await switchCanvas(newCanvas.id)
}

function startRename(canvas) {
  renamingId.value = canvas.id
  renameValue.value = canvas.name
  nextTick(() => {
    const el = Array.isArray(renameInputEl.value) ? renameInputEl.value[0] : renameInputEl.value
    el?.focus?.()
  })
}

async function confirmRename() {
  if (!renamingId.value) return
  const id = renamingId.value
  const name = renameValue.value.trim() || '캔버스'
  renamingId.value = null
  await fetch(`${API}/ai/canvases/${id}`, {
    method: 'PATCH', headers: headers(true),
    body: JSON.stringify({ name }),
  })
  const c = canvasList.value.find(c => c.id === id)
  if (c) c.name = name
}

async function deleteCanvas(id) {
  if (canvasList.value.length <= 1) return
  const res = await fetch(`${API}/ai/canvases/${id}`, { method: 'DELETE', headers: headers(true) })
  if (!res.ok) return
  const { canvases } = await res.json()
  canvasList.value = canvases
  if (currentCanvasId.value === id) {
    await switchCanvas(canvases[0].id)
  }
}

watch(chatMessages, () => _saveChatMessages(currentCanvasId.value), { deep: true })

function onClickOutside() { showCanvasMenu.value = false; openPalette.value = null }

async function autoSeedFromBot(bot) {
  // 자동 시드: strategyBuilder + riskParams → botApply (둘 다 연결).
  // strategyBuilder: 매수 조건 row별 시각화·편집
  // riskParams: SL/TP/MDD 등 봇 리스크 파라미터 시각화·편집
  let strategy = null
  if (bot.strategy_id) {
    try {
      const res = await fetch(`${API}/strategies/${bot.strategy_id}`, { headers: headers() })
      if (res.ok) strategy = await res.json()
    } catch { /* fetch 실패 시 빈 strategy로 시드 */ }
  }

  addNode('strategyBuilder', 80, 120)
  addNode('riskParams', 80, 360)
  addNode('botApply', 540, 240)
  const stratNode = nodes.value.find(n => n.type === 'strategyBuilder')
  const riskNode  = nodes.value.find(n => n.type === 'riskParams')
  const applyNode = nodes.value.find(n => n.type === 'botApply')

  if (stratNode) {
    const existingConditions = Array.isArray(strategy?.conditions) ? strategy.conditions : []
    stratNode.data.config = {
      ...stratNode.data.config,
      name: strategy?.name || `${bot.name} 전략`,
      strategy_type: strategy?.strategy_type || bot.bot_type || 'swing',
      conditions: existingConditions.length > 0
        ? existingConditions
        : [{ indicator: 'rsi', condition: 'below', value: 30, value2: null }],
      saved_id: bot.strategy_id ?? null,
    }
  }
  if (riskNode) {
    // 봇 컬럼에서 risk_params 추출 (NUMERIC → number 변환)
    const num = v => (v === null || v === undefined ? null : Number(v))
    riskNode.data.config = {
      stop_loss_pct: num(bot.stop_loss_pct) ?? riskNode.data.config.stop_loss_pct,
      take_profit_pct: num(bot.take_profit_pct) ?? riskNode.data.config.take_profit_pct,
      max_drawdown_pct: num(bot.max_drawdown_pct) ?? riskNode.data.config.max_drawdown_pct,
      position_size_pct: num(bot.position_size_pct) ?? riskNode.data.config.position_size_pct,
      max_positions: bot.max_positions ?? riskNode.data.config.max_positions,
      max_daily_trades: bot.max_daily_trades ?? riskNode.data.config.max_daily_trades,
      trailing_stop_pct: num(bot.trailing_stop_pct),
      confirm_bars: bot.confirm_bars ?? riskNode.data.config.confirm_bars,
    }
  }
  if (applyNode) {
    applyNode.data.config = { ...applyNode.data.config, bot_id: bot.id, auto_start: false }
  }

  const newEdges = []
  if (stratNode && applyNode) {
    newEdges.push({
      id: `edge-seed-strat-${Date.now()}`,
      source: stratNode.id, sourceHandle: 'strategy',
      target: applyNode.id, targetHandle: 'strategy',
    })
  }
  if (riskNode && applyNode) {
    newEdges.push({
      id: `edge-seed-risk-${Date.now()}`,
      source: riskNode.id, sourceHandle: 'risk_params',
      target: applyNode.id, targetHandle: 'risk_params',
    })
  }
  if (newEdges.length) edges.value = [...edges.value, ...newEdges]
}

onMounted(async () => {
  document.addEventListener('click', onClickOutside)
  if (props.botId !== null) {
    // 봇 모드: 봇 단위 캔버스 ID 강제. 목록 fetch / localStorage 미사용.
    currentCanvasId.value = `bot-${props.botId}`
    canvasList.value = [{ id: currentCanvasId.value, name: '캔버스' }]
  } else {
    await fetchCanvasList()
    const lastId = localStorage.getItem('autostock-last-canvas')
    const validId = canvasList.value.find(c => c.id === lastId)?.id
    currentCanvasId.value = validId || (canvasList.value[0]?.id ?? 'default')
  }
  _loadChatMessages(currentCanvasId.value)
  await loadLayout()
  await fetchBotList()
  fetchStrategies()
  fetchAccounts()

  // 봇 모드 + 빈 캔버스 + 봇에 strategy 있으면 자동 시드
  if (props.botId !== null && nodes.value.length === 0) {
    const bot = botList.value.find(b => b.id === props.botId)
    if (bot?.strategy_id) {
      await autoSeedFromBot(bot)
      saveLayout(true)  // 시드 결과 영속화 → 다음 진입 시 재현
    }
  }

  // 시드·로드 완료 후 모든 노드가 보이게 화면 맞춤 (임베드 환경에서 fit-view-on-init 타이밍 보강)
  await nextTick()
  setTimeout(fitToNodes, 100)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
/* ==========================================================================
   Root layout
   ========================================================================== */
.canvas-view {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  overflow: hidden;
  font-family: var(--font-sans);
  color: var(--text-secondary);
}

/* ==========================================================================
   Toolbar
   ========================================================================== */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-5);
  height: 52px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-faint);
  flex-shrink: 0;
  gap: var(--space-2);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.toolbar-brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3) 0 0;
  margin-right: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--accent);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  border-right: 1px solid var(--border-faint);
  height: 100%;
  flex-shrink: 0;
}

.brand-icon {
  width: 14px;
  height: 14px;
  color: var(--accent);
}

/* Caret icons (drop-down arrows) */
.caret {
  width: 10px;
  height: 10px;
  color: var(--text-muted);
  transition: transform var(--dur-fast) var(--ease-out);
}
.palette-dropdown.open .caret,
.canvas-selector.open .caret {
  transform: rotate(180deg);
  color: var(--accent);
}

/* ==========================================================================
   Canvas selector (multi-canvas dropdown)
   ========================================================================== */
.canvas-selector {
  position: relative;
}

.canvas-sel-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 5px var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  max-width: 180px;
  transition: border-color var(--dur-fast) var(--ease-out),
              background var(--dur-fast) var(--ease-out);
}
.canvas-sel-btn:hover {
  background: var(--surface-2);
  border-color: var(--border-strong);
}

.canvas-sel-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 130px;
}

.canvas-menu {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-1);
  min-width: 220px;
  z-index: var(--z-dropdown);
  box-shadow: var(--shadow-md);
}
.canvas-selector.open .canvas-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.canvas-menu-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px var(--space-2);
  border-radius: var(--radius-sm);
}
.canvas-menu-item:hover {
  background: var(--surface-2);
}
.canvas-menu-item.active {
  background: var(--accent-bg);
}

.canvas-item-name {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.canvas-menu-item.active .canvas-item-name {
  color: var(--accent);
  font-weight: 600;
}

.canvas-item-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.canvas-item-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: var(--radius-xs);
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out),
              color var(--dur-fast) var(--ease-out);
}
.canvas-item-btn svg { width: 12px; height: 12px; }
.canvas-item-btn:hover { background: var(--surface-2); color: var(--text-secondary); }
.canvas-item-btn.danger:hover { color: var(--down-strong); }

.canvas-rename-input {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid var(--accent);
  border-radius: var(--radius-xs);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  padding: 2px var(--space-2);
  outline: none;
}

.canvas-new-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  padding: 6px var(--space-2);
  border-radius: var(--radius-sm);
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--dur-fast) var(--ease-out),
              color var(--dur-fast) var(--ease-out),
              background var(--dur-fast) var(--ease-out);
}
.canvas-new-btn svg { width: 11px; height: 11px; }
.canvas-new-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

/* ==========================================================================
   Palette dropdowns
   ========================================================================== */
.palette-dropdown {
  position: relative;
}

.palette-cat-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--dur-fast) var(--ease-out);
}
.palette-cat-btn:hover { background: var(--surface-1); }
.palette-dropdown.open .palette-cat-btn {
  border-color: var(--border);
  background: var(--surface-1);
}

.palette-menu {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-1);
  z-index: var(--z-dropdown);
  min-width: 200px;
  box-shadow: var(--shadow-md);
}
.palette-dropdown.open .palette-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.palette-menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  color: var(--text-secondary);
  transition: background var(--dur-fast) var(--ease-out);
}
.palette-menu-item:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}
.palette-emoji {
  font-size: 14px;
  filter: saturate(0.85);
}

/* Category accent colors */
.palette-cat-btn.cat-source     { color: var(--info); }
.palette-cat-btn.cat-strategy   { color: var(--accent); }
.palette-cat-btn.cat-processing { color: var(--violet); }
.palette-cat-btn.cat-output     { color: var(--up-strong); }
.palette-cat-btn.cat-config     { color: var(--accent-dim); }

.palette-menu-item.cat-source     .palette-label { color: var(--info); }
.palette-menu-item.cat-strategy   .palette-label { color: var(--accent); }
.palette-menu-item.cat-processing .palette-label { color: var(--violet); }
.palette-menu-item.cat-output     .palette-label { color: var(--up-strong); }
.palette-menu-item.cat-config     .palette-label { color: var(--accent-dim); }

/* ==========================================================================
   Toolbar buttons
   ========================================================================== */
.btn-ghost,
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.btn-ghost svg,
.btn-primary svg {
  width: 12px;
  height: 12px;
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}
.btn-ghost:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}
.btn-ghost.btn-danger:hover {
  border-color: rgba(239, 68, 68, 0.35);
  color: var(--down-strong);
  background: rgba(239, 68, 68, 0.08);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-base);
  border: 1px solid var(--accent);
  box-shadow: var(--shadow-gold);
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
  transform: translateY(-1px);
}

.save-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  min-width: 64px;
  text-align: right;
  justify-content: flex-end;
  transition: color var(--dur-base) var(--ease-out);
}
.save-status svg { width: 11px; height: 11px; }
.save-status.pending { color: var(--text-muted); }
.save-status.saving  { color: var(--info); }
.save-status.saved   { color: var(--up-strong); }

/* ==========================================================================
   VueFlow canvas
   ========================================================================== */
.flow-canvas {
  flex: 1;
  background: var(--bg-base);
  font-family: var(--font-sans);
}

:deep(.vue-flow__background) {
  background: var(--bg-base) !important;
}
:deep(.vue-flow__edge-path) {
  stroke: var(--border-strong);
}
:deep(.vue-flow__edge.animated .vue-flow__edge-path) {
  animation: dashdraw 0.5s linear infinite;
  stroke: var(--info);
}

:deep(.vue-flow__controls) {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}
:deep(.vue-flow__controls-button) {
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  border-color: var(--border-faint);
  transition: background var(--dur-fast) var(--ease-out),
              color var(--dur-fast) var(--ease-out);
}
:deep(.vue-flow__controls-button:hover) {
  background: var(--surface-2);
  color: var(--accent);
}
:deep(.vue-flow__controls-button svg) {
  fill: currentColor;
}

:deep(.vue-flow__minimap) {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

/* ==========================================================================
   Empty canvas hint
   ========================================================================== */
.canvas-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}
.canvas-hint * { pointer-events: auto; }

.hint-icon {
  color: var(--text-faint);
  margin-bottom: var(--space-2);
}
.hint-icon svg { width: 32px; height: 32px; }

.hint-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}

.hint-title {
  font-size: var(--text-md);
  color: var(--text-tertiary);
  letter-spacing: var(--tracking-tight);
  margin-bottom: 2px;
}

.hint-sub {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.hint-presets {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
  flex-wrap: wrap;
  max-width: 520px;
}

.hint-preset-btn {
  padding: 5px var(--space-3);
  background: var(--violet-bg);
  border: 1px solid var(--violet-border);
  border-radius: var(--radius-full);
  color: var(--violet);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.hint-preset-btn:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: var(--violet);
  transform: translateY(-1px);
}

/* ==========================================================================
   Side panel
   ========================================================================== */
.side-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 320px;
  background: var(--bg-elevated);
  border-left: 1px solid var(--border-faint);
  display: flex;
  flex-direction: column;
  z-index: var(--z-hud);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
  flex-shrink: 0;
}

.panel-head-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.panel-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  align-self: flex-start;
}
.panel-eyebrow.cat-source     { background: rgba(96, 165, 250, 0.12); color: var(--info); }
.panel-eyebrow.cat-strategy   { background: var(--accent-bg); color: var(--accent); }
.panel-eyebrow.cat-processing { background: var(--violet-bg); color: var(--violet); }
.panel-eyebrow.cat-output     { background: var(--up-bg); color: var(--up-strong); }
.panel-eyebrow.cat-config     { background: rgba(217, 119, 6, 0.14); color: var(--accent-dim); }

.panel-eyebrow-kr {
  font-weight: 500;
  opacity: 0.85;
}

.panel-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-node-icon {
  font-size: 18px;
  filter: saturate(0.85);
}

.panel-node-name {
  margin: 0;
  font-family: var(--font-sans);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
}

.close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
  flex-shrink: 0;
}
.close-btn svg { width: 14px; height: 14px; }
.close-btn:hover {
  background: var(--surface-2);
  border-color: var(--border);
  color: var(--text-secondary);
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-5) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-bottom: var(--space-2);
}

.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.status-dot-lg {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot-lg.idle    { background: var(--text-muted); }
.status-dot-lg.running { background: var(--info); animation: pulse-dot 1s infinite; }
.status-dot-lg.success { background: var(--up-strong); }
.status-dot-lg.error   { background: var(--down-strong); }
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.status-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.status-error {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--down-strong);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: var(--radius-sm);
  line-height: var(--leading-loose);
  word-break: break-word;
}

/* Config form */
.config-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.config-row:last-child { margin-bottom: 0; }

.config-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.config-input {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  padding: 7px var(--space-3);
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}
.config-input:hover { border-color: var(--border-strong); }
.config-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.config-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.config-checkbox input[type="checkbox"] {
  accent-color: var(--accent);
  width: 14px;
  height: 14px;
  cursor: pointer;
}

/* Ports */
.port-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.port-group:last-child { margin-bottom: 0; }

.port-label-head {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
  color: var(--text-faint);
  width: 28px;
  flex-shrink: 0;
}

.port-chip {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
}
.port-in {
  background: rgba(96, 165, 250, 0.12);
  color: var(--info);
}
.port-out {
  background: var(--violet-bg);
  color: var(--violet);
}

/* Result JSON */
.result-json {
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  overflow: auto;
  max-height: 220px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: var(--leading-loose);
}

.raw-result-details summary {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px 0;
  letter-spacing: var(--tracking-wide);
}
.raw-result-details summary:hover { color: var(--accent); }

/* Panel actions */
.panel-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.btn-run-full {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: 10px 0;
  background: var(--accent);
  color: var(--bg-base);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  box-shadow: var(--shadow-gold);
  transition: all var(--dur-fast) var(--ease-out);
}
.btn-run-full svg { width: 13px; height: 13px; }
.btn-run-full:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
  transform: translateY(-1px);
}
.btn-run-full:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.btn-delete-node {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: 9px 0;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: var(--radius-sm);
  color: var(--down-strong);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.btn-delete-node svg { width: 12px; height: 12px; }
.btn-delete-node:hover {
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(239, 68, 68, 0.4);
}

.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Side panel transitions */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform var(--dur-base) var(--ease-out-expo);
}
.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

/* ==========================================================================
   Strategy builder
   ========================================================================== */
.builder-type-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.builder-type-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  flex: 1;
  padding: 7px var(--space-2);
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.builder-type-btn svg { width: 12px; height: 12px; }
.builder-type-btn.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-bg);
}
.builder-type-btn:not(.active):hover {
  border-color: var(--border-strong);
  color: var(--text-secondary);
}

.builder-preset-wrap {
  margin-bottom: var(--space-1);
}

.builder-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.builder-preset-btn {
  padding: 3px var(--space-3);
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-full);
  color: var(--accent);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.builder-preset-btn:hover {
  background: rgba(245, 158, 11, 0.22);
  border-color: var(--accent);
}

.builder-cond-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: var(--space-2);
}

.builder-sel-ind,
.builder-sel-cond,
.builder-val {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  padding: 5px 6px;
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}
.builder-sel-ind { flex: 2; min-width: 0; }
.builder-sel-cond { flex: 1.5; min-width: 0; }
.builder-val {
  flex: 1;
  min-width: 0;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.builder-sel-ind:focus,
.builder-sel-cond:focus,
.builder-val:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15);
}

.builder-rm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  border-radius: var(--radius-xs);
  transition: color var(--dur-fast) var(--ease-out),
              background var(--dur-fast) var(--ease-out);
}
.builder-rm svg { width: 12px; height: 12px; }
.builder-rm:hover {
  color: var(--down-strong);
  background: rgba(239, 68, 68, 0.1);
}

.builder-add-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  width: 100%;
  padding: 6px 0;
  margin-top: var(--space-1);
  background: transparent;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.builder-add-btn svg { width: 11px; height: 11px; }
.builder-add-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.builder-saved-info {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-2);
  padding: 4px var(--space-2);
  background: var(--up-bg);
  border: 1px solid rgba(34, 197, 94, 0.25);
  border-radius: var(--radius-xs);
  color: var(--up-strong);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}
.builder-saved-info svg { width: 11px; height: 11px; }

/* New-bot button inside config row */
.btn-new-bot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  margin-top: 6px;
  width: 100%;
  padding: 6px 0;
  background: transparent;
  border: 1px dashed var(--accent-border);
  border-radius: var(--radius-sm);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.btn-new-bot svg { width: 11px; height: 11px; }
.btn-new-bot:hover {
  background: var(--accent-bg);
  border-color: var(--accent);
}

/* ==========================================================================
   AI chat panel (bottom-fixed)
   ========================================================================== */
.chat-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-elevated);
  border-top: 1px solid var(--border-faint);
  z-index: 20;
  transition: height var(--dur-base) var(--ease-out);
  box-shadow: 0 -8px 24px -16px rgba(0, 0, 0, 0.6);
}

.chat-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  cursor: pointer;
  user-select: none;
  background: var(--surface-1);
  border-bottom: 1px solid var(--border-faint);
  transition: background var(--dur-fast) var(--ease-out);
}
.chat-toggle:hover {
  background: var(--surface-2);
}

.chat-toggle-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--violet);
}
.chat-toggle-icon-svg {
  width: 13px;
  height: 13px;
  color: var(--violet);
}

.chat-toggle-caret {
  width: 12px;
  height: 12px;
  color: var(--text-muted);
  transition: transform var(--dur-fast) var(--ease-out);
}
.chat-toggle-caret.open {
  transform: rotate(180deg);
}

.chat-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5) var(--space-4);
}

.chat-messages {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-1) 0;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.msg-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}
.chat-msg.user .msg-label {
  color: var(--accent);
  align-self: flex-end;
}
.chat-msg.assistant .msg-label {
  color: var(--violet);
}

.msg-bubble {
  max-width: 85%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  line-height: var(--leading-loose);
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-msg.user .msg-bubble {
  align-self: flex-end;
  background: var(--accent-bg);
  color: var(--text-primary);
  border: 1px solid var(--accent-border);
  border-bottom-right-radius: var(--radius-xs);
}
.chat-msg.assistant .msg-bubble {
  align-self: flex-start;
  background: var(--violet-bg);
  color: var(--text-secondary);
  border: 1px solid var(--violet-border);
  border-bottom-left-radius: var(--radius-xs);
}

.thinking-block {
  margin-bottom: var(--space-2);
  border: 1px solid var(--violet-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-base);
}
.thinking-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  color: var(--violet);
  cursor: pointer;
  user-select: none;
  list-style: none;
}
.thinking-summary svg { width: 11px; height: 11px; }
.thinking-summary::-webkit-details-marker { display: none; }
.thinking-summary:hover { background: var(--violet-bg); }
.thinking-content {
  margin: 0;
  padding: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: var(--leading-loose);
  max-height: 300px;
  overflow-y: auto;
  border-top: 1px solid var(--violet-border);
}

.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 10px var(--space-3);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--violet);
  animation: bounce 0.8s infinite;
  display: inline-block;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); }
  40% { transform: scale(1); }
}

.chat-presets {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.preset-btn {
  padding: 4px var(--space-3);
  background: var(--violet-bg);
  border: 1px solid var(--violet-border);
  border-radius: var(--radius-full);
  color: var(--violet);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.preset-btn:hover {
  background: rgba(167, 139, 250, 0.22);
  border-color: var(--violet);
}

.chat-input-row {
  display: flex;
  gap: var(--space-2);
}

.chat-input {
  flex: 1;
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  padding: 8px var(--space-3);
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}
.chat-input:hover { border-color: var(--border-strong); }
.chat-input:focus {
  border-color: var(--violet);
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.15);
}
.chat-input::placeholder { color: var(--text-faint); }

.chat-send {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-4);
  background: var(--violet);
  border: 1px solid var(--violet);
  border-radius: var(--radius-sm);
  color: #fff;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.chat-send svg { width: 12px; height: 12px; }
.chat-send:hover:not(:disabled) {
  background: var(--violet-strong);
  border-color: var(--violet-strong);
  transform: translateY(-1px);
}
.chat-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ==========================================================================
   New-bot mini modal
   ========================================================================== */
.nb-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  animation: nb-fade-in var(--dur-fast) var(--ease-out);
}
@keyframes nb-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.nb-modal {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 360px;
  overflow: hidden;
  box-shadow: var(--shadow-xl);
  animation: nb-scale-in var(--dur-base) var(--ease-out-expo);
}
@keyframes nb-scale-in {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.nb-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.nb-head-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nb-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--accent);
}

.nb-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
}

.nb-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.nb-close svg { width: 14px; height: 14px; }
.nb-close:hover {
  background: var(--surface-2);
  border-color: var(--border);
  color: var(--text-secondary);
}

.nb-body {
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.nb-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nb-row label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  color: var(--text-muted);
}

.nb-input {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  padding: 8px var(--space-3);
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}
.nb-input:hover { border-color: var(--border-strong); }
.nb-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.nb-error {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--down-strong);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: var(--radius-sm);
}

.nb-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.nb-btn-cancel,
.nb-btn-ok {
  padding: 7px var(--space-4);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}

.nb-btn-cancel {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}
.nb-btn-cancel:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.nb-btn-ok {
  background: var(--accent);
  border: 1px solid var(--accent);
  color: var(--bg-base);
  box-shadow: var(--shadow-gold);
}
.nb-btn-ok:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
  transform: translateY(-1px);
}
.nb-btn-ok:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

/* ==========================================================================
   Connection error toast
   ========================================================================== */
.conn-error-toast {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid rgba(239, 68, 68, 0.4);
  color: var(--down-soft);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  padding: 10px var(--space-5);
  border-radius: var(--radius-md);
  z-index: var(--z-toast);
  pointer-events: none;
  box-shadow: 0 8px 28px rgba(239, 68, 68, 0.22);
}
.conn-error-toast svg {
  width: 14px;
  height: 14px;
  color: var(--down-strong);
  flex-shrink: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur-base), transform var(--dur-base);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
