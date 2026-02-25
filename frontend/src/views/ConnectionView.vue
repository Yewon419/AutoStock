<template>
  <div class="connection-view">
    <h1>연결 설정</h1>

    <!-- 브로커 상태 카드 -->
    <div class="section">
      <h2>브로커 모드</h2>
      <div class="broker-card">
        <div class="broker-info">
          <div class="mode-badge" :class="brokerStatus.mode === 'real' ? 'mode-real' : 'mode-mock'">
            {{ brokerStatus.mode === 'real' ? '실거래 (키움)' : 'Mock (가상)' }}
          </div>
          <div v-if="brokerStatus.mode === 'real'" class="conn-status">
            <span class="dot" :class="brokerStatus.connected ? 'dot-green' : 'dot-red'"></span>
            <span>{{ brokerStatus.connected ? '브릿지 연결됨' : '브릿지 미연결' }}</span>
          </div>
          <div v-else class="conn-status">
            <span class="dot dot-green"></span>
            <span>Mock 모드 활성</span>
          </div>
        </div>
        <div class="broker-actions">
          <button
            v-if="brokerStatus.mode === 'real'"
            class="btn-connect"
            :disabled="connecting || brokerStatus.connected"
            @click="connectBroker"
          >
            {{ connecting ? '연결 중...' : brokerStatus.connected ? '연결됨' : '키움 연결' }}
          </button>
          <button class="btn-refresh" @click="fetchStatus">새로고침</button>
        </div>
      </div>

      <div v-if="brokerStatus.mode === 'real' && !brokerStatus.connected" class="notice">
        <p>키움 브릿지 프로세스가 실행 중이어야 합니다.</p>
        <p class="code">cd kiwoom_bridge && python bridge.py</p>
      </div>
    </div>

    <!-- 계좌 관리 -->
    <div class="section">
      <div class="section-header">
        <h2>계좌 관리</h2>
        <button class="btn-primary" @click="showAddAccount = true">+ 계좌 추가</button>
      </div>

      <div v-if="accounts.length === 0" class="empty-accounts">
        등록된 계좌가 없습니다.
      </div>

      <div v-else class="account-list">
        <div v-for="acc in accounts" :key="acc.id" class="account-item">
          <div class="acc-info">
            <span class="acc-owner">{{ acc.owner_name }}</span>
            <span class="acc-broker">{{ acc.broker }}</span>
            <span class="acc-type" :class="acc.account_type === 'real' ? 'type-real' : 'type-paper'">
              {{ acc.account_type === 'real' ? '실계좌' : '모의투자' }}
            </span>
          </div>
          <button class="btn-delete" @click="deleteAccount(acc.id)">삭제</button>
        </div>
      </div>

      <!-- 계좌 추가 폼 -->
      <div v-if="showAddAccount" class="add-account-form">
        <h3>계좌 추가</h3>
        <div class="form-group">
          <label>계좌번호</label>
          <input v-model="accountForm.account_number" type="text" placeholder="예: 1234567890" />
        </div>
        <div class="form-group">
          <label>예금주</label>
          <input v-model="accountForm.owner_name" type="text" placeholder="이름" />
        </div>
        <div class="form-group">
          <label>증권사</label>
          <select v-model="accountForm.broker">
            <option value="kiwoom">키움증권</option>
          </select>
        </div>
        <div class="form-group">
          <label>계좌 종류</label>
          <select v-model="accountForm.account_type">
            <option value="paper">모의투자</option>
            <option value="real">실계좌</option>
          </select>
        </div>
        <p v-if="accountError" class="error-msg">{{ accountError }}</p>
        <div class="form-actions">
          <button class="btn-secondary" @click="showAddAccount = false">취소</button>
          <button class="btn-primary" @click="addAccount">저장</button>
        </div>
      </div>
    </div>

    <!-- BROKER_MODE 변경 안내 -->
    <div class="section guide">
      <h2>브로커 전환 방법</h2>
      <div class="guide-steps">
        <div class="step">
          <span class="step-num">1</span>
          <div>
            <p class="step-title">Mock → 키움 전환</p>
            <p class="step-desc">backend/.env 파일에서 <code>BROKER_MODE=real</code> 설정</p>
          </div>
        </div>
        <div class="step">
          <span class="step-num">2</span>
          <div>
            <p class="step-title">Docker 재시작</p>
            <p class="step-desc"><code>docker compose up --force-recreate -d backend celery-worker celery-beat</code></p>
          </div>
        </div>
        <div class="step">
          <span class="step-num">3</span>
          <div>
            <p class="step-title">키움 브릿지 실행</p>
            <p class="step-desc">Windows에서 32-bit Python으로 <code>python kiwoom_bridge/bridge.py</code> 실행</p>
          </div>
        </div>
        <div class="step">
          <span class="step-num">4</span>
          <div>
            <p class="step-title">연결 확인</p>
            <p class="step-desc">이 페이지에서 "키움 연결" 버튼 클릭 → 로그인 창 확인</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API = 'http://localhost:8001/api/v1'

