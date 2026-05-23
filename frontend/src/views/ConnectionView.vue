<template>
  <div class="connection-view">
    <header class="page-header">
      <span class="page-eyebrow">SETUP / 연결</span>
      <h1 class="page-title">연결 설정</h1>
    </header>

    <!-- 브로커 상태 카드 -->
    <section class="section">
      <div class="section-head">
        <span class="section-title">브로커 상태</span>
      </div>

      <div class="broker-card">
        <div class="broker-info">
          <span class="mode-badge" :class="modeBadgeClass">{{ modeLabel }}</span>
          <div class="conn-status">
            <span class="dot" :class="brokerStatus.connected ? 'dot-green' : 'dot-red'"></span>
            <span>{{ connLabel }}</span>
          </div>
        </div>
        <div class="broker-actions">
          <button
            v-if="brokerStatus.mode !== 'mock'"
            class="btn-primary"
            type="button"
            :disabled="connecting"
            @click="connectBroker"
          >
            <svg
              :class="{ spin: connecting }"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M21 12a9 9 0 1 1-6-8.5" />
              <path v-if="!connecting" d="M21 4v6h-6" />
            </svg>
            <span>{{ connecting ? 'ISSUING' : 'KIS 토큰 갱신' }}</span>
          </button>
          <button class="btn-ghost" type="button" @click="fetchStatus">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
              <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
            </svg>
            <span>새로고침</span>
          </button>
        </div>
      </div>

      <!-- KIS 계좌 정보 -->
      <div v-if="brokerStatus.mode !== 'mock'" class="kis-info">
        <div class="kis-row">
          <span class="kis-label">계좌번호</span>
          <span class="kis-val mono">{{ brokerStatus.kis_account || '미설정' }}</span>
        </div>
        <div class="kis-row">
          <span class="kis-label">투자 구분</span>
          <span class="kis-val" :class="brokerStatus.kis_is_paper ? 'val-paper' : 'val-real'">
            {{ brokerStatus.kis_is_paper ? '모의투자' : '실전투자' }}
          </span>
        </div>
        <div class="kis-row">
          <span class="kis-label">토큰 만료</span>
          <span class="kis-val mono">
            {{ brokerStatus.token_ttl ? fmtTtl(brokerStatus.token_ttl) + ' 후 갱신' : '-' }}
          </span>
        </div>
      </div>

      <div v-if="connectMsg" class="msg" :class="connectOk ? 'msg-ok' : 'msg-fail'">
        <span class="msg-tag">{{ connectOk ? 'OK' : 'ERR' }}</span>
        <span>{{ connectMsg }}</span>
      </div>
    </section>

    <!-- 계좌 관리 -->
    <section class="section">
      <div class="section-head">
        <span class="section-title">계좌 관리</span>
        <button class="btn-primary small" type="button" @click="showAddAccount = true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>계좌 추가</span>
        </button>
      </div>

      <div v-if="accounts.length === 0" class="empty-accounts">
        등록된 계좌가 없습니다
      </div>

      <div v-else class="account-list">
        <div v-for="acc in accounts" :key="acc.id" class="account-item">
          <div class="acc-info">
            <span class="acc-owner">{{ acc.owner_name }}</span>
            <span class="acc-broker">{{ acc.broker }}</span>
            <span
              class="acc-type"
              :class="acc.account_type === 'real' ? 'type-real' : 'type-paper'"
            >
              {{ acc.account_type === 'real' ? '실계좌' : '모의투자' }}
            </span>
          </div>
          <button class="btn-delete" type="button" @click="deleteAccount(acc.id)">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
            </svg>
            <span>삭제</span>
          </button>
        </div>
      </div>

      <!-- 계좌 추가 폼 -->
      <div v-if="showAddAccount" class="add-account-form">
        <div class="form-head">
          <span class="form-title">계좌 추가</span>
        </div>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label" for="acc-num">계좌번호</label>
            <input
              id="acc-num"
              v-model="accountForm.account_number"
              type="text"
              placeholder="예: XXXXXXXX-XX"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="acc-owner">예금주</label>
            <input
              id="acc-owner"
              v-model="accountForm.owner_name"
              type="text"
              placeholder="이름"
            />
          </div>
          <div class="form-group">
            <label class="form-label" for="acc-broker">증권사</label>
            <select id="acc-broker" v-model="accountForm.broker">
              <option value="kis">한국투자증권 (KIS)</option>
              <option value="kiwoom">키움증권</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="acc-type">계좌 종류</label>
            <select id="acc-type" v-model="accountForm.account_type">
              <option value="paper">모의투자</option>
              <option value="real">실계좌</option>
            </select>
          </div>
        </div>
        <p v-if="accountError" class="msg msg-fail">
          <span class="msg-tag">ERR</span>
          <span>{{ accountError }}</span>
        </p>
        <div class="form-actions">
          <button class="btn-ghost" type="button" @click="showAddAccount = false">
            취소
          </button>
          <button class="btn-primary" type="button" @click="addAccount">저장</button>
        </div>
      </div>
    </section>

    <!-- 브로커 전환 방법 -->
    <section class="section">
      <div class="section-head">
        <span class="section-title">브로커 전환 가이드</span>
      </div>
      <ol class="guide-steps">
        <li v-for="(s, i) in steps" :key="i" class="step">
          <span class="step-num">{{ String(i + 1).padStart(2, '0') }}</span>
          <div class="step-body">
            <p class="step-title">{{ s.title }}</p>
            <p class="step-desc" v-html="s.desc"></p>
          </div>
        </li>
      </ol>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const brokerStatus = ref({ mode: 'mock', connected: null, kis_account: null, kis_is_paper: null, token_ttl: null })
