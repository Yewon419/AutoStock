import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// 401 응답 시 자동 로그아웃 + 로그인 페이지 이동 (중복 리다이렉트 방지)
let _loggingOut = false
const _fetch = window.fetch
window.fetch = async (...args) => {
  const res = await _fetch(...args)
  if (res.status === 401 && !_loggingOut) {
    const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url
    if (!url.includes('/auth/login')) {
      _loggingOut = true
      localStorage.removeItem('token')
      router.push('/login').finally(() => { _loggingOut = false })
    }
  }
  return res
}

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
