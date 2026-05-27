<template>
  <div v-if="open" class="kb-modal-overlay" @click.self="cancel">
    <div class="kb-modal">
      <div class="kb-modal-head">
        <span class="kb-modal-title">📚 참고자료 등록</span>
        <button class="kb-modal-x" type="button" @click="cancel" :disabled="submitting">×</button>
      </div>

      <div class="kb-modal-body">
        <!-- 자료 종류 -->
        <div class="kb-field">
          <label class="kb-label">자료 종류</label>
          <div class="kb-type-row">
            <button
              v-for="t in TYPES"
              :key="t.value"
              type="button"
              class="kb-type-btn"
              :class="{ active: sourceType === t.value }"
              :disabled="submitting"
              @click="sourceType = t.value"
            >
              <span class="kb-type-icon">{{ t.icon }}</span>
              <span class="kb-type-label">{{ t.label }}</span>
            </button>
          </div>
        </div>

        <!-- 제목 -->
        <div class="kb-field">
          <label class="kb-label">제목 <span class="kb-required">*</span></label>
          <input
            v-model="title"
            type="text"
            class="kb-input"
            placeholder="자료를 구분할 짧은 제목"
            :disabled="submitting"
            maxlength="500"
          />
        </div>

        <!-- URL (url·youtube 공용) -->
        <div v-if="sourceType === 'url' || sourceType === 'youtube'" class="kb-field">
          <label class="kb-label">
            {{ sourceType === 'youtube' ? 'YouTube 영상 URL' : 'URL' }}
            <span class="kb-required">*</span>
          </label>
          <input
            v-model="sourceRef"
            type="url"
            class="kb-input mono"
            :placeholder="sourceType === 'youtube'
              ? 'https://www.youtube.com/watch?v=...'
              : 'https://...'"
            :disabled="submitting"
          />
          <p v-if="sourceType === 'youtube'" class="kb-hint">
            한국어 자막 우선, 없으면 영문 fallback. 자막 비활성화 영상은 등록 실패.
          </p>
        </div>

        <!-- 텍스트 본문 (text만) -->
        <div v-if="sourceType === 'text'" class="kb-field">
          <label class="kb-label">본문 <span class="kb-required">*</span></label>
          <textarea
            v-model="rawText"
            class="kb-textarea mono"
            rows="8"
            placeholder="책 발췌·메모·기사 본문 등 자유 형식 텍스트"
            :disabled="submitting"
          ></textarea>
          <p class="kb-hint">{{ rawText.length.toLocaleString() }} 자 입력</p>
        </div>

        <!-- PDF 파일 (pdf만) -->
        <div v-if="sourceType === 'pdf'" class="kb-field">
          <label class="kb-label">PDF 파일 <span class="kb-required">*</span></label>
          <input
            ref="fileInput"
            type="file"
            accept="application/pdf,.pdf"
            class="kb-file"
            :disabled="submitting"
            @change="onFileSelect"
          />
          <p v-if="pdfFile" class="kb-hint">
            {{ pdfFile.name }} ({{ (pdfFile.size / 1024 / 1024).toFixed(2) }} MB)
          </p>
          <p class="kb-hint">
            최대 20MB. 업로드 시점에 텍스트만 추출하고 파일 자체는 서버에 저장하지 않음.
          </p>
        </div>

        <p v-if="error" class="kb-error">{{ error }}</p>
      </div>

      <div class="kb-modal-foot">
        <button class="kb-btn-ghost" type="button" :disabled="submitting" @click="cancel">취소</button>
        <button
          class="kb-btn-primary"
          type="button"
          :disabled="!canSubmit || submitting"
          @click="submit"
        >
          <span v-if="!submitting">등록 → 자동 분석</span>
          <span v-else>등록 중…</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  open: { type: Boolean, default: false },
  botId: { type: Number, required: true },
})

const emit = defineEmits(['close', 'submitted'])

const TYPES = [
  { value: 'text',    icon: '📝', label: '텍스트' },
  { value: 'url',     icon: '🔗', label: 'URL' },
  { value: 'youtube', icon: '▶',  label: 'YouTube' },
  { value: 'pdf',     icon: '📄', label: 'PDF' },
]

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'
const auth = useAuthStore()

const PDF_MAX_BYTES = 20_000_000

const sourceType = ref('text')
const title = ref('')
const sourceRef = ref('')
const rawText = ref('')
const pdfFile = ref(null)
const fileInput = ref(null)
const submitting = ref(false)
const error = ref(null)

const canSubmit = computed(() => {
  if (!title.value.trim()) return false
  if (sourceType.value === 'text') return rawText.value.trim().length > 0
  if (sourceType.value === 'pdf')  return pdfFile.value != null
  return sourceRef.value.trim().length > 0
})

