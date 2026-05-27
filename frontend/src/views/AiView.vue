<template>
  <div class="ai-view">
    <header class="page-header">
      <div class="page-head-text">
        <span class="page-eyebrow">INTELLIGENCE / AI</span>
        <h1 class="page-title">AI 분석</h1>
        <p class="subtitle">ML 스코어링 · 파라미터 최적화 · LLM 전략 자동 생성</p>
      </div>
    </header>

    <!-- 탭 -->
    <nav class="tabs" role="tablist">
      <button
        class="tab-btn"
        type="button"
        :class="{ active: tab === 'score' }"
        role="tab"
        :aria-selected="tab === 'score'"
        @click="tab = 'score'"
      >
        ML 종목 스코어링
      </button>
      <button
        class="tab-btn"
        type="button"
        :class="{ active: tab === 'optimize' }"
        role="tab"
        :aria-selected="tab === 'optimize'"
        @click="tab = 'optimize'"
      >
        파라미터 최적화
      </button>
      <button
        class="tab-btn llm-tab"
        type="button"
        :class="{ active: tab === 'llm' }"
        role="tab"
        :aria-selected="tab === 'llm'"
        @click="switchLlmTab"
      >
        <svg
          class="tab-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
          <path d="M19 3v3" />
          <path d="M17.5 4.5h3" />
        </svg>
        LLM 전략 생성기
      </button>
    </nav>

    <!-- ============================================================
         ML 종목 스코어링 탭
         ============================================================ -->
    <section v-if="tab === 'score'" class="tab-content">
      <div class="panel">
        <div class="panel-head">
          <div class="head-info">
            <span class="panel-title">ML 종목 스코어링</span>
            <span v-if="scoreMeta" class="meta-info">
              기준일 {{ scoreMeta.date }} · 학습 샘플
              {{ scoreMeta.train_samples?.toLocaleString() }} · 매수 신호
              {{ scoreMeta.positive_rate }}%
            </span>
          </div>
          <div class="head-actions">
            <button
              class="btn-ghost"
              type="button"
              :disabled="scoreLoading"
              @click="loadScores"
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
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
              </svg>
              <span>새로고침</span>
            </button>
            <button
              class="btn-primary"
              type="button"
              :disabled="scoreLoading"
              @click="runScoring"
            >
              <svg
                :class="{ spin: scoreLoading }"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path v-if="!scoreLoading" d="M5 12l5 5L20 7" />
                <path v-else d="M21 12a9 9 0 1 1-6-8.5" />
              </svg>
              <span>{{ scoreLoading ? 'TRAINING' : '새로 학습' }}</span>
            </button>
          </div>
        </div>

        <div v-if="scoreLoading" class="loading-box">
          <span class="spinner"></span>
          <span>RandomForest 학습 중 — 수 분 소요됩니다</span>
        </div>

        <div v-else-if="topScores.length === 0" class="empty-state">
          학습 결과가 없습니다. 새로 학습을 실행하세요.
          <small>매일 17:30에 자동 실행됩니다.</small>
        </div>

        <table v-else class="data-table">
          <thead>
            <tr>
              <th class="col-rank">#</th>
              <th>티커</th>
              <th class="th-num">ML 점수</th>
              <th>스코어</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in topScores" :key="item.ticker">
              <td class="rank mono">{{ String(idx + 1).padStart(2, '0') }}</td>
              <td class="ticker-cell"><StockLink :ticker="item.ticker" /></td>
              <td class="score-val td-num" :style="{ color: scoreColor(item.score) }">
                {{ item.score.toFixed(1) }}
              </td>
              <td class="bar-cell">
                <div class="score-bar-wrap">
                  <div
                    class="score-bar"
                    :style="{
                      width: item.score + '%',
                      background: scoreColor(item.score),
                    }"
                  ></div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="info-box">
        <span class="info-tag">MODEL</span>
        <div class="info-body">
          <strong>RandomForest Classifier</strong>
          <ul>
            <li>알고리즘: 트리 100개, 최대 깊이 6</li>
            <li>피처: RSI · MACD 히스토그램 · Stoch K/D · ADX · MA 기울기(20/50) · ATR · 볼린저밴드 위치</li>
            <li>레이블: 5거래일 후 수익률 &gt; 1% → 매수 신호</li>
            <li>학습 기간: 최근 6개월</li>
            <li>점수: 0~100 (높을수록 강도 ↑)</li>
            <li>자동 실행: 매일 17:30 (수집 완료 후)</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- ============================================================
         파라미터 최적화 탭
         ============================================================ -->
    <section v-if="tab === 'optimize'" class="tab-content">
      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">전략 파라미터 최적화</span>
        </div>

        <form class="opt-form" @submit.prevent>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label" for="opt-strategy">전략</label>
              <select id="opt-strategy" v-model="optForm.strategy_id">
                <option value="">전략 선택...</option>
                <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label" for="opt-ind">지표</label>
              <select id="opt-ind" v-model="optForm.indicator">
                <option value="rsi">RSI</option>
                <option value="stoch_k">Stoch K</option>
                <option value="stoch_d">Stoch D</option>
                <option value="adx">ADX</option>
                <option value="macd_histogram">MACD Histogram</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label" for="opt-cond">조건</label>
              <select id="opt-cond" v-model="optForm.condition">
                <option value="below">below · 이하</option>
                <option value="above">above · 이상</option>
              </select>
            </div>

            <div class="form-group form-group-wide">
              <label class="form-label">값 범위 · 간격</label>
              <div class="range-inputs">
                <input v-model.number="optForm.value_min" type="number" placeholder="MIN" />
                <span class="sep">~</span>
                <input v-model.number="optForm.value_max" type="number" placeholder="MAX" />
                <span class="sep">STEP</span>
                <input
                  v-model.number="optForm.value_step"
                  type="number"
                  placeholder="STEP"
                  min="0.1"
                  class="step-input"
                />
              </div>
            </div>

            <div class="form-group form-group-wide">
              <label class="form-label">분석 기간</label>
              <div class="range-inputs">
                <input v-model="optForm.start_date" type="date" />
                <span class="sep">~</span>
                <input v-model="optForm.end_date" type="date" />
              </div>
            </div>
          </div>

          <p class="form-hint">
            고거래량 상위 100종목 대상, 각 값별 1년 백테스트 — 최대 30단계.
          </p>

          <div class="form-actions">
            <button
              class="btn-primary"
              type="button"
              :disabled="optLoading || !optForm.strategy_id"
              @click="runOptimize"
            >
              <svg
                :class="{ spin: optLoading }"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path v-if="!optLoading" d="M5 12l5 5L20 7" />
                <path v-else d="M21 12a9 9 0 1 1-6-8.5" />
              </svg>
              <span>{{ optLoading ? 'OPTIMIZING' : '최적화 실행' }}</span>
            </button>
          </div>
        </form>
      </div>

      <div v-if="optLoading" class="panel">
        <div class="loading-box">
          <span class="spinner"></span>
          <span>Grid Search 백테스트 실행 중 — 수 분 소요됩니다</span>
        </div>
      </div>

      <div v-if="optResult" class="panel">
        <div class="panel-head">
          <span class="panel-title">최적화 결과</span>
          <span v-if="optResult.best" class="best-tag">
            BEST · {{ optResult.best.value }}
            <span class="best-sep">·</span>
            샤프 {{ optResult.best.sharpe.toFixed(2) }}
          </span>
        </div>

        <div v-if="optResult.results?.length > 1" class="chart-wrap">
          <svg :width="svgW" :height="svgH" class="opt-svg">
            <line
              v-for="gl in gridLines"
              :key="gl.y"
              :x1="PAD"
              :y1="gl.y"
              :x2="svgW - PAD"
              :y2="gl.y"
              stroke="rgba(255,255,255,0.05)"
              stroke-width="1"
            />
            <text
              v-for="gl in gridLines"
              :key="'yl' + gl.y"
              :x="PAD - 8"
              :y="gl.y + 4"
              fill="#71717a"
              font-size="10"
              font-family="JetBrains Mono, monospace"
              text-anchor="end"
            >{{ gl.label }}</text>
            <polyline
              :points="linePoints"
              fill="none"
              stroke="#60a5fa"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <circle
              v-for="(r, i) in optResult.results"
              :key="'dot' + i"
              :cx="dotX(i)"
              :cy="dotY(r.sharpe)"
              :r="r === optResult.best ? 6 : 3.5"
              :fill="r === optResult.best ? '#f59e0b' : '#60a5fa'"
              :stroke="r === optResult.best ? '#fafafa' : 'none'"
              stroke-width="1.5"
            />
            <text
              v-for="xl in xLabels"
              :key="'xl' + xl.x"
              :x="xl.x"
              :y="svgH - 4"
              fill="#71717a"
              font-size="9"
              font-family="JetBrains Mono, monospace"
              text-anchor="middle"
            >{{ xl.label }}</text>
            <text
              x="16"
              y="18"
              fill="#a1a1aa"
              font-size="10"
              font-family="JetBrains Mono, monospace"
              letter-spacing="0.1em"
            >SHARPE</text>
          </svg>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th>{{ optResult.indicator }} 값</th>
              <th class="th-num">샤프</th>
              <th class="th-num">총수익률</th>
              <th class="th-num">승률</th>
              <th class="th-num">거래수</th>
              <th class="th-num">점수</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in optResult.results"
              :key="r.value"
              :class="{ 'best-row': r === optResult.best }"
            >
              <td class="mono">{{ r.value }}</td>
              <td class="td-num" :class="numCls(r.sharpe)">{{ r.sharpe.toFixed(2) }}</td>
              <td class="td-num" :class="numCls(r.total_return)">{{ r.total_return.toFixed(1) }}%</td>
              <td class="td-num">{{ r.win_rate.toFixed(1) }}%</td>
              <td class="td-num">{{ r.num_trades }}</td>
              <td class="td-num">{{ r.score.toFixed(0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ============================================================
         LLM 전략 생성기 탭
         ============================================================ -->
    <section v-if="tab === 'llm'" class="tab-content">
      <div class="panel">
        <div class="panel-head">
          <div class="head-info">
            <span class="panel-title">
              <svg
                class="llm-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
                <path d="M19 3v3" />
                <path d="M17.5 4.5h3" />
              </svg>
              LLM 전략 생성기
            </span>
            <span class="meta-info">
              시장 데이터 분석 → Claude AI가 최적 전략 조건 자동 생성
            </span>
          </div>
          <div class="head-actions">
            <button
              class="btn-ghost"
              type="button"
              :disabled="ctxLoading"
              @click="loadMarketContext"
            >
              <span>시장 미리보기</span>
            </button>
            <button
              class="btn-llm"
              type="button"
              :disabled="llmLoading"
              @click="runGenerate"
            >
              <svg
                :class="{ spin: llmLoading }"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path v-if="!llmLoading" d="m12 4-1.5 4.5L6 10l4.5 1.5L12 16l1.5-4.5L18 10l-4.5-1.5z" />
                <path v-else d="M21 12a9 9 0 1 1-6-8.5" />
              </svg>
              <span>{{ llmLoading ? 'GENERATING' : '전략 생성' }}</span>
            </button>
          </div>
        </div>

        <div v-if="ctxLoading" class="loading-box">
          <span class="spinner"></span>
          <span>시장 데이터 수집 중...</span>
        </div>
        <div v-else-if="marketCtx" class="ctx-grid">
          <div v-if="Object.keys(marketCtx.krx_indices || {}).length" class="ctx-card">
            <div class="ctx-title">국내 지수</div>
            <div v-for="(v, k) in marketCtx.krx_indices" :key="k" class="ctx-row">
              <span class="ctx-label">{{ k }}</span>
              <span class="ctx-val mono" :class="v.change_pct >= 0 ? 'up' : 'down'">
                {{ v.close.toLocaleString() }}
                <span class="chg">
                  ({{ v.change_pct >= 0 ? '+' : '' }}{{ v.change_pct }}%)
                </span>
              </span>
            </div>
          </div>
          <div v-if="Object.keys(marketCtx.global_indices || {}).length" class="ctx-card">
            <div class="ctx-title">글로벌</div>
            <div v-for="(v, k) in marketCtx.global_indices" :key="k" class="ctx-row">
              <span class="ctx-label">{{ k }}</span>
              <span class="ctx-val mono" :class="v.change_pct >= 0 ? 'up' : 'down'">
                {{ v.close.toLocaleString() }}
                <span class="chg">
                  ({{ v.change_pct >= 0 ? '+' : '' }}{{ v.change_pct }}%)
                </span>
              </span>
            </div>
          </div>
          <div v-if="Object.keys(marketCtx.investor_trend || {}).length" class="ctx-card">
            <div class="ctx-title">투자자 순매수 · KOSPI</div>
            <div v-for="(v, k) in marketCtx.investor_trend" :key="k" class="ctx-row">
              <span class="ctx-label">
                {{ { foreign: '외국인', institution: '기관', retail: '개인' }[k] || k }}
              </span>
              <span class="ctx-val mono" :class="v >= 0 ? 'up' : 'down'">
                {{ (v >= 0 ? '+' : '') + Math.round(v / 1e8).toLocaleString() }}억
              </span>
            </div>
          </div>
          <div v-if="marketCtx.sector_trend?.top?.length" class="ctx-card">
            <div class="ctx-title">섹터</div>
            <div class="ctx-sub up">▲ 상승</div>
            <div
              v-for="[name, chg] in marketCtx.sector_trend.top || []"
              :key="name"
              class="ctx-row"
            >
              <span class="ctx-label">{{ name }}</span>
              <span class="ctx-val mono up">+{{ chg }}%</span>
            </div>
            <div class="ctx-sub down">▼ 하락</div>
            <div
              v-for="[name, chg] in marketCtx.sector_trend.bottom || []"
              :key="name"
              class="ctx-row"
            >
              <span class="ctx-label">{{ name }}</span>
              <span class="ctx-val mono down">{{ chg }}%</span>
            </div>
          </div>
          <div v-if="marketCtx.news?.length" class="ctx-card ctx-news">
            <div class="ctx-title">주요 뉴스</div>
            <div
              v-for="(n, i) in marketCtx.news.slice(0, 6)"
              :key="i"
              class="news-item"
            >
              <span class="news-num mono">{{ String(i + 1).padStart(2, '0') }}</span>
              <span>{{ n }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="llmLoading" class="panel">
        <div class="loading-box llm-loading">
          <span class="spinner spinner-llm"></span>
          <div class="llm-loading-text">
            <span class="llm-loading-title">Claude AI 분석 중...</span>
            <span class="llm-loading-sub">
              시장 수집 → 지표 요약 → 전략 생성 (30초~1분)
            </span>
          </div>
        </div>
      </div>

      <!-- 방금 생성된 전략 -->
      <div v-if="llmResult" class="panel llm-result-panel">
        <div class="panel-head">
          <span class="panel-title">생성된 전략</span>
          <div class="badge-row">
            <span v-if="llmResult.ml_enhanced" class="ml-badge">
              <span class="ml-dot"></span>
              ML ENHANCED
            </span>
            <span class="confidence-badge" :class="confidenceClass(llmResult.confidence)">
              신뢰도 {{ llmResult.confidence }}%
            </span>
            <span class="risk-badge" :class="'risk-' + llmResult.risk_level">
              {{ { low: '저위험', medium: '중위험', high: '고위험' }[llmResult.risk_level] || llmResult.risk_level }}
            </span>
          </div>
        </div>
        <div class="result-body">
          <div class="result-name">{{ llmResult.strategy_name }}</div>
          <div class="result-analysis">{{ llmResult.analysis }}</div>
          <div class="conditions-list">
            <div
              v-for="(c, i) in llmResult.conditions"
              :key="i"
              class="condition-chip"
            >
              <span class="c-ind">{{ c.indicator }}</span>
              <span class="c-cond">{{ c.condition }}</span>
              <span class="c-val mono">
                {{ c.value }}{{ c.value2 != null ? ' ~ ' + c.value2 : '' }}
              </span>
            </div>
          </div>

          <div
            v-if="llmResult.backtest && llmResult.backtest.num_trades > 0"
            class="backtest-result"
          >
            <div class="backtest-head">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
              <span>ML 상위 종목 자동 백테스트 · 최근 6개월</span>
            </div>
            <div class="backtest-stats">
              <div class="bt-stat">
                <span class="bt-label">총수익률</span>
                <span
                  class="bt-value mono"
                  :class="llmResult.backtest.total_return_pct >= 0 ? 'profit' : 'loss'"
                >
                  {{ llmResult.backtest.total_return_pct >= 0 ? '+' : ''
                  }}{{ llmResult.backtest.total_return_pct }}%
                </span>
              </div>
              <div class="bt-stat">
                <span class="bt-label">승률</span>
                <span class="bt-value mono">{{ llmResult.backtest.win_rate }}%</span>
              </div>
              <div class="bt-stat">
                <span class="bt-label">거래수</span>
                <span class="bt-value mono">{{ llmResult.backtest.num_trades }}회</span>
              </div>
              <div class="bt-stat">
                <span class="bt-label">샤프</span>
                <span
                  class="bt-value mono"
                  :class="llmResult.backtest.sharpe_ratio >= 0 ? 'profit' : 'loss'"
                >
                  {{ llmResult.backtest.sharpe_ratio }}
                </span>
              </div>
              <div class="bt-stat">
                <span class="bt-label">종목</span>
                <span class="bt-value mono">{{ llmResult.backtest.tickers_tested }}</span>
              </div>
            </div>
          </div>
          <div
            v-else-if="llmResult.backtest && llmResult.backtest.num_trades === 0"
            class="backtest-no-trade"
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
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>백테스트 거래 없음 — 조건이 너무 엄격하거나 ML 학습이 필요합니다</span>
          </div>

          <div class="result-actions">
            <button
              class="btn-primary"
              type="button"
              @click="openApplyModal(llmResult.strategy_id, llmResult.strategy_name)"
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
                <rect x="4" y="6" width="16" height="14" rx="2" />
                <path d="M12 6V3" />
                <path d="M10 3h4" />
                <circle cx="9" cy="13" r="1" />
                <circle cx="15" cy="13" r="1" />
                <path d="M9 17h6" />
              </svg>
              <span>봇에 적용</span>
            </button>
            <button class="btn-ghost" type="button" @click="loadGeneratedStrategies">
              히스토리 새로고침
            </button>
          </div>
        </div>
      </div>

      <!-- 생성 이력 -->
      <div class="panel">
        <div class="panel-head">
          <span class="panel-title">생성 이력</span>
          <span class="meta-info">매일 08:30 자동 생성 · 최근 20개</span>
        </div>
        <div v-if="generatedStrategies.length === 0" class="empty-state">
          아직 생성된 전략이 없습니다.
          <small>"전략 생성"을 클릭하거나 매일 08:30에 자동 실행됩니다.</small>
        </div>
        <div v-else class="history-list">
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
                <span class="history-type mono">{{ s.strategy_type }}</span>
              </div>
              <div class="history-right">
                <span
                  class="confidence-badge sm"
                  :class="confidenceClass(s.ai_confidence)"
                >{{ s.ai_confidence }}%</span>
                <span class="history-date mono">{{ fmtDate(s.created_at) }}</span>
                <button
                  class="btn-apply-sm"
                  type="button"
                  @click.stop="openApplyModal(s.id, s.name)"
                >봇에 적용</button>
                <span class="expand-icon" :class="{ open: expandedId === s.id }">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </span>
              </div>
            </div>
            <div v-if="expandedId === s.id" class="history-detail" @click.stop>
              <div class="result-analysis">{{ s.ai_analysis }}</div>
              <div class="conditions-list">
                <div
                  v-for="(c, i) in s.conditions"
                  :key="i"
                  class="condition-chip"
                >
                  <span class="c-ind">{{ c.indicator }}</span>
                  <span class="c-cond">{{ c.condition }}</span>
                  <span class="c-val mono">
                    {{ c.value }}{{ c.value2 != null ? ' ~ ' + c.value2 : '' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="info-box">
        <span class="info-tag">DATA SOURCES</span>
        <div class="info-body">
          <strong>외부 + 내부 통합</strong>
          <ul>
            <li>pykrx — KOSPI/KOSDAQ 지수, 투자자별 순매수, 섹터 등락</li>
            <li>yfinance — S&P500 · 나스닥 · VIX · 달러/원</li>
            <li>네이버 금융 — 시장 뉴스 헤드라인 10건</li>
            <li>내부 DB — RSI 분포 · MACD · MA20 상회 비율</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 봇 적용 모달 -->
    <Teleport to="body">
      <div
        v-if="applyModal.show"
        class="modal-overlay"
        @click.self="closeApplyModal"
      >
        <div class="apply-modal" role="dialog" aria-modal="true">
          <div class="apply-modal-header">
            <div class="apply-modal-head-text">
              <span class="apply-modal-eyebrow">APPLY · 봇 연결</span>
              <h2 class="apply-modal-title">{{ applyModal.strategyName }}</h2>
            </div>
            <button
              class="close-btn"
              type="button"
              aria-label="닫기"
              @click="closeApplyModal"
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
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div class="apply-modal-body">
            <div v-if="applySuccess" class="apply-success">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span><strong>{{ applySuccess }}</strong>에 전략이 적용되었습니다</span>
              <button
                class="btn-ghost"
                type="button"
                style="margin-top: var(--space-3)"
                @click="closeApplyModal"
              >
                닫기
              </button>
            </div>

            <template v-else>
              <div class="apply-section-label">적용할 봇 선택</div>

              <div v-if="botListForApply.length === 0" class="apply-empty">
                생성된 봇이 없습니다.
              </div>

              <div v-else class="apply-bot-list">
                <button
                  v-for="bot in botListForApply"
                  :key="bot.id"
                  class="apply-bot-item"
                  type="button"
                  :disabled="applyLoading"
                  @click="applyToBot(bot)"
                >
                  <div class="apply-bot-left">
                    <span class="apply-bot-name">{{ bot.name }}</span>
                    <span
                      class="apply-bot-type"
                      :class="bot.bot_type === 'scalping' ? 'type-scalping' : 'type-swing'"
                    >
                      {{ bot.bot_type === 'scalping' ? '단타' : '스윙' }}
                    </span>
                  </div>
                  <div class="apply-bot-right">
                    <span
                      class="apply-bot-status"
                      :class="bot.status === 'RUNNING' ? 'status-running' : 'status-idle'"
                    >{{ bot.status }}</span>
                    <span class="apply-arrow" aria-hidden="true">→</span>
                  </div>
                </button>
              </div>

              <div class="apply-divider"></div>

              <button
                class="btn-new-bot"
                type="button"
                @click="createNewBotWithStrategy"
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
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>새 봇 생성 · 전략 자동 적용</span>
              </button>
            </template>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import StockLink from '@/components/StockLink.vue'

const router = useRouter()
const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const tab = ref('score')

// ── ML 스코어링 ──────────────────────────────────────────────────
const topScores = ref([])
const scoreMeta = ref(null)
const scoreLoading = ref(false)
let scoreTaskId = null
let scorePollTimer = null
let scoreStartTime = null

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
  scoreStartTime = Date.now()
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
  if (Date.now() - scoreStartTime > 600000) {
    scoreLoading.value = false
    scoreTaskId = null
    alert('ML 학습 타임아웃 (10분 초과)')
    return
  }
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
  if (score >= 70) return '#22c55e'
  if (score >= 50) return '#f59e0b'
  return '#71717a'
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
  if (v > 0) return 'profit'
  if (v < 0) return 'loss'
  return ''
}

// ── SVG 차트 ─────────────────────────────────────────────────────
const svgW = 680
const svgH = 220
const PAD = 52

const sharpeMin = computed(() => {
  if (!optResult.value?.results?.length) return 0
  return Math.min(...optResult.value.results.map((r) => r.sharpe))
})

const sharpeMax = computed(() => {
  if (!optResult.value?.results?.length) return 1
  return Math.max(...optResult.value.results.map((r) => r.sharpe))
})

function dotX(idx) {
  const n = optResult.value.results.length
  const w = svgW - PAD * 2
  return PAD + (n <= 1 ? w / 2 : (idx / (n - 1)) * w)
}

function dotY(sharpe) {
  const range = sharpeMax.value - sharpeMin.value
  const norm = range > 0 ? (sharpe - sharpeMin.value) / range : 0.5
  const top = 28
  const bottom = svgH - 22
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
  return [0, 1, 2, 3, 4].map((i) => {
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

// ── 봇 적용 모달 ─────────────────────────────────────────────────
const applyModal = ref({ show: false, strategyId: null, strategyName: '' })
const botListForApply = ref([])
const applyLoading = ref(false)
const applySuccess = ref(false)

async function openApplyModal(strategyId, strategyName) {
  applyModal.value = { show: true, strategyId, strategyName }
  applySuccess.value = false
  try {
    const res = await fetch(`${API}/bots`, { headers: headers() })
    botListForApply.value = await res.json()
  } catch {
    botListForApply.value = []
  }
}

function closeApplyModal() {
  applyModal.value = { show: false, strategyId: null, strategyName: '' }
}

async function applyToBot(bot) {
  applyLoading.value = true
  try {
    const res = await fetch(`${API}/bots/${bot.id}`, {
      method: 'PUT',
      headers: { ...headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: applyModal.value.strategyId }),
    })
    if (res.ok) {
      applySuccess.value = bot.name
    } else {
      alert('적용 실패: 실행 중인 봇은 수정할 수 없습니다')
    }
  } finally {
    applyLoading.value = false
  }
}

function createNewBotWithStrategy() {
  router.push({ path: '/bots', query: { strategy_id: applyModal.value.strategyId } })
}

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
.ai-view {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ==========================================================================
   Page header
   ========================================================================== */

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-faint);
}

.page-head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.page-eyebrow {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  margin: 0;
}

.subtitle {
  margin: var(--space-1) 0 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

/* ==========================================================================
   Tabs
   ========================================================================== */

.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border-faint);
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  margin-bottom: -1px;
  transition:
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.tab-icon {
  width: 13px;
  height: 13px;
}

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-btn.llm-tab {
  color: var(--violet);
}

.tab-btn.llm-tab.active {
  color: var(--violet);
  border-bottom-color: var(--violet);
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ==========================================================================
   Panel
   ========================================================================== */

.panel {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.head-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.panel-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.llm-icon {
  width: 14px;
  height: 14px;
  color: var(--violet);
}

.meta-info {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
}

.head-actions {
  display: flex;
  gap: var(--space-2);
}

/* ==========================================================================
   Buttons
   ========================================================================== */

.btn-primary,
.btn-ghost,
.btn-llm {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.btn-primary {
  background: var(--accent);
  color: var(--bg-base);
  border: none;
  box-shadow: var(--shadow-gold);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-primary svg,
.btn-ghost svg,
.btn-llm svg {
  width: 13px;
  height: 13px;
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}

.btn-ghost:hover:not(:disabled) {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-llm {
  background: linear-gradient(135deg, var(--violet-strong), var(--violet));
  color: #fff;
  border: none;
  box-shadow: 0 4px 16px -6px rgba(167, 139, 250, 0.5);
}

.btn-llm:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.1);
}

.btn-llm:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ==========================================================================
   Loading
   ========================================================================== */

.loading-box {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-10) var(--space-5);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  letter-spacing: var(--tracking-wide);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.spinner-llm {
  border-top-color: var(--violet);
}

.llm-loading {
  align-items: flex-start;
}

.llm-loading-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.llm-loading-title {
  color: var(--violet);
  font-weight: 700;
}

.llm-loading-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
  font-family: var(--font-mono);
  text-transform: none;
}

/* ==========================================================================
   Empty state
   ========================================================================== */

.empty-state {
  padding: var(--space-12) var(--space-5);
  text-align: center;
  color: var(--text-faint);
  font-size: var(--text-sm);
  line-height: var(--leading-loose);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.empty-state small {
  color: var(--text-faint);
  font-size: var(--text-xs);
}

/* ==========================================================================
   Data table
   ========================================================================== */

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.data-table th {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-faint);
}

.data-table th.th-num,
.data-table th.col-rank {
  text-align: right;
}

.data-table th.col-rank {
  width: 56px;
}

.data-table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  color: var(--text-secondary);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.data-table tbody tr:hover td {
  background: var(--surface-2);
}

.mono {
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wide);
}

.rank {
  color: var(--text-muted);
  font-size: var(--text-xs);
  text-align: right;
}

.ticker-cell {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
}

.score-val {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: var(--text-md);
}

.td-num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.bar-cell {
  width: 220px;
}

.score-bar-wrap {
  height: 6px;
  background: var(--surface-2);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.score-bar {
  height: 100%;
  border-radius: var(--radius-xs);
  transition: width var(--dur-slow) var(--ease-out);
}

.profit {
  color: var(--profit);
}
.loss {
  color: var(--loss);
}

.best-row td {
  background: var(--accent-bg);
}

.best-row td:first-child {
  border-left: 2px solid var(--accent);
}

.best-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-bg);
  padding: 4px var(--space-2);
  border-radius: var(--radius-xs);
  border: 1px solid var(--accent-border);
  letter-spacing: var(--tracking-wider);
}

.best-sep {
  color: var(--accent-dim);
}

/* ==========================================================================
   Info box
   ========================================================================== */

.info-box {
  display: flex;
  gap: var(--space-4);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}

.info-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  color: var(--accent);
  background: var(--accent-bg);
  padding: 4px 8px;
  border-radius: var(--radius-xs);
  height: fit-content;
  white-space: nowrap;
  border: 1px solid var(--accent-border);
}

.info-body {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-loose);
}

.info-body strong {
  display: block;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.info-body ul {
  margin: 0;
  padding-left: var(--space-4);
}

.info-body li {
  margin-bottom: 3px;
}

/* ==========================================================================
   Optimize form
   ========================================================================== */

.opt-form {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group-wide {
  grid-column: span 3;
}

.form-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  font-weight: 500;
}

.form-group select,
.form-group input,
.range-inputs input {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-sm);
  padding: 7px var(--space-2);
  outline: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.form-group select:focus,
.form-group input:focus,
.range-inputs input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.range-inputs {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.range-inputs input {
  width: 110px;
}

.range-inputs .step-input {
  width: 80px;
}

.sep {
  font-family: var(--font-mono);
  color: var(--text-faint);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wider);
}

.form-hint {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wide);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

/* ==========================================================================
   SVG chart
   ========================================================================== */

.chart-wrap {
  padding: var(--space-4);
  overflow-x: auto;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border-faint);
}

.opt-svg {
  display: block;
}

/* ==========================================================================
   LLM market context grid
   ========================================================================== */

.ctx-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1px;
  background: var(--border-faint);
}

.ctx-card {
  background: var(--surface-1);
  padding: var(--space-4) var(--space-5);
}

.ctx-news {
  grid-column: 1 / -1;
}

.ctx-title {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-bottom: var(--space-3);
}

.ctx-sub {
  font-family: var(--font-mono);
  font-size: 10px;
  margin-bottom: 4px;
  margin-top: 6px;
  letter-spacing: var(--tracking-wider);
}

.ctx-sub.up {
  color: var(--profit);
}

.ctx-sub.down {
  color: var(--loss);
}

.ctx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
}

.ctx-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.ctx-val {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.ctx-val.up {
  color: var(--profit);
}

.ctx-val.down {
  color: var(--loss);
}

.chg {
  font-size: var(--text-xs);
  font-weight: 400;
  margin-left: 4px;
}

.news-item {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  padding: 4px 0;
  display: flex;
  gap: var(--space-2);
  line-height: var(--leading-snug);
}

.news-num {
  color: var(--text-faint);
  flex-shrink: 0;
  width: 22px;
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

/* ==========================================================================
   LLM result panel
   ========================================================================== */

.llm-result-panel {
  border-color: var(--violet-border);
}

.llm-result-panel .panel-head {
  background: var(--violet-bg);
}

.badge-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.result-body {
  padding: var(--space-5);
}

.result-name {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
  letter-spacing: var(--tracking-tight);
}

.result-analysis {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-loose);
  margin-bottom: var(--space-4);
  background: var(--violet-bg);
  border-left: 2px solid var(--violet);
  padding: var(--space-3) var(--space-4);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.conditions-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.condition-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  padding: 4px var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

.c-ind {
  color: var(--violet);
  font-weight: 700;
  text-transform: uppercase;
}

.c-cond {
  color: var(--text-muted);
}

.c-val {
  color: var(--text-primary);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* ==========================================================================
   Confidence / risk / ML badges
   ========================================================================== */

.ml-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 4px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--up-bg);
  color: var(--up-strong);
  border: 1px solid rgba(34, 197, 94, 0.3);
  letter-spacing: var(--tracking-wider);
}

.ml-dot {
  width: 5px;
  height: 5px;
  border-radius: var(--radius-full);
  background: var(--up-strong);
  box-shadow: 0 0 6px var(--up-strong);
}

.confidence-badge {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  padding: 4px var(--space-2);
  border-radius: var(--radius-full);
  letter-spacing: var(--tracking-wider);
}

.confidence-badge.conf-high {
  background: var(--up-bg);
  color: var(--up-strong);
}
.confidence-badge.conf-mid {
  background: var(--accent-bg);
  color: var(--accent);
}
.confidence-badge.conf-low {
  background: var(--surface-2);
  color: var(--text-muted);
}
.confidence-badge.sm {
  font-size: 10px;
  padding: 3px 7px;
}

.risk-badge {
  font-family: var(--font-mono);
  font-size: 10.5px;
  padding: 4px var(--space-2);
  border-radius: var(--radius-full);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.risk-low {
  background: var(--up-bg);
  color: var(--up-strong);
}
.risk-medium {
  background: var(--accent-bg);
  color: var(--accent);
}
.risk-high {
  background: var(--profit-bg);
  color: var(--profit);
}

/* ==========================================================================
   Backtest result block
   ========================================================================== */

.backtest-result {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
}

.backtest-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-bottom: var(--space-3);
}

.backtest-head svg {
  width: 14px;
  height: 14px;
  color: var(--accent);
}

.backtest-stats {
  display: flex;
  gap: var(--space-6);
  flex-wrap: wrap;
}

.bt-stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.bt-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.bt-value {
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.backtest-no-trade {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  color: var(--accent);
  margin-bottom: var(--space-4);
}

.backtest-no-trade svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* ==========================================================================
   History list
   ========================================================================== */

.history-list {
  display: flex;
  flex-direction: column;
}

.history-item {
  border-bottom: 1px solid var(--border-faint);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.history-item:last-child {
  border-bottom: none;
}

.history-item:hover {
  background: var(--surface-2);
}

.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  gap: var(--space-3);
}

.history-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
  min-width: 0;
}

.history-name {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 500;
}

.history-type {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--surface-2);
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.history-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.history-date {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wide);
}

.btn-apply-sm {
  padding: 4px var(--space-3);
  background: var(--violet-bg);
  border: 1px solid var(--violet-border);
  border-radius: var(--radius-sm);
  color: var(--violet);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.btn-apply-sm:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: var(--violet);
}

.expand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: var(--text-faint);
  transition: transform var(--dur-fast) var(--ease-out);
}

.expand-icon svg {
  width: 14px;
  height: 14px;
}

.expand-icon.open {
  transform: rotate(180deg);
  color: var(--accent);
}

.history-detail {
  padding: 0 var(--space-5) var(--space-4);
}

/* ==========================================================================
   Apply modal
   ========================================================================== */

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  animation: overlayIn var(--dur-base) var(--ease-out);
}

