<template>
  <div class="app-layout">
    <!-- 헤더 -->
    <header class="header">
      <div class="header-left">
        <span class="logo">AutoStock</span>
      </div>
      <div class="header-right">
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
        <RouterLink to="/strategies" class="nav-item" active-class="active">
          <span class="nav-icon">⚡</span>
          <span>전략 관리</span>
        </RouterLink>
        <RouterLink to="/bots" class="nav-item" active-class="active">
          <span class="nav-icon">🤖</span>
          <span>자동매매</span>
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
      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}
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

.content {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}
</style>