watch(() => props.open, (v) => {
  if (v) {
    sourceType.value = 'text'
    title.value = ''
    sourceRef.value = ''
    rawText.value = ''
    pdfFile.value = null
    error.value = null
    submitting.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
})

function onFileSelect(e) {
  const f = e.target.files?.[0]
  if (!f) { pdfFile.value = null; return }
  if (f.size > PDF_MAX_BYTES) {
    error.value = `파일 크기 초과 (${(f.size/1024/1024).toFixed(2)} MB > 20 MB)`
    e.target.value = ''
    pdfFile.value = null
    return
  }
  if (!f.name.toLowerCase().endsWith('.pdf')) {
    error.value = 'PDF 파일만 업로드 가능합니다'
    e.target.value = ''
    pdfFile.value = null
    return
  }
  pdfFile.value = f
  error.value = null
  if (!title.value.trim()) {
    // 파일명 기반 자동 title (사용자 수정 가능)
    title.value = f.name.replace(/\.pdf$/i, '')
  }
}

function cancel() {
  if (submitting.value) return
  emit('close', { cancelled: true })
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  error.value = null
  try {
    let res
    if (sourceType.value === 'pdf') {
      const form = new FormData()
      form.append('title', title.value.trim())
      form.append('file', pdfFile.value)
      res = await fetch(`${API}/trading/bots/${props.botId}/knowledge-sources/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },  // multipart: Content-Type 미지정
        body: form,
      })
    } else {
      const body = {
        source_type: sourceType.value,
        title: title.value.trim(),
        source_ref: (sourceType.value === 'url' || sourceType.value === 'youtube')
          ? sourceRef.value.trim()
          : null,
        raw_text: sourceType.value === 'text' ? rawText.value : null,
      }
      res = await fetch(`${API}/trading/bots/${props.botId}/knowledge-sources`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${auth.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
    }
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `등록 실패 (HTTP ${res.status})`)
    }
    const source = await res.json()
    emit('submitted', source)
    emit('close', { cancelled: false })
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.kb-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal, 1000);
}

.kb-modal {
  width: min(560px, 92vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--surface-1, #0d1118);
  border: 1px solid var(--accent-border, rgba(245,158,11,0.2));
  border-radius: var(--radius-lg, 12px);
  box-shadow: var(--shadow-gold, 0 4px 24px -8px rgba(245,158,11,0.5));
  color: var(--text-primary, #fafafa);
  font-family: var(--font-sans, system-ui);
}

.kb-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--surface-2, #14181f);
}
.kb-modal-title {
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent, #f59e0b);
}
.kb-modal-x {
  background: transparent;
  border: none;
  color: var(--text-tertiary, #a1a1aa);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
}
.kb-modal-x:hover:not(:disabled) { color: var(--text-primary, #fafafa); }

.kb-modal-body {
  padding: 16px 18px;
  overflow-y: auto;
}

.kb-field { margin-bottom: 16px; }
.kb-field:last-child { margin-bottom: 0; }

.kb-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary, #a1a1aa);
  margin-bottom: 6px;
}
.kb-required { color: var(--accent, #f59e0b); }

.kb-type-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.kb-type-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  background: var(--surface-2, #14181f);
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 6px);
  color: var(--text-secondary, #d4d4d8);
  cursor: pointer;
  transition: all 0.15s;
}
.kb-type-btn:hover:not(:disabled) { background: var(--surface-1, #0d1118); }
.kb-type-btn.active {
  background: var(--accent-bg, rgba(245,158,11,0.14));
  border-color: var(--accent, #f59e0b);
  color: var(--accent, #f59e0b);
}
.kb-type-icon { font-size: 18px; }
.kb-type-label { font-size: 11px; font-weight: 600; }

.kb-input, .kb-textarea {
  width: 100%;
  padding: 8px 10px;
  background: var(--bg-base, #050507);
  border: 1px solid var(--surface-2, #14181f);
  border-radius: var(--radius-sm, 6px);
  color: var(--text-primary, #fafafa);
  font-size: 13px;
  font-family: inherit;
  box-sizing: border-box;
}
.kb-textarea { resize: vertical; min-height: 120px; }
.kb-input:focus, .kb-textarea:focus {
  outline: none;
  border-color: var(--accent, #f59e0b);
}
.kb-input.mono, .kb-textarea.mono {
  font-family: var(--font-mono, ui-monospace, "SF Mono", Menlo, monospace);
  font-size: 12px;
}

.kb-file {
  width: 100%;
  padding: 6px;
  background: var(--bg-base, #050507);
  border: 1px dashed var(--surface-2, #14181f);
  border-radius: var(--radius-sm, 6px);
  color: var(--text-secondary, #d4d4d8);
  font-size: 12px;
  cursor: pointer;
}
.kb-file:hover:not(:disabled) { border-color: var(--accent, #f59e0b); }
.kb-file::file-selector-button {
  margin-right: 10px;
  padding: 4px 10px;
  background: var(--accent-bg, rgba(245,158,11,0.14));
  border: 1px solid var(--accent-border, rgba(245,158,11,0.2));
  border-radius: var(--radius-sm, 6px);
  color: var(--accent, #f59e0b);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.kb-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-muted, #71717a);
}
.kb-error {
  margin: 0 0 6px;
  padding: 8px 10px;
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: var(--radius-sm, 6px);
  color: #fca5a5;
  font-size: 12px;
}

.kb-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--surface-2, #14181f);
}
.kb-btn-ghost, .kb-btn-primary {
  padding: 8px 16px;
  border-radius: var(--radius-sm, 6px);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
}
.kb-btn-ghost {
  background: transparent;
  border: 1px solid var(--surface-2, #14181f);
  color: var(--text-secondary, #d4d4d8);
}
.kb-btn-ghost:hover:not(:disabled) { background: var(--surface-2, #14181f); }
.kb-btn-primary {
  background: var(--accent, #f59e0b);
  border: 1px solid var(--accent, #f59e0b);
  color: #0a0c12;
}
.kb-btn-primary:hover:not(:disabled) { background: var(--accent-hover, #fbbf24); }
.kb-btn-primary:disabled, .kb-btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
