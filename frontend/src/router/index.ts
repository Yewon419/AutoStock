import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard',
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'market',
          name: 'market',
          component: () => import('@/views/MarketView.vue'),
        },
        {
          path: 'market/:ticker',
          name: 'stock-detail',
          component: () => import('@/views/StockDetailView.vue'),
        },
        {
          path: 'bots',
          name: 'bots',
          component: () => import('@/views/BotView.vue'),
        },
        {
          path: 'bots/:id',
          name: 'bot-detail',
          component: () => import('@/views/BotDetailView.vue'),
        },
        {
          path: 'connection',
          name: 'connection',
          component: () => import('@/views/ConnectionView.vue'),
        },
        {
          path: 'ai',
          name: 'ai',
          component: () => import('@/views/AiView.vue'),
        },
        // 전역 /strategies, /canvas 라우트 폐기 (봇 1:1 모델 — 봇 페이지 캔버스 탭으로 통합)
        // CanvasView·StrategyView 컴포넌트 자체는 BotCanvas가 임베드로 사용
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
})

export default router
