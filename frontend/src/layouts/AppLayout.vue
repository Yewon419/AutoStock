<template>
  <div class="app-layout">
    <header class="topbar">
      <div class="topbar-left">
        <span class="brand">
          <span class="brand-mark">AS</span>
          <span class="brand-name">AUTOSTOCK</span>
        </span>
        <span class="topbar-sep">/</span>
        <span class="topbar-status">
          <span class="status-dot"></span>
          <span class="status-label">SYSTEM ONLINE</span>
        </span>
      </div>

      <div class="topbar-right">
        <div v-if="auth.token" class="bell-wrap">
          <button
            class="icon-btn bell-btn"
            :class="{ 'has-pending': unseenCount > 0 }"
            type="button"
            aria-label="알림"
            @click="toggleDropdown"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
              <path d="M10.5 21a1.5 1.5 0 0 0 3 0" />
            </svg>
            <span v-if="unseenCount > 0" class="bell-badge">{{ unseenCount }}</span>
          </button>
          <div v-if="showDropdown" class="bell-dropdown" role="menu">
            <div class="dd-head">
              <span class="dd-title">PENDING</span>
              <span class="dd-count-total">{{ pendingSummary.total }}</span>
            </div>
            <div v-if="pendingSummary.by_bot.length === 0" class="dd-empty">
              대기 중인 제안 없음
            </div>
            <div v-else class="dd-list">
              <button
                v-for="b in pendingSummary.by_bot"
                :key="b.bot_id"
                class="dd-row"
                type="button"
                @click="goBot(b.bot_id)"
              >
                <span class="dd-bot-name">{{ b.bot_name }}</span>
                <span class="dd-count" :class="{ unseen: isUnseen(b) }">{{ b.count }}</span>
              </button>
            </div>
          </div>
        </div>
        <span v-if="auth.user?.username" class="username">{{ auth.user.username }}</span>
        <button class="logout-btn" type="button" @click="logout">
          <span>LOGOUT</span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
        </button>
      </div>
    </header>

    <div class="body">
      <nav class="sidebar">
        <RouterLink to="/dashboard" class="nav-item" active-class="active">
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="3" width="7" height="9" rx="1" />
            <rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="12" width="7" height="9" rx="1" />
            <rect x="3" y="16" width="7" height="5" rx="1" />
          </svg>
          <span>대시보드</span>
        </RouterLink>

        <RouterLink to="/market" class="nav-item" active-class="active">
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polyline points="3 17 9 11 13 15 21 7" />
            <polyline points="14 7 21 7 21 14" />
          </svg>
          <span>주식 데이터</span>
        </RouterLink>

        <RouterLink to="/bots" class="nav-item" active-class="active">
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <rect x="4" y="6" width="16" height="14" rx="2" />
            <path d="M12 6V3" />
            <path d="M10 3h4" />
            <circle cx="9" cy="13" r="1" />
            <circle cx="15" cy="13" r="1" />
            <path d="M9 17h6" />
          </svg>
          <span>자동매매</span>
        </RouterLink>

        <RouterLink to="/ai" class="nav-item" active-class="active">
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path
              d="m12 4-1.6 4.4L6 10l4.4 1.6L12 16l1.6-4.4L18 10l-4.4-1.6z"
            />
            <path d="M19 3v3" />
            <path d="M17.5 4.5h3" />
            <path d="M5 18v2" />
            <path d="M4 19h2" />
          </svg>
          <span>AI 분석</span>
        </RouterLink>

        <RouterLink to="/connection" class="nav-item" active-class="active">
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M9 7V2" />
            <path d="M15 7V2" />
            <path d="M7 7h10v4a5 5 0 0 1-10 0z" />
            <path d="M12 16v6" />
          </svg>
          <span>연결 설정</span>
        </RouterLink>

        <div class="sidebar-foot">
          <span class="sidebar-meta">v0.7 · PHASE 7</span>
        </div>
      </nav>

      <main class="content" :class="{ 'content-canvas': isCanvas }">
        <RouterView :key="route.path" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const isCanvas = computed(() => route.name === 'canvas')

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'
const LAST_SEEN_KEY = 'as:lastSeenSuggestionByBot' // { [botId]: lastSeenId }
const pendingSummary = ref({ total: 0, by_bot: [] })
const lastSeenMap = ref(loadLastSeen())
const showDropdown = ref(false)
let pollTimer = null

