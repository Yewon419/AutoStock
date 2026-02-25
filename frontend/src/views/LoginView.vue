<template>
  <div class="auth-wrap">
    <div class="auth-box">
      <h1 class="logo">AutoStock</h1>
      <p class="tagline">자동매매 플랫폼</p>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">로그인</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">회원가입</button>
      </div>

      <form @submit.prevent="submit">
        <div class="field">
          <label>아이디</label>
          <input v-model="form.username" type="text" placeholder="아이디를 입력하세요" required />
        </div>

        <div class="field" v-if="mode === 'register'">
          <label>이메일</label>
          <input v-model="form.email" type="email" placeholder="이메일을 입력하세요" required />
        </div>

        <div class="field">
          <label>비밀번호</label>
          <input v-model="form.password" type="password" placeholder="비밀번호를 입력하세요" required />
        </div>

        <p class="error" v-if="error">{{ error }}</p>
        <p class="success" v-if="success">{{ success }}</p>

        <button class="submit-btn" type="submit" :disabled="loading">
          {{ loading ? '처리 중...' : mode === 'login' ? '로그인' : '회원가입' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref('login')
const loading = ref(false)
const error = ref('')
const success = ref('')

const form = reactive({ username: '', email: '', password: '' })

async function submit() {
  error.value = ''
  success.value = ''
  loading.value = true

  try {
    if (mode.value === 'login') {
      await auth.login(form.username, form.password)
      router.push('/dashboard')
    } else {
      await auth.register(form.username, form.email, form.password)
      success.value = '회원가입 완료! 로그인해주세요.'
      mode.value = 'login'
      form.password = ''
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f1117;
}

.auth-box {
  width: 100%;
  max-width: 420px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  padding: 40px;
}

.logo {
  font-size: 28px;
  font-weight: 700;
  color: #4f9eff;
  text-align: center;
  margin: 0;
}

.tagline {
  text-align: center;
  color: #6b7280;
  font-size: 13px;
  margin: 6px 0 28px;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #2a2d3e;
  margin-bottom: 24px;
}

.tabs button {
  flex: 1;
  padding: 10px;
  background: none;
  border: none;
  color: #6b7280;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}

.tabs button.active {
  color: #4f9eff;
  border-bottom-color: #4f9eff;
}

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  padding: 10px 12px;
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.2s;
}

.field input:focus {
  border-color: #4f9eff;
}

.error {
  color: #f87171;
  font-size: 13px;
  margin-bottom: 12px;
}

.success {
  color: #34d399;
  font-size: 13px;
  margin-bottom: 12px;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background: #4f9eff;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.submit-btn:hover:not(:disabled) {
  background: #3b8af0;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
