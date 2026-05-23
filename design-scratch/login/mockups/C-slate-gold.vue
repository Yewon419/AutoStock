<!--
  Candidate C — Slate Gold (자산관리 프리미엄)
  로직 없는 시각 시안. 보존본.
  실사용은 frontend/src/views/LoginView.vue.
-->
<template>
  <div class="auth-wrap">
    <svg class="backdrop" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="lineGold" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#F59E0B" stop-opacity="0" />
          <stop offset="50%" stop-color="#F59E0B" stop-opacity="0.55" />
          <stop offset="100%" stop-color="#F59E0B" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="lineSlate" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#64748B" stop-opacity="0" />
          <stop offset="50%" stop-color="#64748B" stop-opacity="0.45" />
          <stop offset="100%" stop-color="#64748B" stop-opacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points="0,520 120,500 240,540 360,460 480,490 600,420 720,450 840,380 960,410 1080,340 1200,360 1320,300 1440,330"
        stroke="url(#lineGold)"
        stroke-width="2"
        fill="none"
      />
      <polyline
        points="0,640 120,620 240,660 360,600 480,640 600,580 720,610 840,550 960,580 1080,510 1200,540 1320,470 1440,500"
        stroke="url(#lineSlate)"
        stroke-width="1.5"
        fill="none"
      />
      <polyline
        points="0,720 120,740 240,690 360,720 480,670 600,700 720,650 840,690 960,640 1080,680 1200,620 1320,660 1440,600"
        stroke="url(#lineSlate)"
        stroke-width="1.5"
        fill="none"
      />
    </svg>

    <div class="glow glow-gold"></div>
    <div class="glow glow-slate"></div>

    <div class="auth-card">
      <div class="brand">
        <span class="brand-dot"></span>
        <h1 class="logo">AutoStock</h1>
      </div>
      <p class="tagline">AI 기반 자동매매 플랫폼</p>

      <form @submit.prevent class="form">
        <div class="field">
          <label for="username">아이디</label>
          <input id="username" type="text" placeholder="아이디" />
        </div>

        <div class="field">
          <label for="password">비밀번호</label>
          <input id="password" type="password" placeholder="비밀번호" />
        </div>

        <button class="submit-btn" type="submit">로그인</button>
      </form>

      <div class="footer">
        <span class="footer-text">처음이신가요?</span>
        <button type="button" class="link">회원가입</button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 시각 시안용. 상태·로직 없음.
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Asta+Sans:wght@300;400;500;600;700&display=swap');

.auth-wrap {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0a1020 0%, #0f172a 50%, #111827 100%);
  overflow: hidden;
  font-family: 'Asta Sans', 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}

.backdrop {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.5;
  pointer-events: none;
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
}

.glow-gold {
  width: 480px;
  height: 480px;
  background: rgba(245, 158, 11, 0.14);
  top: -120px;
  right: -120px;
}

.glow-slate {
  width: 520px;
  height: 520px;
  background: rgba(94, 106, 210, 0.08);
  bottom: -160px;
  left: -160px;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  margin: 0 24px;
  padding: 40px 36px 32px;
  background: rgba(34, 39, 53, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 24px 48px -12px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(0, 0, 0, 0.2);
}

.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 12px rgba(245, 158, 11, 0.6);
}

.logo {
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.02em;
  margin: 0;
}

.tagline {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  margin: 8px 0 32px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
  letter-spacing: 0.01em;
}

.field input {
  width: 100%;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: #f8fafc;
  font-size: 14px;
  font-family: inherit;
  box-sizing: border-box;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.field input::placeholder {
  color: #475569;
}

.field input:hover {
  border-color: rgba(255, 255, 255, 0.14);
}

.field input:focus {
  border-color: #f59e0b;
  background: rgba(15, 23, 42, 0.7);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.submit-btn {
  margin-top: 8px;
  width: 100%;
  padding: 13px;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: #0f172a;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  letter-spacing: -0.01em;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
  box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25);
}

.submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.35);
  filter: brightness(1.05);
}

.submit-btn:active {
  transform: translateY(0);
}

.footer {
  text-align: center;
  margin-top: 24px;
  font-size: 13px;
  color: #94a3b8;
}

.footer-text {
  margin-right: 6px;
}

.link {
  background: none;
  border: none;
  color: #f59e0b;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  padding: 0;
  transition: color 0.2s ease;
}

.link:hover {
  color: #fbbf24;
  text-decoration: underline;
}
</style>
