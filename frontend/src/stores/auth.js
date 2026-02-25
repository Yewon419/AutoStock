import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.access_token
    localStorage.setItem('token', res.access_token)
    await fetchMe()
  }

  async function register(username, email, password) {
    return await api.post('/auth/register', { username, email, password })
  }

  async function fetchMe() {
    try {
      user.value = await api.get('/auth/me')
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, isLoggedIn, login, register, fetchMe, logout }
})