const brokerStatus = ref({ mode: 'mock', connected: null })
const accounts = ref([])
const connecting = ref(false)
const showAddAccount = ref(false)
const accountError = ref('')
const accountForm = ref({ account_number: '', owner_name: '', broker: 'kiwoom', account_type: 'paper' })

function headers() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

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
  try {
    await fetch(`${API}/broker/connect`, { method: 'POST', headers: headers() })
    setTimeout(fetchStatus, 3000)  // 3초 후 상태 재확인
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
    accountForm.value = { account_number: '', owner_name: '', broker: 'kiwoom', account_type: 'paper' }
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

onMounted(() => {
  fetchStatus()
  fetchAccounts()
})
</script>

<style scoped>
.connection-view { max-width: 800px; }

h1 { font-size: 22px; font-weight: 700; color: #e5e7eb; margin: 0 0 28px; }
h2 { font-size: 16px; font-weight: 600; color: #e5e7eb; margin: 0 0 16px; }
h3 { font-size: 14px; font-weight: 600; color: #e5e7eb; margin: 0 0 14px; }

.section {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.section-header h2 { margin: 0; }

/* 브로커 카드 */
.broker-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #0f1117;
  border-radius: 8px;
  border: 1px solid #2a2d3e;
}

.broker-info { display: flex; align-items: center; gap: 16px; }

.mode-badge {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
}
.mode-real { background: rgba(245,158,11,.15); color: #f59e0b; }
.mode-mock { background: rgba(79,158,255,.15); color: #4f9eff; }

.conn-status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #9ca3af; }

.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-green { background: #10b981; box-shadow: 0 0 6px #10b981; }
.dot-red { background: #ef4444; }

.broker-actions { display: flex; gap: 8px; }

.btn-connect {
  padding: 8px 18px;
  background: #10b981;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-connect:hover { background: #059669; }
.btn-connect:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-refresh {
  padding: 8px 14px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
}
.btn-refresh:hover { border-color: #4b5563; color: #e5e7eb; }

.notice {
  margin-top: 14px;
  padding: 12px 16px;
  background: rgba(245,158,11,.08);
  border: 1px solid rgba(245,158,11,.2);
  border-radius: 8px;
  font-size: 13px;
  color: #d97706;
}
.notice p { margin: 4px 0; }
.notice .code { font-family: monospace; background: rgba(0,0,0,.3); padding: 4px 8px; border-radius: 4px; }

/* 계좌 목록 */
.empty-accounts { color: #4b5563; font-size: 14px; text-align: center; padding: 24px 0; }

.account-list { display: flex; flex-direction: column; gap: 8px; }

.account-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
}

.acc-info { display: flex; align-items: center; gap: 12px; }
.acc-owner { font-size: 14px; color: #e5e7eb; font-weight: 500; }
.acc-broker { font-size: 12px; color: #6b7280; background: #2a2d3e; padding: 2px 8px; border-radius: 4px; }
.acc-type { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.type-paper { background: rgba(245,158,11,.15); color: #f59e0b; }
.type-real { background: rgba(239,68,68,.15); color: #ef4444; }

.btn-delete {
  padding: 5px 12px;
  background: none;
  border: 1px solid #374151;
  border-radius: 6px;
  color: #6b7280;
  font-size: 12px;
  cursor: pointer;
}
.btn-delete:hover { border-color: #ef4444; color: #ef4444; }

/* 계좌 추가 폼 */
.add-account-form {
  margin-top: 16px;
  padding: 16px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
}

.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
.form-group input, .form-group select {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  padding: 8px 10px;
  font-size: 14px;
  box-sizing: border-box;
}
.form-group input:focus, .form-group select:focus { outline: none; border-color: #4f9eff; }

.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }

.error-msg { color: #ef4444; font-size: 13px; margin: 8px 0 0; }

/* 가이드 */
.guide .guide-steps { display: flex; flex-direction: column; gap: 16px; }

.step { display: flex; gap: 14px; align-items: flex-start; }

.step-num {
  width: 28px; height: 28px;
  background: #4f9eff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
  flex-shrink: 0;
}

.step-title { font-size: 14px; color: #e5e7eb; font-weight: 500; margin: 0 0 4px; }
.step-desc { font-size: 13px; color: #6b7280; margin: 0; }
.step-desc code { background: #2a2d3e; padding: 1px 6px; border-radius: 4px; font-family: monospace; color: #9ca3af; }

/* 공통 버튼 */
.btn-primary {
  background: #4f9eff; color: #fff;
  border: none; border-radius: 6px;
  padding: 8px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-primary:hover { background: #3b8ae8; }

.btn-secondary {
  background: none; border: 1px solid #2a2d3e;
  border-radius: 6px; color: #9ca3af;
  padding: 8px 18px; font-size: 14px; cursor: pointer;
}
.btn-secondary:hover { border-color: #4b5563; color: #e5e7eb; }
</style>