@keyframes overlayIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.apply-modal {
  width: 480px;
  max-width: 92vw;
  max-height: 84vh;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modalIn var(--dur-slow) var(--ease-out);
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.apply-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.apply-modal-head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.apply-modal-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--violet);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.apply-modal-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.close-btn svg {
  width: 14px;
  height: 14px;
}

.close-btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.apply-modal-body {
  padding: var(--space-5);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.apply-section-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.apply-empty {
  font-size: var(--text-sm);
  color: var(--text-faint);
  text-align: center;
  padding: var(--space-5) 0;
}

.apply-bot-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.apply-bot-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  width: 100%;
  text-align: left;
  color: inherit;
  font-family: inherit;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.apply-bot-item:hover:not(:disabled) {
  border-color: var(--violet);
  background: var(--violet-bg);
}

.apply-bot-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.apply-bot-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.apply-bot-name {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 500;
}

.apply-bot-type {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
}

.type-scalping {
  background: var(--accent-bg);
  color: var(--accent);
}

.type-swing {
  background: rgba(96, 165, 250, 0.14);
  color: var(--info);
}

.apply-bot-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.apply-bot-status {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 3px 7px;
  border-radius: var(--radius-full);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
}

.status-running {
  background: var(--up-bg);
  color: var(--up-strong);
}

.status-idle {
  background: var(--surface-2);
  color: var(--text-muted);
}

.apply-arrow {
  font-family: var(--font-mono);
  font-size: var(--text-md);
  color: var(--text-muted);
}

.apply-divider {
  border-top: 1px solid var(--border-faint);
  margin: var(--space-1) 0;
}

.btn-new-bot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--violet-bg);
  border: 1px dashed var(--violet-border);
  border-radius: var(--radius-md);
  color: var(--violet);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  width: 100%;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.btn-new-bot svg {
  width: 13px;
  height: 13px;
}

.btn-new-bot:hover {
  background: rgba(167, 139, 250, 0.2);
  border-color: var(--violet);
}

.apply-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) 0;
  text-align: center;
  font-size: var(--text-md);
  color: var(--up-strong);
}

.apply-success svg {
  width: 36px;
  height: 36px;
  color: var(--up-strong);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .form-group-wide {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .panel-head {
    flex-direction: column;
    align-items: stretch;
  }
  .head-actions {
    justify-content: stretch;
  }
  .head-actions > * {
    flex: 1;
    justify-content: center;
  }
}
</style>