function loadLastSeen() {
  try {
    const raw = localStorage.getItem(LAST_SEEN_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function isUnseen(b) {
  return (b.max_id || 0) > (lastSeenMap.value[b.bot_id] || 0)
}

// 미확인 봇의 카운트만 합산. 행을 클릭해 그 봇 페이지로 이동하면 그 봇의 카운트만 사라짐.
const unseenCount = computed(() =>
  pendingSummary.value.by_bot.reduce((sum, b) => sum + (isUnseen(b) ? b.count : 0), 0),
)

async function fetchPendingSummary() {
  if (!auth.token) return
  try {
    const res = await fetch(`${API}/trading/bots/suggestions/pending-summary`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (res.ok) pendingSummary.value = await res.json()
  } catch {
    /* 헤더 배지 실패는 무시 */
  }
}

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
  if (showDropdown.value) fetchPendingSummary() // 열 때 fresh, 단 last-seen은 갱신하지 않음
}

function goBot(botId) {
  // 이 봇 행을 클릭해 페이지로 이동 → 이 봇의 max_id를 마지막 본 id로 저장
  const bot = pendingSummary.value.by_bot.find((b) => b.bot_id === botId)
  if (bot) {
    const newMap = { ...lastSeenMap.value, [botId]: bot.max_id || 0 }
    lastSeenMap.value = newMap
    localStorage.setItem(LAST_SEEN_KEY, JSON.stringify(newMap))
  }
  showDropdown.value = false
  router.push(`/bots/${botId}`)
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  fetchPendingSummary()
  pollTimer = setInterval(fetchPendingSummary, 30000) // 30s 폴링
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  background: var(--bg-base);
  color: var(--text-primary);
  overflow: hidden;
}

/* ==========================================================================
   Topbar
   ========================================================================== */

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-7);
  height: var(--header-h);
  background: linear-gradient(180deg, rgba(10, 12, 18, 0.85), rgba(10, 12, 18, 0.6));
  backdrop-filter: var(--blur-sm);
  -webkit-backdrop-filter: var(--blur-sm);
  border-bottom: 1px solid var(--border-faint);
  flex-shrink: 0;
  position: relative;
  z-index: var(--z-hud);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.topbar-right {
  gap: var(--space-4);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.brand-mark {
  font-weight: 700;
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  background: var(--accent-bg);
  color: var(--accent);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--accent-border);
}

.brand-name {
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: var(--tracking-wider);
}

.topbar-sep {
  color: var(--text-faint);
}

.topbar-status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-secondary);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--success);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
  animation: statusPulse 2s ease-in-out infinite;
}

@keyframes statusPulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.9);
  }
}

/* ==========================================================================
   Top-right controls (bell / user / logout)
   ========================================================================== */

.icon-btn {
  position: relative;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.icon-btn svg {
  width: 16px;
  height: 16px;
}

.icon-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.bell-btn.has-pending {
  color: var(--accent);
  border-color: var(--accent-border);
}

.bell-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: var(--danger);
  color: #fff;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  border: 1px solid var(--bg-base);
  font-family: var(--font-mono);
  letter-spacing: 0;
}

.username {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
  padding: 0 var(--space-1);
}

.logout-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 12px;
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

.logout-btn svg {
  width: 13px;
  height: 13px;
}

.logout-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

/* ==========================================================================
   Bell dropdown
   ========================================================================== */

.bell-wrap {
  position: relative;
}

.bell-dropdown {
  position: absolute;
  top: calc(100% + var(--space-2));
  right: 0;
  min-width: 280px;
  background: var(--glass-bg-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  backdrop-filter: var(--blur-md);
  -webkit-backdrop-filter: var(--blur-md);
  z-index: var(--z-dropdown);
  overflow: hidden;
}

.dd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.dd-title {
  color: var(--text-muted);
  font-weight: 600;
}

.dd-count-total {
  color: var(--accent);
  font-weight: 700;
}

.dd-empty {
  padding: var(--space-5) var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
  text-align: center;
}

.dd-list {
  max-height: 320px;
  overflow-y: auto;
}

.dd-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border-faint);
  color: var(--text-secondary);
  font-family: inherit;
  font-size: var(--text-sm);
  text-align: left;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.dd-row:hover {
  background: var(--surface-1);
}

.dd-row:last-child {
  border-bottom: none;
}

.dd-bot-name {
  color: var(--text-primary);
  font-weight: 500;
}

.dd-count {
  background: var(--surface-2);
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
  min-width: 20px;
  text-align: center;
}

.dd-count.unseen {
  background: var(--accent-bg);
  color: var(--accent);
}

/* ==========================================================================
   Body / Sidebar / Content
   ========================================================================== */

.body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.sidebar {
  width: var(--sidebar-w);
  background: var(--bg-elevated);
  border-right: 1px solid var(--border-faint);
  padding: var(--space-3) 0 0;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: 0 var(--space-3);
  padding: 10px var(--space-3);
  color: var(--text-muted);
  text-decoration: none;
  font-size: var(--text-md);
  font-weight: 500;
  border-radius: var(--radius-md);
  transition:
    color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.nav-item::before {
  content: '';
  position: absolute;
  left: -3px;
  top: 50%;
  width: 2px;
  height: 0;
  background: var(--accent);
  border-radius: var(--radius-full);
  transform: translateY(-50%);
  transition: height var(--dur-base) var(--ease-out);
}

.nav-item:hover {
  background: var(--surface-1);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent-bg);
  color: var(--accent);
}

.nav-item.active::before {
  height: 60%;
}

.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  stroke-width: 1.75;
}

.sidebar-foot {
  margin-top: auto;
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-faint);
}

.sidebar-meta {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
  background: var(--bg-base);
}

.content-canvas {
  padding: 0;
  overflow: hidden;
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 900px) {
  .topbar-status {
    display: none;
  }
  .sidebar {
    width: 64px;
  }
  .nav-item span {
    display: none;
  }
  .nav-item {
    justify-content: center;
    margin: 0 var(--space-2);
    padding: 12px;
  }
  .sidebar-foot {
    display: none;
  }
}

@media (max-width: 640px) {
  .topbar {
    padding: 0 var(--space-4);
  }
  .brand-name {
    display: none;
  }
  .username {
    display: none;
  }
  .content {
    padding: var(--space-5);
  }
}
</style>
