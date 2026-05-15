<template>
  <div class="app-layout">
    <!-- 헤더 -->
    <header class="header">
      <div class="header-left">
        <span class="logo">AutoStock</span>
      </div>
      <div class="header-right">
        <div class="suggestions-bell" v-if="auth.token">
          <button class="bell-btn" @click="toggleDropdown" :class="{ 'has-pending': pendingSummary.total > 0 }">
            🔔
            <span v-if="pendingSummary.total > 0" class="bell-badge">{{ pendingSummary.total }}</span>
          </button>
          <div v-if="showDropdown" class="bell-dropdown">
            <div class="dd-title">튜닝 제안 {{ pendingSummary.total }}건</div>
            <div v-if="pendingSummary.by_bot.length === 0" class="dd-empty">대기 중인 제안이 없습니다</div>
            <div v-else>
              <div
                v-for="b in pendingSummary.by_bot"
                :key="b.bot_id"
                class="dd-row"
                @click="goBot(b.bot_id)"
              >
                <span class="dd-bot-name">{{ b.bot_name }}</span>
                <span class="dd-count">{{ b.count }}</span>
              </div>
            </div>
          </div>
        </div>
        <span class="username">{{ auth.user?.username }}</span>
        <button class="logout-btn" @click="logout">로그아웃</button>
      </div>
    </header>

    <div class="body">
      <!-- 사이드바 -->
      <nav class="sidebar">
        <RouterLink to="/dashboard" class="nav-item" active-class="active">
          <span class="nav-icon">⬛</span>
          <span>대시보드</span>
        </RouterLink>
        <RouterLink to="/market" class="nav-item" active-class="active">
          <span class="nav-icon">📈</span>
          <span>주식 데이터</span>
        </RouterLink>
        <RouterLink to="/canvas" class="nav-item nav-canvas" active-class="active">
          <span class="nav-icon">✦</span>
          <span>AI 캔버스</span>
        </RouterLink>
        <RouterLink to="/bots" class="nav-item" active-class="active">
          <span class="nav-icon">🤖</span>
          <span>자동매매</span>
        </RouterLink>
        <RouterLink to="/strategies" class="nav-item" active-class="active">
          <span class="nav-icon">⚡</span>
          <span>전략 관리</span>
        </RouterLink>
        <RouterLink to="/ai" class="nav-item" active-class="active">
          <span class="nav-icon">🧠</span>
          <span>AI 분석</span>
        </RouterLink>
        <RouterLink to="/connection" class="nav-item" active-class="active">
          <span class="nav-icon">🔌</span>
          <span>연결 설정</span>
        </RouterLink>
      </nav>

      <!-- 메인 콘텐츠 -->
      <main class="content" :class="{ 'content-canvas': isCanvas }">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route  = useRoute()
const auth   = useAuthStore()
const isCanvas = computed(() => route.name === 'canvas')

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'
const pendingSummary = ref({ total: 0, by_bot: [] })
const showDropdown = ref(false)
let pollTimer = null

async function fetchPendingSummary() {
  if (!auth.token) return
  try {
    const res = await fetch(`${API}/trading/bots/suggestions/pending-summary`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (res.ok) pendingSummary.value = await res.json()
  } catch { /* 헤더 배지 실패는 무시 */ }
}

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
  if (showDropdown.value) fetchPendingSummary()
}

function goBot(botId) {
  showDropdown.value = false
  router.push(`/bots/${botId}`)
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  fetchPendingSummary()
  pollTimer = setInterval(fetchPendingSummary, 30000)  // 30s 폴링
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #0f1117;
  color: #e5e7eb;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 56px;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3e;
  flex-shrink: 0;
}

.logo {
  color: #4f9eff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.username {
  color: #6b7280;
  font-size: 13px;
}

.logout-btn {
  padding: 5px 12px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.logout-btn:hover {
  border-color: #4f9eff;
  color: #4f9eff;
}

.body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.sidebar {
  width: 200px;
  background: #1a1d27;
  border-right: 1px solid #2a2d3e;
  padding: 16px 0;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: #6b7280;
  text-decoration: none;
  font-size: 14px;
  border-radius: 0;
  transition: all 0.15s;
}

.nav-item:hover {
  background: #2a2d3e;
  color: #e5e7eb;
}

.nav-item.active {
  background: #1e3a5f;
  color: #4f9eff;
}

.nav-icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.nav-canvas { color: #a78bfa !important; }
.nav-canvas.active { background: rgba(124,58,237,.15) !important; color: #a78bfa !important; }

.content {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}

.content-canvas {
  padding: 0;
  overflow: hidden;
}

/* 알림함 배지 */
.suggestions-bell {
  position: relative;
}

.bell-btn {
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  padding: 5px 10px;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;
  position: relative;
}

.bell-btn:hover { border-color: #4f9eff; color: #4f9eff; }

.bell-btn.has-pending { color: #fcd34d; border-color: rgba(252, 211, 77, 0.4); }

.bell-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ef4444;
  color: white;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

.bell-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  min-width: 240px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  z-index: 100;
  overflow: hidden;
}

.dd-title {
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #e5e7eb;
  border-bottom: 1px solid #2a2d3e;
}

.dd-empty {
  padding: 16px 12px;
  color: #6b7280;
  font-size: 13px;
  text-align: center;
}

.dd-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #d1d5db;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.dd-row:hover { background: #2a2d3e; }
.dd-row:last-child { border-bottom: none; }

.dd-bot-name { color: #e5e7eb; }

.dd-count {
  background: rgba(252, 211, 77, 0.15);
  color: #fcd34d;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
</style>
