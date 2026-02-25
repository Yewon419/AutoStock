<template>
  <div class="market">
    <div class="page-header">
      <h2 class="page-title">주식 데이터</h2>
      <button class="collect-btn" :disabled="collecting" @click="triggerCollect">
        {{ collecting ? '수집 중...' : '전체 수집' }}
      </button>
    </div>

    <!-- 검색 & 필터 -->
    <div class="search-bar">
      <input
        v-model="search"
        class="search-input"
        type="text"
        placeholder="종목명 또는 티커 검색"
        @input="onSearch"
      />
      <div class="market-tabs">
        <button
          v-for="m in ['전체', 'KOSPI', 'KOSDAQ']"
          :key="m"
          class="tab-btn"
          :class="{ active: marketFilter === m }"
          @click="setMarket(m)"
        >
          {{ m }}
        </button>
      </div>
    </div>

    <!-- 알림 메시지 -->
    <div v-if="message" class="message" :class="messageType">{{ message }}</div>

    <!-- 데이터 없음 안내 -->
    <div v-if="!loading && total === 0 && !search" class="empty-state">
      <p>아직 수집된 종목 데이터가 없습니다.</p>
      <p>우측 상단 <strong>전체 수집</strong> 버튼을 클릭해 데이터를 수집하세요.</p>
      <p class="empty-note">초회 수집은 수천 개 종목을 처리하므로 시간이 걸립니다.</p>
    </div>

    <!-- 종목 테이블 -->
    <div v-else class="table-wrap">
      <table class="stock-table">
        <thead>
          <tr>
            <th>티커</th>
            <th>종목명</th>
            <th>시장</th>
            <th>섹터</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="loading">로딩 중...</td>
          </tr>
          <tr v-for="stock in stocks" :key="stock.ticker" class="stock-row">
            <td class="ticker">{{ stock.ticker }}</td>
            <td class="company">{{ stock.company_name }}</td>
            <td>
              <span class="badge" :class="stock.market_type.toLowerCase()">
                {{ stock.market_type }}
              </span>
            </td>
            <td class="sector">{{ stock.sector ?? '-' }}</td>
            <td>
              <RouterLink :to="`/market/${stock.ticker}`" class="detail-link">
                차트 보기
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 페이지네이션 -->
    <div v-if="total > limit" class="pagination">
      <button :disabled="page === 1" @click="changePage(page - 1)">이전</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="changePage(page + 1)">다음</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api/index'

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
  max-width: 1000px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
}

.collect-btn {
  padding: 8px 18px;
  background: #1e3a5f;
  border: 1px solid #4f9eff;
  border-radius: 8px;
  color: #4f9eff;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.collect-btn:hover:not(:disabled) {
  background: #4f9eff;
  color: #fff;
}

.collect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
}

.search-input {
  flex: 1;
  padding: 10px 14px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}

.search-input:focus {
  border-color: #4f9eff;
}

.search-input::placeholder {
  color: #4b5563;
}

.market-tabs {
  display: flex;
  gap: 4px;
}

.tab-btn {
  padding: 8px 14px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn:hover {
  border-color: #4f9eff;
  color: #4f9eff;
}

.tab-btn.active {
  background: #1e3a5f;
  border-color: #4f9eff;
  color: #4f9eff;
}

.message {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}

.message.info {
  background: #1e3a5f;
  border: 1px solid #4f9eff;
  color: #93c5fd;
}

.message.error {
  background: #3b1a1a;
  border: 1px solid #ef4444;
  color: #fca5a5;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #6b7280;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  line-height: 2;
}

.empty-note {
  margin-top: 8px;
  font-size: 12px;
  color: #4b5563;
}

.table-wrap {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  overflow: hidden;
}

.stock-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.stock-table thead th {
  padding: 12px 16px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  border-bottom: 1px solid #2a2d3e;
}

.stock-row td {
  padding: 12px 16px;
  border-bottom: 1px solid #1e2130;
  transition: background 0.1s;
}

.stock-row:last-child td {
  border-bottom: none;
}

.stock-row:hover td {
  background: #1e2130;
}

.ticker {
  font-family: monospace;
  color: #9ca3af;
  font-size: 13px;
}

.company {
  font-weight: 500;
}

.sector {
  color: #6b7280;
  font-size: 13px;
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.badge.kospi {
  background: #1e3a5f;
  color: #4f9eff;
}

.badge.kosdaq {
  background: #1e3b2a;
  color: #4ade80;
}

.detail-link {
  color: #4f9eff;
  text-decoration: none;
  font-size: 13px;
}

.detail-link:hover {
  text-decoration: underline;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
  color: #6b7280;
  font-size: 14px;
}

.pagination button {
  padding: 6px 14px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.15s;
}

.pagination button:hover:not(:disabled) {
  border-color: #4f9eff;
  color: #4f9eff;
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
