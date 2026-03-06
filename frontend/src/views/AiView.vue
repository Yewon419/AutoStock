<template>
  <div class="ai-view">
    <div class="page-header">
      <h1>AI 분석</h1>
      <p class="subtitle">ML 스코어링 · 파라미터 최적화 · LLM 전략 자동 생성</p>
    </div>

    <!-- 탭 -->
    <div class="tabs">
      <button class="tab-btn" :class="{ active: tab === 'score' }" @click="tab = 'score'">
        ML 종목 스코어링
      </button>
      <button class="tab-btn" :class="{ active: tab === 'optimize' }" @click="tab = 'optimize'">
        파라미터 최적화
      </button>
      <button class="tab-btn llm-tab" :class="{ active: tab === 'llm' }" @click="switchLlmTab">
        ✦ LLM 전략 생성기
      </button>
    </div>

    <!-- ============================================================ -->
    <!-- ML 종목 스코어링 탭                                           -->
    <!-- ============================================================ -->
    <div v-if="tab === 'score'" class="tab-content">
      <div class="panel">
        <div class="panel-header">
          <div class="header-info">
            <span class="panel-title">ML 종목 스코어링</span>
            <span v-if="scoreMeta" class="meta-info">
              기준일: {{ scoreMeta.date }} &nbsp;|&nbsp;
              학습 샘플: {{ scoreMeta.train_samples?.toLocaleString() }}개 &nbsp;|&nbsp;
              매수 신호 비율: {{ scoreMeta.positive_rate }}%
            </span>
          </div>
          <div class="header-actions">
            <button class="btn-secondary" @click="loadScores" :disabled="scoreLoading">새로고침</button>
            <button class="btn-primary" @click="runScoring" :disabled="scoreLoading">
              {{ scoreLoading ? '학습 중...' : '새로 학습 실행' }}
            </button>
          </div>
        </div>

        <div v-if="scoreLoading" class="loading-box">
          <div class="spinner"></div>
          <span>RandomForest 모델 학습 중... (수 분 소요될 수 있습니다)</span>
        </div>

        <div v-else-if="topScores.length === 0" class="empty-state">
          학습 결과가 없습니다. "새로 학습 실행" 버튼을 클릭하세요.
          <br /><small>매일 17:30에 자동 실행됩니다.</small>
        </div>

        <div v-else>
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:50px">순위</th>
                <th>티커</th>
                <th style="text-align:right">ML 점수</th>
                <th>스코어</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in topScores" :key="item.ticker">
                <td class="rank">{{ idx + 1 }}</td>
                <td class="ticker-cell">{{ item.ticker }}</td>
                <td class="score-val" :style="{ color: scoreColor(item.score) }">
                  {{ item.score.toFixed(1) }}
                </td>
                <td class="bar-cell">
                  <div class="score-bar-wrap">
                    <div
                      class="score-bar"
                      :style="{ width: item.score + '%', background: scoreColor(item.score) }"
                    ></div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 모델 설명 -->
      <div class="info-box">
        <strong>모델 정보</strong>
        <ul>
          <li>알고리즘: Random Forest Classifier (트리 100개, 최대 깊이 6)</li>
          <li>피처: RSI, MACD 히스토그램, Stoch K/D, ADX, MA 기울기 (20/50), ATR, 볼린저밴드 위치</li>
          <li>레이블: 5거래일 후 수익률 &gt; 1% → 매수 신호</li>
          <li>학습 기간: 최근 6개월 히스토리</li>
          <li>점수: 0~100 (높을수록 매수 신호 강도 높음)</li>
          <li>자동 실행: 매일 17:30 (데이터 수집 완료 후)</li>
        </ul>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 파라미터 최적화 탭                                             -->
    <!-- ============================================================ -->
    <div v-if="tab === 'optimize'" class="tab-content">
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">전략 파라미터 최적화</span>
        </div>

        <div class="opt-form">
          <div class="form-row">
            <label>전략 선택</label>
            <select v-model="optForm.strategy_id">
              <option value="">전략 선택...</option>
              <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>

          <div class="form-row">
            <label>지표</label>
            <select v-model="optForm.indicator">
              <option value="rsi">RSI</option>
              <option value="stoch_k">Stoch K</option>
              <option value="stoch_d">Stoch D</option>
              <option value="adx">ADX</option>
              <option value="macd_histogram">MACD Histogram</option>
            </select>
          </div>

          <div class="form-row">
            <label>조건</label>
            <select v-model="optForm.condition">
              <option value="below">below (이하)</option>
              <option value="above">above (이상)</option>
            </select>
          </div>

          <div class="form-row">
            <label>값 범위</label>
            <div class="range-inputs">
              <input type="number" v-model.number="optForm.value_min" placeholder="최소" />
              <span class="sep">~</span>
              <input type="number" v-model.number="optForm.value_max" placeholder="최대" />
              <span class="sep">간격</span>
              <input type="number" v-model.number="optForm.value_step" placeholder="스텝" min="0.1" style="width:80px" />
            </div>
          </div>

          <div class="form-row">
            <label>분석 기간</label>
            <div class="range-inputs">
              <input type="date" v-model="optForm.start_date" />
              <span class="sep">~</span>
              <input type="date" v-model="optForm.end_date" />
            </div>
          </div>

          <div class="form-hint">
            고거래량 상위 100개 종목을 대상으로 각 값별 1년 백테스트를 실행합니다. (최대 30단계)
          </div>

          <div class="form-actions">
            <button
              class="btn-primary"
              @click="runOptimize"
              :disabled="optLoading || !optForm.strategy_id"
            >
              {{ optLoading ? '최적화 실행 중...' : '최적화 실행' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 로딩 -->
      <div v-if="optLoading" class="panel">
        <div class="loading-box">
          <div class="spinner"></div>
          <span>Grid Search 백테스트 실행 중... (수 분 소요될 수 있습니다)</span>
        </div>
      </div>

      <!-- 결과 -->
      <div v-if="optResult" class="panel">
        <div class="panel-header">
          <span class="panel-title">최적화 결과</span>
          <span v-if="optResult.best" class="best-tag">
            최적값: <strong>{{ optResult.best.value }}</strong>
            &nbsp;(샤프 {{ optResult.best.sharpe.toFixed(2) }})
          </span>
        </div>

        <!-- SVG 라인 차트 -->
        <div class="chart-wrap" v-if="optResult.results?.length > 1">
          <svg :width="svgW" :height="svgH" class="opt-svg">
            <!-- 그리드 -->
            <line
              v-for="gl in gridLines"
              :key="gl.y"
              :x1="PAD" :y1="gl.y" :x2="svgW - PAD" :y2="gl.y"
              stroke="#2a2d3e" stroke-width="1"
            />
            <!-- y 라벨 -->
            <text
              v-for="gl in gridLines"
              :key="'yl' + gl.y"
              :x="PAD - 6" :y="gl.y + 4"
              fill="#6b7280" font-size="10" text-anchor="end"
            >{{ gl.label }}</text>
            <!-- 라인 -->
            <polyline
              :points="linePoints"
              fill="none" stroke="#4f9eff" stroke-width="2" stroke-linejoin="round"
            />
            <!-- 점 -->
            <circle
              v-for="(r, i) in optResult.results"
              :key="'dot' + i"
              :cx="dotX(i)" :cy="dotY(r.sharpe)"
              :r="r === optResult.best ? 6 : 3.5"
              :fill="r === optResult.best ? '#f59e0b' : '#4f9eff'"
              :stroke="r === optResult.best ? '#fff' : 'none'"
              stroke-width="1.5"
            />
            <!-- x 라벨 -->
            <text
              v-for="xl in xLabels"
              :key="'xl' + xl.x"
              :x="xl.x" :y="svgH - 4"
              fill="#6b7280" font-size="9" text-anchor="middle"
            >{{ xl.label }}</text>
            <!-- 축 타이틀 -->
            <text x="16" y="16" fill="#9ca3af" font-size="11">샤프 비율</text>
          </svg>
        </div>

        <!-- 결과 테이블 -->
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ optResult.indicator }} 값</th>
              <th style="text-align:right">샤프</th>
              <th style="text-align:right">총수익률</th>
              <th style="text-align:right">승률</th>
              <th style="text-align:right">거래수</th>
              <th style="text-align:right">점수</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in optResult.results"
              :key="r.value"
              :class="{ 'best-row': r === optResult.best }"
            >
              <td>{{ r.value }}</td>
              <td style="text-align:right" :class="numCls(r.sharpe)">{{ r.sharpe.toFixed(2) }}</td>
              <td style="text-align:right" :class="numCls(r.total_return)">{{ r.total_return.toFixed(1) }}%</td>
              <td style="text-align:right">{{ r.win_rate.toFixed(1) }}%</td>
              <td style="text-align:right">{{ r.num_trades }}</td>
              <td style="text-align:right">{{ r.score.toFixed(0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <!-- ============================================================ -->
    <!-- LLM 전략 생성기 탭                                            -->
    <!-- ============================================================ -->
    <div v-if="tab === 'llm'" class="tab-content">

      <!-- 시장 컨텍스트 미리보기 + 생성 버튼 -->
      <div class="panel">
        <div class="panel-header">
          <div class="header-info">
            <span class="panel-title">✦ LLM 전략 생성기</span>
            <span class="meta-info">시장 데이터를 분석하여 Claude AI가 최적 전략 조건을 자동 생성합니다</span>
          </div>
          <div class="header-actions">
            <button class="btn-secondary" @click="loadMarketContext" :disabled="ctxLoading">
              시장 현황 미리보기
            </button>
            <button class="btn-llm" @click="runGenerate" :disabled="llmLoading">
              {{ llmLoading ? 'AI 분석 중...' : '✦ 전략 생성' }}
            </button>
          </div>
        </div>

        <!-- 시장 컨텍스트 -->
        <div v-if="ctxLoading" class="loading-box">
          <div class="spinner"></div><span>시장 데이터 수집 중...</span>
        </div>
        <div v-else-if="marketCtx" class="ctx-grid">
          <!-- 국내 지수 -->
          <div class="ctx-card" v-if="Object.keys(marketCtx.krx_indices || {}).length">
            <div class="ctx-title">국내 지수</div>
            <div v-for="(v, k) in marketCtx.krx_indices" :key="k" class="ctx-row">
              <span class="ctx-label">{{ k }}</span>
              <span class="ctx-val" :class="v.change_pct >= 0 ? 'up' : 'down'">
                {{ v.close.toLocaleString() }}
                <span class="chg">({{ v.change_pct >= 0 ? '+' : '' }}{{ v.change_pct }}%)</span>
              </span>
            </div>
          </div>
          <!-- 글로벌 -->
          <div class="ctx-card" v-if="Object.keys(marketCtx.global_indices || {}).length">
            <div class="ctx-title">글로벌 시장</div>
            <div v-for="(v, k) in marketCtx.global_indices" :key="k" class="ctx-row">
              <span class="ctx-label">{{ k }}</span>
              <span class="ctx-val" :class="v.change_pct >= 0 ? 'up' : 'down'">
                {{ v.close.toLocaleString() }}
                <span class="chg">({{ v.change_pct >= 0 ? '+' : '' }}{{ v.change_pct }}%)</span>
              </span>
            </div>
          </div>
          <!-- 투자자 동향 -->
          <div class="ctx-card" v-if="Object.keys(marketCtx.investor_trend || {}).length">
            <div class="ctx-title">투자자 순매수 (KOSPI)</div>
            <div v-for="(v, k) in marketCtx.investor_trend" :key="k" class="ctx-row">
              <span class="ctx-label">{{ {foreign:'외국인', institution:'기관', retail:'개인'}[k] || k }}</span>
              <span class="ctx-val" :class="v >= 0 ? 'up' : 'down'">
                {{ (v >= 0 ? '+' : '') + Math.round(v / 1e8).toLocaleString() }}억원
              </span>
            </div>
          </div>
          <!-- 섹터 -->
          <div class="ctx-card" v-if="marketCtx.sector_trend?.top?.length">
            <div class="ctx-title">섹터 동향</div>
            <div class="ctx-sub">▲ 상승</div>
            <div v-for="[name, chg] in (marketCtx.sector_trend.top || [])" :key="name" class="ctx-row">
              <span class="ctx-label">{{ name }}</span>
              <span class="ctx-val up">+{{ chg }}%</span>
            </div>
            <div class="ctx-sub" style="margin-top:6px">▼ 하락</div>
            <div v-for="[name, chg] in (marketCtx.sector_trend.bottom || [])" :key="name" class="ctx-row">
              <span class="ctx-label">{{ name }}</span>
              <span class="ctx-val down">{{ chg }}%</span>
            </div>
          </div>
          <!-- 뉴스 -->
          <div class="ctx-card ctx-news" v-if="marketCtx.news?.length">
            <div class="ctx-title">주요 뉴스</div>
            <div v-for="(n, i) in marketCtx.news.slice(0,6)" :key="i" class="news-item">
              <span class="news-num">{{ i + 1 }}</span>{{ n }}
            </div>
          </div>
        </div>
      </div>

      <!-- LLM 생성 로딩 -->
      <div v-if="llmLoading" class="panel">
        <div class="loading-box">
          <div class="spinner spinner-llm"></div>
          <div>
            <div style="color:#a78bfa;font-weight:600">Claude AI 분석 중...</div>
            <div style="font-size:12px;margin-top:4px">시장 데이터 수집 → 기술 지표 요약 → 전략 생성 (30초~1분 소요)</div>
          </div>
        </div>
      </div>

      <!-- 방금 생성된 전략 결과 -->
      <div v-if="llmResult" class="panel llm-result-panel">
        <div class="panel-header">
          <span class="panel-title">생성된 전략</span>
          <div style="display:flex;align-items:center;gap:10px">
            <span class="confidence-badge" :class="confidenceClass(llmResult.confidence)">
              신뢰도 {{ llmResult.confidence }}%
            </span>
            <span class="risk-badge" :class="'risk-' + llmResult.risk_level">
              {{ {low:'저위험', medium:'중위험', high:'고위험'}[llmResult.risk_level] || llmResult.risk_level }}
            </span>
          </div>
        </div>
        <div class="result-body">
          <div class="result-name">{{ llmResult.strategy_name }}</div>
          <div class="result-analysis">{{ llmResult.analysis }}</div>
          <div class="conditions-list">
            <div v-for="(c, i) in llmResult.conditions" :key="i" class="condition-chip">
              <span class="c-ind">{{ c.indicator }}</span>
              <span class="c-cond">{{ c.condition }}</span>
              <span class="c-val">{{ c.value }}{{ c.value2 != null ? ' ~ ' + c.value2 : '' }}</span>
            </div>
          </div>
          <div class="result-actions">
            <span class="result-hint">전략 탭에서 봇에 적용할 수 있습니다</span>
            <button class="btn-secondary" @click="loadGeneratedStrategies">히스토리 새로고침</button>
          </div>
        </div>
      </div>

      <!-- 생성 이력 -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">생성 이력</span>
          <span class="meta-info">매일 08:30 자동 생성 · 최근 20개</span>
        </div>
        <div v-if="generatedStrategies.length === 0" class="empty-state">
          아직 생성된 전략이 없습니다.<br/>
          <small>"✦ 전략 생성" 버튼을 클릭하거나 매일 08:30에 자동 실행됩니다.</small>
        </div>
        <div v-else>
          <div
            v-for="s in generatedStrategies"
            :key="s.id"
            class="history-item"
            :class="{ expanded: expandedId === s.id }"
            @click="expandedId = expandedId === s.id ? null : s.id"
          >
            <div class="history-row">
              <div class="history-left">
                <span class="history-name">{{ s.name }}</span>
                <span class="history-type">{{ s.strategy_type }}</span>
              </div>
              <div class="history-right">
                <span class="confidence-badge sm" :class="confidenceClass(s.ai_confidence)">
                  {{ s.ai_confidence }}%
                </span>
                <span class="history-date">{{ fmtDate(s.created_at) }}</span>
                <span class="expand-icon">{{ expandedId === s.id ? '▲' : '▼' }}</span>
              </div>
            </div>
            <div v-if="expandedId === s.id" class="history-detail">
              <div class="result-analysis">{{ s.ai_analysis }}</div>
              <div class="conditions-list">
                <div v-for="(c, i) in s.conditions" :key="i" class="condition-chip">
                  <span class="c-ind">{{ c.indicator }}</span>
                  <span class="c-cond">{{ c.condition }}</span>
                  <span class="c-val">{{ c.value }}{{ c.value2 != null ? ' ~ ' + c.value2 : '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 사용 데이터 안내 -->
      <div class="info-box">
        <strong>데이터 소스</strong>
        <ul>
          <li>pykrx — KOSPI/KOSDAQ 지수, 투자자별 순매수(외국인/기관/개인), 섹터별 등락</li>
          <li>yfinance — S&P500, 나스닥, VIX(공포지수), 달러/원 환율</li>
          <li>네이버 금융 — 시장 뉴스 헤드라인 10건</li>
          <li>DB 기술 지표 — RSI 분포, MACD, MA20 상회 종목 비율</li>
        </ul>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API = 'http://localhost:8001/api/v1'

const tab = ref('score')

// ── ML 스코어링 ──────────────────────────────────────────────────
const topScores = ref([])
const scoreMeta = ref(null)
const scoreLoading = ref(false)
let scoreTaskId = null
let scorePollTimer = null

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function loadScores() {
  try {
    const res = await fetch(`${API}/ai/scores`, { headers: headers() })
    const data = await res.json()
    scoreMeta.value = data.meta
    topScores.value = Object.entries(data.scores || {})
      .map(([ticker, score]) => ({ ticker, score }))
      .sort((a, b) => b.score - a.score)
  } catch {
    // 무시
  }
}

async function runScoring() {
  scoreLoading.value = true
  try {
    const res = await fetch(`${API}/ai/score`, { method: 'POST', headers: headers() })
    const data = await res.json()
    scoreTaskId = data.task_id
    pollScore()
  } catch {
    scoreLoading.value = false
  }
}

async function pollScore() {
  if (!scoreTaskId) return
  try {
    const res = await fetch(`${API}/ai/score/${scoreTaskId}`, { headers: headers() })
    const data = await res.json()
    if (data.status === 'completed') {
      scoreLoading.value = false
      scoreTaskId = null
      await loadScores()
    } else if (data.status === 'failed') {
      scoreLoading.value = false
      scoreTaskId = null
      alert('ML 학습 실패: ' + (data.error || ''))
    } else {
      scorePollTimer = setTimeout(pollScore, 3000)
    }
  } catch {
    scorePollTimer = setTimeout(pollScore, 5000)
  }
}

function scoreColor(score) {
  if (score >= 70) return '#10b981'
  if (score >= 50) return '#f59e0b'
  return '#6b7280'
}

// ── 파라미터 최적화 ──────────────────────────────────────────────
const strategies = ref([])
const optLoading = ref(false)
const optResult = ref(null)
let optTaskId = null
let optPollTimer = null

const today = new Date().toISOString().split('T')[0]
const oneYearAgo = new Date(Date.now() - 365 * 86400000).toISOString().split('T')[0]

const optForm = ref({
  strategy_id: '',
  indicator: 'rsi',
  condition: 'below',
  value_min: 20,
  value_max: 40,
  value_step: 2,
  start_date: oneYearAgo,
  end_date: today,
})

async function loadStrategies() {
  try {
    const res = await fetch(`${API}/strategies`, { headers: headers() })
    strategies.value = await res.json()
  } catch {
    // 무시
  }
}

async function runOptimize() {
  optLoading.value = true
  optResult.value = null
  try {
    const body = { ...optForm.value, strategy_id: Number(optForm.value.strategy_id) }
    const res = await fetch(`${API}/ai/optimize`, {
      method: 'POST',
      headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    optTaskId = data.task_id
    pollOptimize()
  } catch {
    optLoading.value = false
  }
}

async function pollOptimize() {
  if (!optTaskId) return
  try {
    const res = await fetch(`${API}/ai/optimize/${optTaskId}`, { headers: headers() })
    const data = await res.json()
    if (data.status === 'completed') {
      optLoading.value = false
      optTaskId = null
      optResult.value = data.result
    } else if (data.status === 'failed') {
      optLoading.value = false
      optTaskId = null
      alert('최적화 실패: ' + (data.error || ''))
    } else {
      optPollTimer = setTimeout(pollOptimize, 3000)
    }
  } catch {
    optPollTimer = setTimeout(pollOptimize, 5000)
  }
}

function numCls(v) {
  if (v > 0) return 'positive'
  if (v < 0) return 'negative'
  return ''
}

// ── SVG 차트 ─────────────────────────────────────────────────────
const svgW = 680
const svgH = 220
const PAD = 52

const sharpeMin = computed(() => {
  if (!optResult.value?.results?.length) return 0
  return Math.min(...optResult.value.results.map(r => r.sharpe))
})

const sharpeMax = computed(() => {
  if (!optResult.value?.results?.length) return 1
  return Math.max(...optResult.value.results.map(r => r.sharpe))
})

function dotX(idx) {
  const n = optResult.value.results.length
  const w = svgW - PAD * 2
  return PAD + (n <= 1 ? w / 2 : (idx / (n - 1)) * w)
}

function dotY(sharpe) {
  const range = sharpeMax.value - sharpeMin.value
  const norm = range > 0 ? (sharpe - sharpeMin.value) / range : 0.5
  const top = 24
  const bottom = svgH - 20
  return bottom - norm * (bottom - top)
}

const linePoints = computed(() => {
  if (!optResult.value?.results) return ''
  return optResult.value.results.map((r, i) => `${dotX(i)},${dotY(r.sharpe)}`).join(' ')
})

const gridLines = computed(() => {
  if (!optResult.value?.results?.length) return []
  const min = sharpeMin.value
  const max = sharpeMax.value
  return [0, 1, 2, 3, 4].map(i => {
    const val = min + (max - min) * (i / 4)
    return { y: dotY(val), label: val.toFixed(2) }
  })
})

const xLabels = computed(() => {
  if (!optResult.value?.results?.length) return []
  const results = optResult.value.results
  const step = Math.max(1, Math.ceil(results.length / 10))
  return results
    .map((r, i) => ({ x: dotX(i), label: r.value, i }))
    .filter(({ i }) => i % step === 0 || i === results.length - 1)
})

// ── LLM 전략 생성 ──────────────────────────────────────────────
const llmLoading = ref(false)
const llmResult = ref(null)
const marketCtx = ref(null)
const ctxLoading = ref(false)
const generatedStrategies = ref([])
const expandedId = ref(null)
let llmTaskId = null
let llmPollTimer = null

async function switchLlmTab() {
  tab.value = 'llm'
  if (generatedStrategies.value.length === 0) await loadGeneratedStrategies()
}

async function loadMarketContext() {
  ctxLoading.value = true
  try {
    const res = await fetch(`${API}/ai/market-context`, { headers: headers() })
    const data = await res.json()
    if (data.status === 'ok') marketCtx.value = data.context
  } catch {
    // 무시
  } finally {
    ctxLoading.value = false
  }
}

async function loadGeneratedStrategies() {
  try {
    const res = await fetch(`${API}/ai/generated-strategies`, { headers: headers() })
    if (res.ok) generatedStrategies.value = await res.json()
  } catch {
    // 무시
  }
}

async function runGenerate() {
  llmLoading.value = true
  llmResult.value = null
  try {
    const res = await fetch(`${API}/ai/generate-strategy`, { method: 'POST', headers: headers() })
    const data = await res.json()
    llmTaskId = data.task_id
    pollGenerate()
  } catch {
    llmLoading.value = false
  }
}

async function pollGenerate() {
  if (!llmTaskId) return
  try {
    const res = await fetch(`${API}/ai/generate-strategy/${llmTaskId}`, { headers: headers() })
    const data = await res.json()
    if (data.status === 'completed') {
      llmLoading.value = false
      llmTaskId = null
      const r = data.result
      if (r.status === 'ok') {
        llmResult.value = r
        await loadGeneratedStrategies()
      } else {
        alert('전략 생성 실패: ' + (r.message || ''))
      }
    } else if (data.status === 'failed') {
      llmLoading.value = false
      llmTaskId = null
      alert('전략 생성 오류: ' + (data.error || ''))
    } else {
      llmPollTimer = setTimeout(pollGenerate, 3000)
    }
  } catch {
    llmPollTimer = setTimeout(pollGenerate, 5000)
  }
}

function confidenceClass(c) {
  if (c >= 70) return 'conf-high'
  if (c >= 40) return 'conf-mid'
  return 'conf-low'
}

function fmtDate(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─────────────────────────────────────────────────────────────────
onMounted(() => {
  loadScores()
  loadStrategies()
})

onUnmounted(() => {
  if (scorePollTimer) clearTimeout(scorePollTimer)
  if (optPollTimer) clearTimeout(optPollTimer)
  if (llmPollTimer) clearTimeout(llmPollTimer)
})
</script>

<style scoped>
.ai-view { max-width: 1000px; }

.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #e5e7eb; }
.subtitle { margin: 0; font-size: 13px; color: #6b7280; }

/* 탭 */
.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 20px;
  border-bottom: 1px solid #2a2d3e;
}

.tab-btn {
  padding: 10px 22px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #6b7280;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: -1px;
}

.tab-btn:hover { color: #e5e7eb; }
.tab-btn.active { color: #4f9eff; border-bottom-color: #4f9eff; }

/* 탭 콘텐츠 */
.tab-content { display: flex; flex-direction: column; gap: 16px; }

/* 패널 */
.panel {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid #2a2d3e;
}

.panel-title { font-size: 14px; font-weight: 600; color: #e5e7eb; }

.header-info { display: flex; flex-direction: column; gap: 3px; }
.meta-info { font-size: 12px; color: #6b7280; }

.header-actions { display: flex; gap: 8px; }

/* 버튼 */
.btn-primary {
  padding: 7px 16px;
  background: #2563eb;
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  padding: 7px 14px;
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-secondary:hover:not(:disabled) { border-color: #4f9eff; color: #4f9eff; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

/* 로딩 */
.loading-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 40px 24px;
  color: #6b7280;
  font-size: 13px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #2a2d3e;
  border-top-color: #4f9eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 빈 상태 */
.empty-state {
  padding: 60px 24px;
  text-align: center;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.7;
}

/* 테이블 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  padding: 9px 16px;
  text-align: left;
  color: #6b7280;
  font-weight: 500;
  font-size: 11px;
  background: rgba(20, 23, 32, 0.5);
  border-bottom: 1px solid #2a2d3e;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.data-table td {
  padding: 10px 16px;
  color: #e5e7eb;
  border-bottom: 1px solid #1a1f2e;
}

.data-table tbody tr:hover { background: #1f2235; }
.data-table tbody tr:last-child td { border-bottom: none; }

.rank { color: #6b7280; font-size: 12px; }
.ticker-cell { font-weight: 600; color: #4f9eff; font-family: monospace; }

.score-val { font-weight: 700; font-size: 14px; text-align: right; }

.bar-cell { width: 200px; }
.score-bar-wrap {
  height: 6px;
  background: #2a2d3e;
  border-radius: 3px;
  overflow: hidden;
}
.score-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* 수익/손실 색 */
.positive { color: #ef4444; }
.negative { color: #10b981; }

/* 최적 행 */
.best-row td { background: rgba(245, 158, 11, 0.08); }
.best-row td:first-child { border-left: 2px solid #f59e0b; }

.best-tag {
  font-size: 13px;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 4px 10px;
  border-radius: 6px;
}

/* 모델 설명 박스 */
.info-box {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 10px;
  padding: 16px 20px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.7;
}
.info-box strong { color: #9ca3af; display: block; margin-bottom: 8px; }
.info-box ul { margin: 0; padding-left: 18px; }
.info-box li { margin-bottom: 3px; }

/* 최적화 폼 */
.opt-form { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

.form-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.form-row label {
  width: 90px;
  flex-shrink: 0;
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
}

.form-row select,
.form-row input[type="number"],
.form-row input[type="date"] {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 13px;
  padding: 7px 10px;
  outline: none;
  transition: border-color 0.15s;
}
.form-row select:focus,
.form-row input:focus { border-color: #4f9eff; }

.form-row select { min-width: 200px; }
.form-row input[type="number"] { width: 100px; }
.form-row input[type="date"] { width: 150px; }

.range-inputs { display: flex; align-items: center; gap: 8px; }
.sep { color: #4b5563; font-size: 13px; }

.form-hint { font-size: 12px; color: #4b5563; padding-left: 106px; }

.form-actions { padding-left: 106px; }

/* SVG 차트 */
.chart-wrap {
  padding: 16px 16px 8px;
  overflow-x: auto;
}
.opt-svg { display: block; }

/* LLM 탭 버튼 */
.tab-btn.llm-tab { color: #a78bfa; }
.tab-btn.llm-tab.active { color: #a78bfa; border-bottom-color: #a78bfa; }

/* LLM 전략 생성 버튼 */
.btn-llm {
  padding: 7px 18px;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.02em;
}
.btn-llm:hover:not(:disabled) { background: linear-gradient(135deg, #6d28d9, #9333ea); }
.btn-llm:disabled { opacity: 0.5; cursor: not-allowed; }

/* 시장 컨텍스트 그리드 */
.ctx-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1px;
  background: #2a2d3e;
}
.ctx-card {
  background: #1a1d27;
  padding: 16px 18px;
}
.ctx-news { grid-column: 1 / -1; }
.ctx-title { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
.ctx-sub { font-size: 10px; color: #4b5563; margin-bottom: 4px; }
.ctx-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; }
.ctx-label { font-size: 12px; color: #9ca3af; }
.ctx-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.ctx-val.up { color: #ef4444; }
.ctx-val.down { color: #60a5fa; }
.chg { font-size: 11px; font-weight: 400; margin-left: 4px; }
.news-item { font-size: 12px; color: #9ca3af; padding: 3px 0; display: flex; gap: 8px; line-height: 1.5; }
.news-num { color: #4b5563; flex-shrink: 0; width: 14px; }

/* 스피너 LLM 색상 */
.spinner-llm { border-top-color: #a78bfa; }

/* LLM 결과 패널 */
.llm-result-panel { border-color: rgba(167,139,250,.3); }
.result-body { padding: 20px 24px; }
.result-name { font-size: 17px; font-weight: 700; color: #e5e7eb; margin-bottom: 10px; }
.result-analysis { font-size: 13px; color: #9ca3af; line-height: 1.7; margin-bottom: 16px; background: rgba(167,139,250,.05); border-left: 2px solid #7c3aed; padding: 10px 14px; border-radius: 0 6px 6px 0; }
.conditions-list { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.condition-chip { display: flex; align-items: center; gap: 6px; background: #0f1117; border: 1px solid #2a2d3e; border-radius: 20px; padding: 5px 12px; font-size: 12px; }
.c-ind { color: #a78bfa; font-weight: 600; }
.c-cond { color: #6b7280; }
.c-val { color: #e5e7eb; font-weight: 600; }
.result-actions { display: flex; align-items: center; justify-content: space-between; }
.result-hint { font-size: 12px; color: #4b5563; }

/* 신뢰도 배지 */
.confidence-badge { font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 999px; }
.confidence-badge.conf-high { background: rgba(16,185,129,.15); color: #10b981; }
.confidence-badge.conf-mid  { background: rgba(245,158,11,.15); color: #f59e0b; }
.confidence-badge.conf-low  { background: rgba(107,114,128,.15); color: #9ca3af; }
.confidence-badge.sm { font-size: 11px; padding: 2px 7px; }

/* 위험도 배지 */
.risk-badge { font-size: 11px; padding: 3px 9px; border-radius: 999px; font-weight: 600; }
.risk-low    { background: rgba(16,185,129,.15); color: #10b981; }
.risk-medium { background: rgba(245,158,11,.15); color: #f59e0b; }
.risk-high   { background: rgba(239,68,68,.15);  color: #ef4444; }

/* 생성 이력 */
.history-item { border-bottom: 1px solid #1f2235; cursor: pointer; transition: background 0.1s; }
.history-item:last-child { border-bottom: none; }
.history-item:hover { background: #1f2235; }
.history-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; }
.history-left { display: flex; align-items: center; gap: 10px; }
.history-name { font-size: 13px; color: #e5e7eb; font-weight: 500; }
.history-type { font-size: 11px; color: #4b5563; background: #2a2d3e; padding: 2px 7px; border-radius: 4px; }
.history-right { display: flex; align-items: center; gap: 10px; }
.history-date { font-size: 11px; color: #4b5563; }
.expand-icon { font-size: 10px; color: #4b5563; }
.history-detail { padding: 0 18px 16px; }
</style>
