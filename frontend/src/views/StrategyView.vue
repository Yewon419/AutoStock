<template>
  <div class="strategy">
    <div class="page-header">
      <h2 class="page-title">전략 관리</h2>
      <button class="create-btn" @click="openCreate">+ 새 전략</button>
    </div>

    <div v-if="loading" class="empty">로딩 중...</div>
    <div v-else-if="strategies.length === 0" class="empty">
      <p>등록된 전략이 없습니다.</p>
      <p>우측 상단 <strong>+ 새 전략</strong> 버튼으로 전략을 만들어보세요.</p>
    </div>

    <div v-else class="strategy-grid">
      <div v-for="s in strategies" :key="s.id" class="strategy-card">
        <div class="card-top">
          <span class="card-name">{{ s.name }}</span>
          <span class="card-count">조건 {{ s.conditions.length }}개</span>
        </div>
        <p class="card-desc">{{ s.description || '설명 없음' }}</p>
        <div class="card-conditions">
          <span v-for="c in s.conditions.slice(0, 3)" :key="c.indicator + c.condition" class="cond-tag">
            {{ indicatorLabel(c.indicator) }} {{ conditionLabel(c.condition) }}
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

        <div class="field">
          <label>전략명</label>
          <input v-model="form.name" type="text" placeholder="전략명을 입력하세요" />
        </div>
        <div class="field">
          <label>설명 (선택)</label>
          <input v-model="form.description" type="text" placeholder="간단한 설명" />
        </div>

        <div class="conditions-label">
          <label>조건 (모두 충족 시 매수)</label>
          <button class="add-cond-btn" @click="addCondition">+ 조건 추가</button>
        </div>

        <div v-for="(cond, idx) in form.conditions" :key="idx" class="cond-row">
          <select v-model="cond.indicator" class="cond-select">
            <option v-for="ind in INDICATORS" :key="ind.key" :value="ind.key">{{ ind.label }}</option>
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
import { ref, onMounted } from 'vue'
import { api } from '@/api/index'

const INDICATORS = [
  { key: 'rsi', label: 'RSI' },
  { key: 'macd', label: 'MACD' },
  { key: 'macd_signal', label: 'MACD Signal' },
  { key: 'macd_histogram', label: 'MACD Histogram' },
  { key: 'stoch_k', label: 'Stoch %K' },
  { key: 'stoch_d', label: 'Stoch %D' },
  { key: 'bollinger_upper', label: 'Bollinger Upper' },
  { key: 'bollinger_middle', label: 'Bollinger Middle' },
  { key: 'bollinger_lower', label: 'Bollinger Lower' },
  { key: 'ma_20', label: 'MA 20' },
  { key: 'ma_50', label: 'MA 50' },
  { key: 'ma_200', label: 'MA 200' },
  { key: 'adx', label: 'ADX' },
  { key: 'obv', label: 'OBV' },
]

const CONDITIONS = [
  { key: 'above', label: '이상 (>)' },
  { key: 'below', label: '이하 (<)' },
  { key: 'between', label: '사이 (between)' },
  { key: 'golden_cross', label: '골든크로스 ↑' },
  { key: 'dead_cross', label: '데드크로스 ↓' },
]

function indicatorLabel(key) {
  return INDICATORS.find(i => i.key === key)?.label ?? key
}
function conditionLabel(key) {
  return CONDITIONS.find(c => c.key === key)?.label ?? key
}

const strategies = ref([])
const loading = ref(false)
const modal = ref(false)
const saving = ref(false)
const editTarget = ref(null)
const formError = ref('')

const defaultCondition = () => ({ indicator: 'rsi', condition: 'below', value: null, value2: null })
const form = ref({ name: '', description: '', conditions: [defaultCondition()] })

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
  form.value = { name: '', description: '', conditions: [defaultCondition()] }
  formError.value = ''
  modal.value = true
}

function openEdit(s) {
  editTarget.value = s
  form.value = {
    name: s.name,
    description: s.description || '',
    conditions: s.conditions.map(c => ({ ...c })),
  }
  formError.value = ''
  modal.value = true
}

function closeModal() { modal.value = false }

function addCondition() {
  form.value.conditions.push(defaultCondition())
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
  margin-bottom: 24px;
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
  align-items: center;
  margin-bottom: 8px;
}
.card-name { font-size: 16px; font-weight: 600; }
.card-count { font-size: 11px; color: #6b7280; background: #2a2d3e; padding: 2px 8px; border-radius: 10px; }
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
  width: 560px;
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
</style>