const accounts = ref([])
const connecting = ref(false)
const connectMsg = ref('')
const connectOk = ref(true)
const showAddAccount = ref(false)
const accountError = ref('')
const accountForm = ref({ account_number: '', owner_name: '', broker: 'kis', account_type: 'real' })

const steps = [
  {
    title: 'Mock → KIS 전환',
    desc: '<code>.env</code> 파일에서 <code>BROKER_MODE=paper</code> 로 변경',
  },
  {
    title: 'KIS 키 설정',
    desc: '<code>KIS_APP_KEY</code>, <code>KIS_APP_SECRET</code>, <code>KIS_ACCOUNT_NO</code> 입력',
  },
  {
    title: '실전 / 모의투자 선택',
    desc: '실전: <code>KIS_IS_PAPER=false</code> &nbsp;|&nbsp; 모의: <code>KIS_IS_PAPER=true</code>',
  },
  {
    title: 'Docker 재시작',
    desc: '<code>docker compose up --force-recreate -d backend celery-worker celery-beat</code>',
  },
  {
    title: '토큰 발급 확인',
    desc: '이 페이지의 <strong>KIS 토큰 갱신</strong> 버튼 → 초록 점 확인',
  },
]

function headers() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

const modeLabel = computed(() => {
  const m = brokerStatus.value.mode
  if (m === 'paper') return 'KIS · PAPER'
  if (m === 'real') return 'KIS · REAL'
  return 'MOCK · 가상'
})

const modeBadgeClass = computed(() => {
  const m = brokerStatus.value.mode
  if (m === 'paper') return 'mode-paper'
  if (m === 'real') return 'mode-real'
  return 'mode-mock'
})

const connLabel = computed(() => {
  const s = brokerStatus.value
  if (s.mode === 'mock') return 'Mock 모드 활성'
  return s.connected ? 'KIS 토큰 유효' : 'KIS 토큰 없음 (갱신 필요)'
})

async function fetchStatus() {
  const res = await fetch(`${API}/broker/status`, { headers: headers() })
  if (res.ok) brokerStatus.value = await res.json()
}

async function fetchAccounts() {
  const res = await fetch(`${API}/accounts`, { headers: headers() })
  if (res.ok) accounts.value = await res.json()
}

async function connectBroker() {
  connecting.value = true
  connectMsg.value = ''
  try {
    const res = await fetch(`${API}/broker/connect`, { method: 'POST', headers: headers() })
    const data = await res.json()
    connectOk.value = data.success !== false
    connectMsg.value = data.message
    await fetchStatus()
  } finally {
    connecting.value = false
  }
}

async function addAccount() {
  if (!accountForm.value.account_number.trim() || !accountForm.value.owner_name.trim()) {
    accountError.value = '계좌번호와 예금주를 입력하세요'
    return
  }
  accountError.value = ''
  const res = await fetch(`${API}/accounts`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(accountForm.value),
  })
  if (res.ok) {
    showAddAccount.value = false
    accountForm.value = { account_number: '', owner_name: '', broker: 'kis', account_type: 'real' }
    fetchAccounts()
  } else {
    accountError.value = '추가 실패'
  }
}

async function deleteAccount(id) {
  if (!confirm('계좌를 삭제하시겠습니까?')) return
  await fetch(`${API}/accounts/${id}`, { method: 'DELETE', headers: headers() })
  fetchAccounts()
}

function fmtTtl(sec) {
  if (sec >= 3600) return Math.floor(sec / 3600) + '시간'
  if (sec >= 60) return Math.floor(sec / 60) + '분'
  return sec + '초'
}

onMounted(() => {
  fetchStatus()
  fetchAccounts()
})
</script>

<style scoped>
.connection-view {
  max-width: 880px;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ==========================================================================
   Page header
   ========================================================================== */

.page-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  margin: 0;
}

