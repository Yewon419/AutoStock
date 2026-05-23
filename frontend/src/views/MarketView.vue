<template>
  <div class="market">
    <header class="page-header">
      <div class="page-head-left">
        <span class="page-eyebrow">DATA / 마켓</span>
        <h1 class="page-title">주식 데이터</h1>
      </div>
      <button
        class="collect-btn"
        type="button"
        :disabled="collecting"
        @click="triggerCollect"
      >
        <svg
          v-if="!collecting"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 12a9 9 0 1 1-9-9" />
          <polyline points="21 4 21 10 15 10" />
        </svg>
        <svg
          v-else
          class="spin"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 12a9 9 0 1 1-6-8.5" />
        </svg>
        <span>{{ collecting ? 'COLLECTING' : 'COLLECT ALL' }}</span>
      </button>
    </header>

    <!-- 검색 & 필터 -->
    <div class="control-bar">
      <div class="search-wrap">
        <svg
          class="search-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="11" cy="11" r="7" />
          <line x1="20" y1="20" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="search"
          class="search-input"
          type="text"
          placeholder="종목명 또는 티커 검색"
          @input="onSearch"
        />
      </div>
      <div class="market-tabs" role="tablist">
        <button
          v-for="m in markets"
          :key="m"
          class="tab-btn"
          type="button"
          :class="{ active: marketFilter === m }"
          role="tab"
          :aria-selected="marketFilter === m"
          @click="setMarket(m)"
        >
          {{ m }}
        </button>
      </div>
    </div>

    <!-- 알림 메시지 -->
    <div v-if="message" class="message" :class="messageType">
      <span class="msg-tag">{{ messageType === 'error' ? 'ERR' : 'INFO' }}</span>
      <span>{{ message }}</span>
    </div>

    <!-- 데이터 없음 -->
    <div v-if="!loading && total === 0 && !search" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M3 5v14a9 3 0 0 0 18 0V5" />
          <path d="M3 12a9 3 0 0 0 18 0" />
        </svg>
      </div>
      <p class="empty-title">수집된 종목 데이터가 없습니다</p>
      <p class="empty-desc">
        상단의 <strong>COLLECT ALL</strong> 버튼으로 종목 데이터를 수집하세요.
      </p>
      <p class="empty-note">초회 수집은 수천 종목을 처리하므로 시간이 걸립니다.</p>
    </div>

    <!-- 종목 테이블 -->
    <div v-else class="table-wrap">
      <table class="stock-table">
        <thead>
          <tr>
            <th class="th-ticker">티커</th>
            <th>종목명</th>
            <th>시장</th>
            <th>섹터</th>
            <th class="th-action"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="loading">LOADING...</td>
          </tr>
          <tr v-for="stock in stocks" v-else :key="stock.ticker" class="stock-row">
            <td class="ticker">{{ stock.ticker }}</td>
            <td class="company">{{ stock.company_name }}</td>
            <td>
              <span class="badge" :class="stock.market_type.toLowerCase()">
                {{ stock.market_type }}
              </span>
            </td>
            <td class="sector">{{ stock.sector ?? '-' }}</td>
            <td class="td-action">
              <RouterLink :to="`/market/${stock.ticker}`" class="detail-link">
                차트
                <span aria-hidden="true">→</span>
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 페이지네이션 -->
    <div v-if="total > limit" class="pagination">
      <button
        class="page-btn"
        type="button"
        :disabled="page === 1"
        @click="changePage(page - 1)"
      >
        <span aria-hidden="true">←</span>
        <span>이전</span>
      </button>
      <span class="page-indicator">
        <span class="page-num">{{ page }}</span>
        <span class="page-sep">/</span>
        <span class="page-total">{{ totalPages }}</span>
      </span>
      <button
        class="page-btn"
        type="button"
        :disabled="page >= totalPages"
        @click="changePage(page + 1)"
      >
        <span>다음</span>
        <span aria-hidden="true">→</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/index'

const markets = ['전체', 'KOSPI', 'KOSDAQ']

const stocks = ref([])
const total = ref(0)
const page = ref(1)
const limit = 50
const search = ref('')
const marketFilter = ref('전체')
const loading = ref(false)
const collecting = ref(false)
const message = ref('')
const messageType = ref('info')

let searchTimer = null

const totalPages = computed(() => Math.ceil(total.value / limit))

