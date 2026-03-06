<template>
  <div class="strategy">
    <div class="page-header">
      <h2 class="page-title">전략 관리</h2>
      <button class="create-btn" @click="openCreate">+ 새 전략</button>
    </div>

    <!-- 탭 필터 -->
    <div class="type-tabs">
      <button
        v-for="tab in TYPE_TABS"
        :key="tab.key"
        class="type-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }} <span class="tab-count">{{ tabCount(tab.key) }}</span></button>
    </div>

    <div v-if="loading" class="empty">로딩 중...</div>
    <div v-else-if="filteredStrategies.length === 0" class="empty">
      <p>등록된 전략이 없습니다.</p>
      <p>우측 상단 <strong>+ 새 전략</strong> 버튼으로 전략을 만들어보세요.</p>
    </div>

    <div v-else class="strategy-grid">
      <div v-for="s in filteredStrategies" :key="s.id" class="strategy-card">
        <div class="card-top">
          <div class="card-title-row">
            <span class="card-name">{{ s.name }}</span>
            <span class="type-badge" :class="s.strategy_type">
              {{ s.strategy_type === 'scalping' ? '단타' : '스윙' }}
            </span>
          </div>
          <span class="card-count">조건 {{ s.conditions.length }}개</span>
        </div>
        <p class="card-desc">{{ s.description || '설명 없음' }}</p>
        <div class="card-conditions">
          <span v-for="c in s.conditions.slice(0, 3)" :key="c.indicator + c.condition" class="cond-tag">
            {{ indicatorLabel(c.indicator, s.strategy_type) }} {{ conditionLabel(c.condition) }}
            {{ c.value != null ? c.value : '' }}{{ c.value2 != null ? '~' + c.value2 : '' }}
          </span>
          <span v-if="s.conditions.length > 3" class="cond-tag more">+{{ s.conditions.length - 3 }}</span>
        </div>
        <div class="card-actions">
          <RouterLink :to="`/strategies/${s.id}`" class="action-btn primary">백테스트</RouterLink>
          <button class="action-btn" @click="openEdit(s)">수정</button>
          <button class="action-btn danger" @click="confirmDelete(s)">삭제</button>
        </div>
      </div>
    </div>

    <!-- 생성/수정 모달 -->
    <div v-if="modal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3 class="modal-title">{{ editTarget ? '전략 수정' : '새 전략' }}</h3>

        <!-- 전략 타입 선택 -->
        <div class="field">
          <label>전략 타입</label>
          <div class="type-selector">
            <button
              class="type-opt"
              :class="{ active: form.strategy_type === 'swing' }"
              @click="setStrategyType('swing')"
            >
              <span class="type-opt-icon">📈</span>
              <span class="type-opt-name">스윙 (Swing)</span>
              <span class="type-opt-desc">일봉 기반 · 중장기 포지션</span>
            </button>
            <button
              class="type-opt"
              :class="{ active: form.strategy_type === 'scalping' }"
              @click="setStrategyType('scalping')"
            >
              <span class="type-opt-icon">⚡</span>
              <span class="type-opt-name">단타 (Scalping)</span>
              <span class="type-opt-desc">분봉 기반 · 당일 청산</span>
            </button>
          </div>
        </div>

        <div class="field">
          <label>전략명</label>
          <input v-model="form.name" type="text" placeholder="전략명을 입력하세요" />
        </div>
        <div class="field">
          <label>설명 (선택)</label>
          <input v-model="form.description" type="text" placeholder="간단한 설명" />
        </div>

        <!-- 프리셋 -->
        <div class="field" v-if="!editTarget">
          <label>빠른 시작 (프리셋)</label>
          <div class="preset-list">
            <button
              v-for="p in currentPresets"
              :key="p.name"
              class="preset-btn"
              :class="{ active: selectedPreset === p.name }"
              @click="applyPreset(p)"
              :title="p.description"
            >{{ p.name }}</button>
          </div>
        </div>

        <!-- 지표 설명 -->
        <div class="indicator-hint" v-if="form.strategy_type === 'scalping'">
          <span class="hint-icon">⚡</span>
          분봉 지표 사용 — RSI·MACD·볼린저밴드·MA(5/10/20)·거래량비율·시가대비등락률·VWAP·ATR·MA크로스(ma5_minus_ma20 golden_cross 0)
        </div>
        <div class="indicator-hint swing" v-else>
          <span class="hint-icon">📈</span>
          일봉 지표 사용 — RSI·MACD·스토캐스틱·볼린저밴드·MA(20/50/200)·ADX·OBV
        </div>

        <div class="conditions-label">
          <label>조건 (모두 충족 시 매수)</label>
          <button class="add-cond-btn" @click="addCondition">+ 조건 추가</button>
        </div>

        <div v-for="(cond, idx) in form.conditions" :key="idx" class="cond-row">
          <select v-model="cond.indicator" class="cond-select">
            <option v-for="ind in currentIndicators" :key="ind.key" :value="ind.key">{{ ind.label }}</option>
          </select>
          <select v-model="cond.condition" class="cond-select">
            <option v-for="ct in CONDITIONS" :key="ct.key" :value="ct.key">{{ ct.label }}</option>
          </select>
          <input
            v-model.number="cond.value"
            class="cond-input"
            type="number"
            :placeholder="cond.condition === 'between' ? '하단값' : '값'"
          />
          <input
            v-if="cond.condition === 'between'"
            v-model.number="cond.value2"
            class="cond-input"
            type="number"
            placeholder="상단값"
          />
          <button class="remove-cond-btn" @click="removeCondition(idx)">✕</button>
        </div>

        <p v-if="formError" class="form-error">{{ formError }}</p>

        <div class="modal-actions">
          <button class="modal-cancel" @click="closeModal">취소</button>
          <button class="modal-save" :disabled="saving" @click="saveStrategy">
            {{ saving ? '저장 중...' : '저장' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/index'

// ── 타입 탭 ───────────────────────────────────────────────────────────
const TYPE_TABS = [
  { key: 'all', label: '전체' },
  { key: 'swing', label: '스윙' },
  { key: 'scalping', label: '단타' },
]
const activeTab = ref('all')

// ── 지표 목록 ─────────────────────────────────────────────────────────
const SWING_INDICATORS = [
  { key: 'rsi',              label: 'RSI' },
  { key: 'macd',             label: 'MACD' },
  { key: 'macd_signal',      label: 'MACD Signal' },
  { key: 'macd_histogram',   label: 'MACD Histogram' },
  { key: 'stoch_k',          label: 'Stoch %K' },
  { key: 'stoch_d',          label: 'Stoch %D' },
  { key: 'bollinger_upper',  label: '볼린저 상단' },
  { key: 'bollinger_middle', label: '볼린저 중단' },
  { key: 'bollinger_lower',  label: '볼린저 하단' },
  { key: 'ma_20',            label: 'MA 20' },
  { key: 'ma_50',            label: 'MA 50' },
  { key: 'ma_200',           label: 'MA 200' },
  { key: 'adx',              label: 'ADX' },
  { key: 'obv',              label: 'OBV' },
]

const SCALPING_INDICATORS = [
  // 기본 모멘텀
  { key: 'rsi',                label: 'RSI (분봉)' },
  { key: 'macd',               label: 'MACD (분봉)' },
  { key: 'macd_signal',        label: 'MACD Signal' },
  { key: 'macd_histogram',     label: 'MACD Histogram' },
  // 볼린저
  { key: 'bollinger_upper',    label: '볼린저 상단' },
  { key: 'bollinger_middle',   label: '볼린저 중단' },
  { key: 'bollinger_lower',    label: '볼린저 하단' },
  // 이동평균
  { key: 'ma_5',               label: 'MA 5' },
  { key: 'ma_10',              label: 'MA 10' },
  { key: 'ma_20',              label: 'MA 20' },
  // 거래량/가격
  { key: 'volume_ratio',       label: '거래량 비율 (현재/20봉평균)' },
  { key: 'opening_gap',        label: '시가대비 등락률(%)' },
  // 신규: VWAP
  { key: 'vwap',               label: 'VWAP (세션 평균)' },
  { key: 'price_vs_vwap',      label: 'VWAP 대비 등락률(%) — above 0 = 가격>VWAP' },
  // 신규: ATR
  { key: 'atr',                label: 'ATR 14 (분봉 변동성)' },
  // 신규: MA 크로스 차이값 (golden_cross value=0 으로 MA↔MA 크로스 표현)
  { key: 'ma5_minus_ma10',     label: 'MA5−MA10 (골든크로스 value=0)' },
  { key: 'ma5_minus_ma20',     label: 'MA5−MA20 (골든크로스 value=0)' },
]

const ALL_INDICATORS = [...SWING_INDICATORS, ...SCALPING_INDICATORS]

const CONDITIONS = [
  { key: 'above',        label: '초과 (>)' },
  { key: 'below',        label: '미만 (<)' },
  { key: 'between',      label: '사이 (between)' },
  { key: 'golden_cross', label: '골든크로스 ↑' },
  { key: 'dead_cross',   label: '데드크로스 ↓' },
]

function indicatorLabel(key, strategyType) {
  const list = strategyType === 'scalping' ? SCALPING_INDICATORS : SWING_INDICATORS
  return list.find(i => i.key === key)?.label ?? ALL_INDICATORS.find(i => i.key === key)?.label ?? key
}
function conditionLabel(key) {
  return CONDITIONS.find(c => c.key === key)?.label ?? key
}

// ── 프리셋 ────────────────────────────────────────────────────────────
const SWING_PRESETS = [
  {
    name: 'RSI 과매도',
    description: 'RSI 30 이하 과매도 구간 진입 종목 매수 (일봉)',
    strategy_type: 'swing',
    conditions: [{ indicator: 'rsi', condition: 'below', value: 30, value2: null }],
  },
  {
    name: 'RSI 과매수 모멘텀',
    description: 'RSI 70 이상 + ADX 25 이상 강한 상승 추세 (일봉)',
    strategy_type: 'swing',
    conditions: [
      { indicator: 'rsi', condition: 'above', value: 70, value2: null },
      { indicator: 'adx', condition: 'above', value: 25, value2: null },
    ],
  },
  {
    name: 'MACD 골든크로스',
    description: 'MACD가 0선을 상향 돌파하는 시점 매수 (일봉)',
    strategy_type: 'swing',
    conditions: [{ indicator: 'macd', condition: 'golden_cross', value: 0, value2: null }],
  },
  {
    name: '스토캐스틱 반전',
    description: 'Stoch %K/%D 모두 20 이하 과매도 반전 신호 (일봉)',
    strategy_type: 'swing',
    conditions: [
      { indicator: 'stoch_k', condition: 'below', value: 20, value2: null },
      { indicator: 'stoch_d', condition: 'below', value: 20, value2: null },
    ],
  },
  {
    name: '강세장 눌림목',
    description: 'ADX 25 이상 추세장 + RSI 40~60 눌림목 구간 (일봉)',
    strategy_type: 'swing',
    conditions: [
      { indicator: 'adx', condition: 'above', value: 25, value2: null },
      { indicator: 'rsi', condition: 'between', value: 40, value2: 60 },
    ],
  },
]

const SCALPING_PRESETS = [
  {
    name: '★ 과매도 반등 + 거래량 (추천)',
    description: 'RSI 35 이하 과매도 + 거래량 2배 급증. Mock/Real 모두 안정적으로 신호 발생',
    strategy_type: 'scalping',
    conditions: [
      { indicator: 'rsi',          condition: 'below', value: 35,  value2: null },
      { indicator: 'volume_ratio', condition: 'above', value: 2.0, value2: null },
    ],
  },
  {
    name: 'VWAP 위 + 거래량 모멘텀',
    description: '가격이 VWAP 위 + 거래량 1.5배 확인. 추세 방향 필터 포함 (Real 최적)',
    strategy_type: 'scalping',
    conditions: [
      { indicator: 'price_vs_vwap', condition: 'above', value: 0,   value2: null },
      { indicator: 'volume_ratio',  condition: 'above', value: 1.5, value2: null },
      { indicator: 'rsi',           condition: 'between', value: 40, value2: 65 },
    ],
  },
  {
    name: 'MA5↑MA20 크로스 + VWAP',
    description: 'MA5가 MA20 위로 골든크로스 + 가격이 VWAP 위. 단기 추세 전환 포착',
    strategy_type: 'scalping',
    conditions: [
      { indicator: 'ma5_minus_ma20', condition: 'golden_cross', value: 0,   value2: null },
      { indicator: 'price_vs_vwap', condition: 'above',        value: 0,   value2: null },
      { indicator: 'volume_ratio',  condition: 'above',        value: 1.3, value2: null },
    ],
  },
  {
    name: 'MACD Histogram 반전',
    description: 'MACD Histogram 음→양 전환 + 거래량 확인. 단기 추세 반전 포착',
    strategy_type: 'scalping',
    conditions: [
      { indicator: 'macd_histogram', condition: 'golden_cross', value: 0,   value2: null },
      { indicator: 'volume_ratio',   condition: 'above',        value: 1.5, value2: null },
    ],
  },
  {
    name: '갭업 초반 모멘텀',
    description: '시가 대비 1.5% 이상 갭업 + 거래량 확인. 오전 강세 초반 포착',
    strategy_type: 'scalping',
    conditions: [
      { indicator: 'opening_gap',  condition: 'above', value: 1.5, value2: null },
      { indicator: 'volume_ratio', condition: 'above', value: 1.2, value2: null },
    ],
  },
]

// ── 상태 ─────────────────────────────────────────────────────────────
const strategies = ref([])
const loading = ref(false)
const modal = ref(false)
const saving = ref(false)
const editTarget = ref(null)
const formError = ref('')
const selectedPreset = ref('')

const defaultCondition = () => ({ indicator: 'rsi', condition: 'below', value: null, value2: null })
const form = ref({ name: '', description: '', strategy_type: 'swing', conditions: [defaultCondition()] })

// ── computed ──────────────────────────────────────────────────────────
const filteredStrategies = computed(() => {
  if (activeTab.value === 'all') return strategies.value
  return strategies.value.filter(s => (s.strategy_type || 'swing') === activeTab.value)
})

const currentIndicators = computed(() =>
  form.value.strategy_type === 'scalping' ? SCALPING_INDICATORS : SWING_INDICATORS
)

const currentPresets = computed(() =>
  form.value.strategy_type === 'scalping' ? SCALPING_PRESETS : SWING_PRESETS
)

function tabCount(key) {
  if (key === 'all') return strategies.value.length
  return strategies.value.filter(s => (s.strategy_type || 'swing') === key).length
}

// ── 메서드 ────────────────────────────────────────────────────────────
function setStrategyType(type) {
  form.value.strategy_type = type
  // 타입 바꾸면 기본 조건도 해당 타입 첫 지표로 초기화
  const firstInd = type === 'scalping' ? 'rsi' : 'rsi'
  form.value.conditions = [{ indicator: firstInd, condition: 'below', value: null, value2: null }]
  selectedPreset.value = ''
}

function applyPreset(preset) {
  selectedPreset.value = preset.name
  form.value.name = preset.name
  form.value.description = preset.description
  form.value.conditions = preset.conditions.map(c => ({ ...c }))
}

async function fetchStrategies() {
  loading.value = true
  try {
    strategies.value = await api.get('/strategies')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  selectedPreset.value = ''
  form.value = { name: '', description: '', strategy_type: 'swing', conditions: [defaultCondition()] }
  formError.value = ''
  modal.value = true
}

function openEdit(s) {
  editTarget.value = s
  form.value = {
    name: s.name,
    description: s.description || '',
    strategy_type: s.strategy_type || 'swing',
    conditions: s.conditions.map(c => ({ ...c })),
  }
  formError.value = ''
  modal.value = true
}

function closeModal() { modal.value = false }

function addCondition() {
  const firstInd = form.value.strategy_type === 'scalping' ? 'rsi' : 'rsi'
  form.value.conditions.push({ indicator: firstInd, condition: 'below', value: null, value2: null })
}
function removeCondition(idx) {
  form.value.conditions.splice(idx, 1)
}

async function saveStrategy() {
  formError.value = ''
  if (!form.value.name.trim()) { formError.value = '전략명을 입력하세요'; return }
  if (form.value.conditions.length === 0) { formError.value = '조건을 하나 이상 추가하세요'; return }

  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || null,
      strategy_type: form.value.strategy_type,
      conditions: form.value.conditions,
    }
    if (editTarget.value) {
      await api.put(`/strategies/${editTarget.value.id}`, payload)
    } else {
      await api.post('/strategies', payload)
    }
    closeModal()
    await fetchStrategies()
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function confirmDelete(s) {
  if (!confirm(`"${s.name}" 전략을 삭제하시겠습니까?`)) return
  try {
    await api.delete(`/strategies/${s.id}`)
    await fetchStrategies()
  } catch (e) {
    alert(e.message)
  }
}

onMounted(fetchStrategies)
</script>

<style scoped>
.strategy { max-width: 1000px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-title { font-size: 22px; font-weight: 600; }

.create-btn {
  padding: 8px 18px;
  background: #1e3a5f;
  border: 1px solid #4f9eff;
  border-radius: 8px;
  color: #4f9eff;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.create-btn:hover { background: #4f9eff; color: #fff; }

/* 타입 탭 */
.type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.type-tab {
  padding: 7px 18px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 20px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.type-tab:hover { border-color: #4f9eff; color: #4f9eff; }
.type-tab.active { background: #1e3a5f; border-color: #4f9eff; color: #4f9eff; font-weight: 600; }
.tab-count {
  font-size: 11px;
  background: #2a2d3e;
  padding: 1px 6px;
  border-radius: 8px;
}
.type-tab.active .tab-count { background: #4f9eff22; }

.empty {
  text-align: center;
  padding: 60px;
  color: #6b7280;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  line-height: 2;
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.strategy-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  padding: 20px;
  transition: border-color 0.15s;
}
.strategy-card:hover { border-color: #4f9eff; }

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.card-name { font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-count { font-size: 11px; color: #6b7280; background: #2a2d3e; padding: 2px 8px; border-radius: 10px; flex-shrink: 0; }

/* 타입 배지 */
.type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 8px;
  flex-shrink: 0;
}
.type-badge.swing { background: #1e3a5f; color: #4f9eff; border: 1px solid #2a4a6f; }
.type-badge.scalping { background: #3a2800; color: #fb923c; border: 1px solid #5a3800; }

.card-desc { font-size: 13px; color: #6b7280; margin-bottom: 12px; min-height: 20px; }

.card-conditions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.cond-tag {
  font-size: 11px;
  padding: 3px 8px;
  background: #1e3a5f;
  border: 1px solid #2a4a6f;
  border-radius: 4px;
  color: #93c5fd;
}
.cond-tag.more { background: #2a2d3e; border-color: #3a3d4e; color: #6b7280; }

.card-actions { display: flex; gap: 8px; }
.action-btn {
  flex: 1;
  padding: 7px 0;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
  transition: all 0.15s;
}
.action-btn:hover { border-color: #4f9eff; color: #4f9eff; }
.action-btn.primary { background: #1e3a5f; border-color: #4f9eff; color: #4f9eff; }
.action-btn.primary:hover { background: #4f9eff; color: #fff; }
.action-btn.danger:hover { border-color: #ef4444; color: #ef4444; }

/* 모달 */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  padding: 32px;
  width: 580px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-title { font-size: 18px; font-weight: 700; margin-bottom: 20px; }

.field { margin-bottom: 16px; }
.field label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.field input {
  width: 100%;
  padding: 10px 12px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  box-sizing: border-box;
  outline: none;
}
.field input:focus { border-color: #4f9eff; }

/* 타입 선택 */
.type-selector {
  display: flex;
  gap: 10px;
}
.type-opt {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 10px;
  background: #0f1117;
  border: 2px solid #2a2d3e;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}
.type-opt:hover { border-color: #4f9eff44; }
.type-opt.active { border-color: #4f9eff; background: #1e3a5f22; }
.type-opt.active:last-child { border-color: #fb923c; background: #3a280022; }
.type-opt-icon { font-size: 22px; }
.type-opt-name { font-size: 14px; font-weight: 600; color: #e5e7eb; }
.type-opt-desc { font-size: 11px; color: #6b7280; }

/* 지표 힌트 */
.indicator-hint {
  font-size: 12px;
  color: #fb923c;
  background: #3a280022;
  border: 1px solid #5a380044;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.indicator-hint.swing {
  color: #4f9eff;
  background: #1e3a5f22;
  border-color: #2a4a6f44;
}
.hint-icon { font-size: 14px; }

.conditions-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.conditions-label label { font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.add-cond-btn {
  padding: 5px 12px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #4f9eff;
  font-size: 12px;
  cursor: pointer;
}
.add-cond-btn:hover { background: #1e3a5f; }

.cond-row {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 8px;
}
.cond-select, .cond-input {
  padding: 8px 10px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
}
.cond-select { flex: 1.5; }
.cond-input { flex: 1; width: 0; }
.cond-select:focus, .cond-input:focus { border-color: #4f9eff; }
.remove-cond-btn {
  padding: 6px 10px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
}
.remove-cond-btn:hover { border-color: #ef4444; color: #ef4444; }

.form-error { color: #f87171; font-size: 13px; margin: 8px 0; }

.modal-actions { display: flex; gap: 10px; margin-top: 24px; justify-content: flex-end; }
.modal-cancel {
  padding: 9px 20px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  color: #6b7280;
  font-size: 14px;
  cursor: pointer;
}
.modal-save {
  padding: 9px 24px;
  background: #4f9eff;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.modal-save:disabled { opacity: 0.5; cursor: not-allowed; }

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.preset-btn {
  padding: 6px 14px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 20px;
  color: #9ca3af;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.preset-btn:hover { border-color: #4f9eff; color: #4f9eff; background: #1e3a5f; }
.preset-btn.active { border-color: #4f9eff; color: #fff; background: #4f9eff; }
</style>