/* ==========================================================================
   Section
   ========================================================================== */

.section {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.section-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.section > .broker-card,
.section > .kis-info,
.section > .msg,
.section > .empty-accounts,
.section > .account-list,
.section > .add-account-form,
.section > .guide-steps {
  margin: var(--space-5);
}

.section > .kis-info,
.section > .msg,
.section > .add-account-form {
  margin-top: 0;
}

/* ==========================================================================
   Broker card
   ========================================================================== */

.broker-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-base);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-faint);
}

.broker-info {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.mode-badge {
  font-family: var(--font-mono);
  padding: 5px var(--space-3);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.mode-real {
  background: var(--profit-bg);
  color: var(--profit);
}

.mode-paper {
  background: var(--accent-bg);
  color: var(--accent);
}

.mode-mock {
  background: rgba(96, 165, 250, 0.14);
  color: var(--info);
}

.conn-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.dot-green {
  background: var(--up-strong);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.6);
}

.dot-red {
  background: var(--profit);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
}

.broker-actions {
  display: flex;
  gap: var(--space-2);
}

/* ==========================================================================
   KIS info rows
   ========================================================================== */

.kis-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--space-4);
  background: var(--bg-base);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-faint);
}

.kis-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--text-sm);
  padding: 4px 0;
}

.kis-label {
  font-family: var(--font-mono);
  color: var(--text-muted);
  width: 92px;
  flex-shrink: 0;
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.kis-val {
  color: var(--text-primary);
  font-weight: 500;
}

.kis-val.mono {
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wide);
}

.val-paper {
  color: var(--accent);
  font-weight: 700;
}

.val-real {
  color: var(--profit);
  font-weight: 700;
}

/* ==========================================================================
   Buttons
   ========================================================================== */

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 9px var(--space-4);
  background: var(--accent);
  color: var(--bg-base);
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
    transform var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
  box-shadow: var(--shadow-gold);
}

.btn-primary svg {
  width: 14px;
  height: 14px;
}

.btn-primary.small {
  padding: 7px var(--space-3);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.btn-primary:active:not(:disabled) {
  transform: translateY(0);
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-4);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.btn-ghost svg {
  width: 14px;
  height: 14px;
}

.btn-ghost:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-delete {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px var(--space-3);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.btn-delete svg {
  width: 13px;
  height: 13px;
}

.btn-delete:hover {
  border-color: rgba(239, 68, 68, 0.4);
  color: var(--profit);
  background: var(--profit-bg);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ==========================================================================
   Messages
   ========================================================================== */

.msg {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  border: 1px solid;
  margin: var(--space-3) 0 0;
}

.msg-ok {
  background: var(--up-bg);
  border-color: rgba(34, 197, 94, 0.25);
  color: var(--up-strong);
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
   Account list
   ========================================================================== */

.empty-accounts {
  text-align: center;
  padding: var(--space-10) var(--space-5);
  color: var(--text-faint);
  font-size: var(--text-sm);
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.account-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
  transition: border-color var(--dur-fast) var(--ease-out);
}

.account-item:hover {
  border-color: var(--border-strong);
}

.acc-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.acc-owner {
  font-size: var(--text-md);
  color: var(--text-primary);
  font-weight: 500;
}

.acc-broker {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  background: var(--surface-2);
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.acc-type {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.type-paper {
  background: var(--accent-bg);
  color: var(--accent);
}

.type-real {
  background: var(--profit-bg);
  color: var(--profit);
}

/* ==========================================================================
   Add account form
   ========================================================================== */

.add-account-form {
  padding: var(--space-4) var(--space-5);
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
}

.form-head {
  margin-bottom: var(--space-4);
}

.form-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 9px var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-md);
  outline: none;
  box-sizing: border-box;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.form-group input::placeholder {
  color: var(--text-faint);
}

.form-group input:hover,
.form-group select:hover {
  border-color: var(--border-strong);
}

.form-group input:focus,
.form-group select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

/* ==========================================================================
   Guide steps
   ========================================================================== */

.guide-steps {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.step {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
}

.step-num {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-bg);
  color: var(--accent);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  flex-shrink: 0;
  letter-spacing: var(--tracking-wide);
}

.step-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-title {
  font-size: var(--text-md);
  color: var(--text-primary);
  font-weight: 600;
  margin: 0;
}

.step-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-snug);
  margin: 0;
}

.step-desc :deep(code) {
  font-family: var(--font-mono);
  background: var(--surface-2);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  color: var(--accent);
  font-size: 12px;
  letter-spacing: var(--tracking-wide);
}

.step-desc :deep(strong) {
  color: var(--accent);
  font-weight: 700;
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 720px) {
  .broker-card {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-3);
  }
  .broker-info {
    justify-content: space-between;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