async function fetchStocks() {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: page.value, limit })
    if (search.value) params.append('search', search.value)
    if (marketFilter.value !== '전체') params.append('market', marketFilter.value)
    const data = await api.get(`/market/stocks?${params}`)
    stocks.value = data.items
    total.value = data.total
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchStocks()
  }, 300)
}

function setMarket(m) {
  marketFilter.value = m
  page.value = 1
  fetchStocks()
}

function changePage(p) {
  page.value = p
  fetchStocks()
}

async function triggerCollect() {
  collecting.value = true
  try {
    const data = await api.post('/market/collect')
    showMessage(`수집 요청 완료 (task_id: ${data.task_id}). 백그라운드에서 진행 중입니다.`, 'info')
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    collecting.value = false
  }
}

function showMessage(msg, type = 'info') {
  message.value = msg
  messageType.value = type
  setTimeout(() => { message.value = '' }, 5000)
}

onMounted(fetchStocks)
</script>

<style scoped>
.market {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ==========================================================================
   Page header
   ========================================================================== */

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-faint);
}

.page-head-left {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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

.collect-btn {
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

.collect-btn svg {
  width: 14px;
  height: 14px;
}

.collect-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.collect-btn:active:not(:disabled) {
  transform: translateY(0);
}

.collect-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
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
   Control bar (search + market tabs)
   ========================================================================== */

.control-bar {
  display: flex;
  gap: var(--space-4);
  align-items: center;
}

.search-wrap {
  position: relative;
  flex: 1;
}

.search-icon {
  position: absolute;
  left: var(--space-3);
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 10px var(--space-3) 10px 40px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-md);
  outline: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.search-input:hover {
  border-color: var(--border-strong);
}

.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.search-input::placeholder {
  color: var(--text-faint);
}

.market-tabs {
  display: inline-flex;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}

.tab-btn {
  padding: 7px var(--space-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  background: var(--accent-bg);
  color: var(--accent);
}

/* ==========================================================================
   Message banner
   ========================================================================== */

.message {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  border: 1px solid;
}

.message.info {
  background: rgba(96, 165, 250, 0.08);
  border-color: rgba(96, 165, 250, 0.25);
  color: var(--loss-soft);
}

.message.error {
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
   Empty state
   ========================================================================== */

.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-5);
  background: var(--surface-1);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.empty-icon {
  color: var(--text-faint);
  margin-bottom: var(--space-3);
}

.empty-icon svg {
  width: 44px;
  height: 44px;
}

.empty-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.empty-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.empty-desc strong {
  font-family: var(--font-mono);
  color: var(--accent);
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

.empty-note {
  font-size: var(--text-xs);
  color: var(--text-faint);
  margin-top: var(--space-2);
}

/* ==========================================================================
   Stock table
   ========================================================================== */

.table-wrap {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.stock-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.stock-table thead th {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
  color: var(--text-muted);
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-faint);
}

.th-ticker {
  width: 110px;
}

.th-action {
  width: 100px;
  text-align: right;
}

.stock-row td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  transition: background var(--dur-fast) var(--ease-out);
}

.stock-row:last-child td {
  border-bottom: none;
}

.stock-row:hover td {
  background: var(--surface-2);
}

.ticker {
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  letter-spacing: var(--tracking-wide);
}

.company {
  font-weight: 500;
  color: var(--text-primary);
}

.sector {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.badge {
  font-family: var(--font-mono);
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

.badge.kospi {
  background: var(--accent-bg);
  color: var(--accent);
}

.badge.kosdaq {
  background: var(--up-bg);
  color: var(--up-strong);
}

.detail-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  text-decoration: none;
  transition: color var(--dur-fast) var(--ease-out);
}

.detail-link:hover {
  color: var(--accent-hover);
  text-decoration: underline;
}

.td-action {
  text-align: right;
}

.loading {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  letter-spacing: var(--tracking-wider);
}

/* ==========================================================================
   Pagination
   ========================================================================== */

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-2);
}

.page-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  font-family: inherit;
  font-size: var(--text-sm);
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.page-btn:hover:not(:disabled) {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-indicator {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-variant-numeric: tabular-nums;
}

.page-num {
  color: var(--text-primary);
  font-weight: 700;
}

.page-sep {
  color: var(--text-faint);
}

.page-total {
  color: var(--text-muted);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-3);
  }
  .control-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .market-tabs {
    justify-content: stretch;
  }
  .market-tabs .tab-btn {
    flex: 1;
  }
}
</style>
