<template>
  <div class="bot-detail" v-if="bot">
    <!-- 헤더 -->
    <div class="detail-header">
      <div class="header-left">
        <button class="back-btn" @click="router.push('/bots')">← 목록</button>
        <h1>{{ bot.name }}</h1>
        <span class="badge" :class="statusClass(bot.status)">{{ bot.status }}</span>
      </div>
      <div class="header-actions">
        <button
          v-if="bot.status !== 'RUNNING'"
          class="btn-edit"
          @click="openEdit"
        >✏️ 수정</button>
        <button
          v-if="bot.status !== 'RUNNING'"
          class="btn-start"
          @click="startBot"
        >▶ 시작</button>
        <button
          v-if="bot.status === 'RUNNING'"
          class="btn-stop"
          @click="stopBot"
        >⏹ 정지</button>
      </div>
    </div>

    <!-- 설정 요약 카드 -->
    <div class="summary-grid">
      <div class="summary-card">
        <span class="s-label">초기 자금</span>
        <span class="s-value">{{ fmtMoney(bot.initial_cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">현재 캐시</span>
        <span class="s-value">{{ fmtMoney(bot.cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">보유 평가</span>
        <span class="s-value">{{ fmtMoney(bot.holdings_value || 0) }}</span>
      </div>
      <div class="summary-card s-total">
        <span class="s-label">총자산</span>
        <span class="s-value">{{ fmtMoney(bot.total_assets || 0) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">손절 / 익절</span>
        <span class="s-value">{{ bot.stop_loss_pct }}% / {{ bot.take_profit_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">최대 낙폭</span>
        <span class="s-value">{{ bot.max_drawdown_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">포지션 크기</span>
        <span class="s-value">{{ bot.position_size_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">거래 시간</span>
        <span class="s-value">{{ fmtTime(bot.trading_start_time) }} ~ {{ fmtTime(bot.trading_end_time) }}</span>
      </div>
      <template v-if="bot.bot_type === 'scalping'">
        <div class="summary-card">
          <span class="s-label">트레일링 스탑</span>
          <span class="s-value">{{ bot.trailing_stop_pct != null ? bot.trailing_stop_pct + '%' : 'OFF' }}</span>
        </div>
        <div class="summary-card">
          <span class="s-label">연속 확인 봉</span>
          <span class="s-value">{{ bot.confirm_bars ?? 1 }}봉</span>
        </div>
      </template>
    </div>

    <!-- 종합 성과 카드 -->
    <div class="perf-section" v-if="perf">
      <div class="perf-card" :class="perf.total_pnl >= 0 ? 'perf-pos' : 'perf-neg'">
        <span class="p-label">누적 손익</span>
        <span class="p-main">{{ fmtPnl(perf.total_pnl) }}</span>
        <span class="p-sub" :class="pnlClass(perf.total_return_pct)">
          {{ perf.total_return_pct >= 0 ? '+' : '' }}{{ perf.total_return_pct.toFixed(2) }}%
        </span>
      </div>
      <div class="perf-card">
        <span class="p-label">승률</span>
        <span class="p-main">{{ perf.win_rate.toFixed(1) }}%</span>
        <span class="p-sub">{{ perf.winning_trades }}승 {{ perf.losing_trades }}패 ({{ perf.total_trades }}건)</span>
      </div>
      <div class="perf-card">
        <span class="p-label">손익비</span>
        <span class="p-main" :class="perf.profit_factor >= 1 ? 'val-good' : 'val-bad'">
          {{ perf.profit_factor > 0 ? perf.profit_factor.toFixed(2) : '-' }}
        </span>
        <span class="p-sub">평균수익 {{ fmtPnl(perf.avg_win) }}</span>
      </div>
      <div class="perf-card">
        <span class="p-label">샤프 비율</span>
        <span class="p-main" :class="perf.sharpe_ratio >= 1 ? 'val-good' : perf.sharpe_ratio >= 0 ? '' : 'val-bad'">
          {{ perf.sharpe_ratio !== 0 ? perf.sharpe_ratio.toFixed(2) : '-' }}
        </span>
        <span class="p-sub">위험 대비 수익</span>
      </div>
      <div class="perf-card">
        <span class="p-label">최대 낙폭</span>
        <span class="p-main val-bad">{{ perf.max_drawdown > 0 ? '-' + perf.max_drawdown.toFixed(2) + '%' : '-' }}</span>
        <span class="p-sub">최고점 대비</span>
      </div>
      <div class="perf-card">
        <span class="p-label">총 수수료+세금</span>
        <span class="p-main">{{ fmtMoney(perf.total_fee) }}</span>
        <span class="p-sub">최대손실 {{ fmtPnl(perf.worst_trade) }}</span>
      </div>
    </div>

    <!-- 종목 태그 -->
    <div class="tickers-row">
      <span class="tickers-label">대상 종목</span>
      <div class="ticker-tags">
        <span v-for="t in (bot.tickers || [])" :key="t" class="ticker-tag">{{ t }}</span>
        <span v-if="!(bot.tickers || []).length" class="no-tickers">종목 없음</span>
      </div>
    </div>

    <!-- 탭 -->
    <div class="tabs">
      <button
        v-for="tab in ['canvas', 'positions', 'orders', 'executions', 'reports']"
        :key="tab"
        class="tab-btn"
        :class="{ active: activeTab === tab }"
        @click="switchTab(tab)"
      >{{ tabLabel(tab) }}</button>
    </div>

    <!-- 캔버스 탭 -->
    <div v-if="activeTab === 'canvas'">
      <BotCanvas :bot-id="Number(botId)" />
    </div>

    <!-- 포지션 탭 -->
    <div v-if="activeTab === 'positions'">
      <div v-if="positions.length === 0" class="empty-tab">보유 포지션이 없습니다.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>종목</th>
            <th>수량</th>
            <th>평균단가</th>
            <th>현재가</th>
            <th>평가금액</th>
            <th>미실현손익</th>
            <th>수익률</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pos in positions" :key="pos.id">
            <td class="ticker-cell">{{ pos.ticker }}</td>
            <td>{{ pos.quantity.toLocaleString() }}</td>
            <td>{{ fmtPrice(pos.avg_price) }}</td>
            <td>{{ fmtPrice(pos.current_price) }}</td>
            <td>{{ fmtPrice(pos.market_value) }}</td>
            <td :class="pnlClass(pos.unrealized_pnl)">{{ fmtPnl(pos.unrealized_pnl) }}</td>
            <td :class="pnlClass(pos.unrealized_pct)">{{ pos.unrealized_pct > 0 ? '+' : '' }}{{ pos.unrealized_pct.toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 주문 탭 -->
    <div v-if="activeTab === 'orders'">
      <div v-if="orders.length === 0" class="empty-tab">주문 내역이 없습니다.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>시각</th>
            <th>종목</th>
            <th>구분</th>
            <th>수량</th>
            <th>체결가</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td class="time-cell">{{ fmtDatetime(o.created_at) }}</td>
            <td>{{ o.ticker }}</td>
            <td :class="o.order_type === 'BUY' ? 'buy-cell' : 'sell-cell'">{{ o.order_type }}</td>
            <td>{{ o.quantity.toLocaleString() }}</td>
            <td>{{ fmtPrice(o.price) }}</td>
            <td><span class="badge badge-gray">{{ o.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 체결 내역 탭 (매도 손익 중심) -->
    <div v-if="activeTab === 'executions'">
      <div v-if="executions.length === 0" class="empty-tab">체결 내역이 없습니다.</div>
      <template v-else>
        <!-- 주가 차트 + 체결 포인트 -->
        <div class="chart-container" style="margin-bottom: 16px;">
          <div class="chart-title-row">
            <div style="display:flex;align-items:center;gap:10px;">
              <span class="chart-title">주가 & 체결 포인트</span>
              <select v-if="execTickers.length > 1" v-model="selectedExecTicker"
                @change="onExecTickerChange" class="ticker-select">
                <option v-for="t in execTickers" :key="t" :value="t">{{ tickerName(t) }}</option>
              </select>
              <span v-else class="chart-ticker-label">{{ tickerName(selectedExecTicker) }}</span>
            </div>
            <div class="exec-chart-legend">
              <span class="legend-item"><span class="legend-dot" style="background:#60a5fa;"></span>매수</span>
              <span class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span>매도(수익)</span>
              <span class="legend-item"><span class="legend-dot" style="background:#10b981;"></span>매도(손실)</span>
            </div>
          </div>
          <div v-if="execChartLoading" class="chart-loading">차트 불러오는 중...</div>
          <div ref="execChartEl" style="height: 260px;"></div>
        </div>
        <!-- 체결 내역 테이블 -->
        <table class="data-table">
          <thead>
            <tr>
              <th>체결 시각</th>
              <th>종목</th>
              <th>구분</th>
              <th>수량</th>
              <th>체결가</th>
              <th>손익</th>
              <th>수익률</th>
              <th>수수료+세금</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in executions" :key="e.id"
              :class="e.profit_loss != null && e.profit_loss > 0 ? 'exec-profit' : e.profit_loss != null && e.profit_loss < 0 ? 'exec-loss' : ''">
              <td class="time-cell">{{ fmtDatetime(e.executed_at) }}</td>
              <td class="ticker-cell">{{ tickerName(e.ticker) }}</td>
              <td :class="e.execution_type === 'BUY' ? 'buy-cell' : 'sell-cell'">{{ e.execution_type }}</td>
              <td>{{ e.quantity.toLocaleString() }}</td>
              <td>{{ fmtPrice(e.price) }}</td>
              <td :class="pnlClass(e.profit_loss)">
                {{ e.profit_loss != null ? fmtPnl(e.profit_loss) : '-' }}
              </td>
              <td :class="pnlClass(e.profit_loss_pct)">
                {{ e.profit_loss_pct != null ? (e.profit_loss_pct >= 0 ? '+' : '') + e.profit_loss_pct.toFixed(2) + '%' : '-' }}
              </td>
              <td class="fee-cell">{{ fmtPrice((e.fee || 0) + (e.tax || 0)) }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>

    <!-- 보고서 탭 -->
    <div v-if="activeTab === 'reports'">
      <div v-if="reports.length === 0 && !reportScore && !reportScoreInsufficient" class="empty-tab">일별 보고서가 없습니다.</div>
      <div v-else>

        <!-- 데이터 부족 안내 -->
        <div v-if="reportScoreInsufficient" class="insufficient-notice">
          📊 성과 평가를 위한 데이터가 아직 부족합니다.<br>
          <span class="insufficient-reason">{{ reportScoreInsufficient }}</span>
        </div>

        <!-- ① 종합 점수 카드 -->
        <div v-if="reportScore" class="score-section">
          <!-- 점수 원형 + 등급 -->
          <div class="score-main">
            <div class="score-circle" :class="gradeClass(reportScore.grade)">
              <div class="score-num">{{ reportScore.total_score }}</div>
              <div class="score-denom">/ 100</div>
            </div>
            <div class="score-grade-badge" :class="gradeClass(reportScore.grade)">{{ reportScore.grade }}</div>
            <div class="score-summary">{{ reportScore.summary }}</div>
          </div>

          <!-- 카테고리 바 -->
          <div class="score-categories">
            <div
              v-for="(val, key) in reportScore.categories"
              :key="key"
              class="score-cat-row"
            >
              <div class="cat-label">{{ key }}</div>
              <div class="cat-bar-wrap">
                <div class="cat-bar" :style="{ width: val + '%' }" :class="barColor(val)"></div>
              </div>
              <div class="cat-val" :class="barColor(val)">{{ val }}</div>
            </div>
          </div>

          <!-- 강점 / 약점 / 권장사항 -->
          <div class="score-insights">
            <div class="insight-block insight-strength">
              <div class="insight-title">💪 강점</div>
              <ul><li v-for="s in reportScore.strengths" :key="s">{{ s }}</li></ul>
            </div>
            <div class="insight-block insight-weakness">
              <div class="insight-title">⚠️ 약점</div>
              <ul><li v-for="w in reportScore.weaknesses" :key="w">{{ w }}</li></ul>
            </div>
            <div class="insight-block insight-rec">
              <div class="insight-title">💡 권장사항</div>
              <ul><li v-for="r in reportScore.recommendations" :key="r">{{ r }}</li></ul>
            </div>
          </div>

          <!-- 보조 지표 요약 -->
          <div class="meta-row">
            <div class="meta-item"><span class="mi-label">수익률</span><span class="mi-val" :class="reportScore.meta.total_return_pct >= 0 ? 'profit' : 'loss'">{{ reportScore.meta.total_return_pct >= 0 ? '+' : '' }}{{ reportScore.meta.total_return_pct }}%</span></div>
            <div class="meta-item"><span class="mi-label">샤프비율</span><span class="mi-val">{{ reportScore.meta.sharpe_ratio }}</span></div>
            <div class="meta-item"><span class="mi-label">최대낙폭</span><span class="mi-val loss">-{{ reportScore.meta.max_drawdown }}%</span></div>
            <div class="meta-item"><span class="mi-label">승률</span><span class="mi-val">{{ reportScore.meta.win_rate }}%</span></div>
            <div class="meta-item"><span class="mi-label">손익비</span><span class="mi-val">{{ reportScore.meta.profit_factor }}</span></div>
            <div class="meta-item"><span class="mi-label">수익일 비율</span><span class="mi-val">{{ reportScore.meta.winning_days_pct }}%</span></div>
            <div class="meta-item"><span class="mi-label">최대연속손실</span><span class="mi-val" :class="reportScore.meta.max_consecutive_losses > 5 ? 'loss' : ''">{{ reportScore.meta.max_consecutive_losses }}일</span></div>
          </div>
        </div>

        <!-- ② 차트 영역 -->
        <div v-if="reports.length" class="charts-row" style="margin-top: 20px;">
          <div class="chart-container chart-half">
            <div class="chart-title">누적 손익</div>
            <div ref="lineChartEl" style="height: 180px;"></div>
          </div>
          <div class="chart-container chart-half">
            <div class="chart-title">일일 손익</div>
            <div ref="barChartEl" style="height: 180px;"></div>
          </div>
        </div>

        <!-- ③ 보고서 테이블 -->
        <table v-if="reports.length" class="data-table" style="margin-top: 16px;">
          <thead>
            <tr>
              <th>날짜</th>
              <th>총 자산</th>
              <th>캐시</th>
              <th>보유 평가</th>
              <th>일일 손익</th>
              <th>누적 손익</th>
              <th>승률</th>
              <th>거래 수</th>
              <th>MDD</th>
              <th>샤프</th>
              <th>손익비</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id">
              <td>{{ r.date }}</td>
              <td>{{ fmtPrice(r.total_assets) }}</td>
              <td>{{ fmtPrice(r.cash) }}</td>
              <td>{{ fmtPrice(r.holdings_value) }}</td>
              <td :class="pnlClass(r.daily_pnl)">{{ fmtPnl(r.daily_pnl) }}</td>
              <td :class="pnlClass(r.total_pnl)">{{ fmtPnl(r.total_pnl) }}</td>
              <td>{{ r.win_rate.toFixed(1) }}%</td>
              <td>{{ r.total_trades }}</td>
              <td class="mdd-cell">{{ r.max_drawdown > 0 ? '-' + r.max_drawdown.toFixed(2) + '%' : '-' }}</td>
              <td :class="r.sharpe_ratio >= 1 ? 'val-good' : r.sharpe_ratio < 0 ? 'val-bad' : ''">
                {{ r.sharpe_ratio !== 0 ? r.sharpe_ratio.toFixed(2) : '-' }}
              </td>
              <td :class="r.profit_factor >= 1 ? 'val-good' : r.profit_factor > 0 ? 'val-bad' : ''">
                {{ r.profit_factor > 0 ? r.profit_factor.toFixed(2) : '-' }}
              </td>
            </tr>
          </tbody>
        </table>

      </div>
    </div>
    <!-- 수정 모달 -->
    <div v-if="showEdit" class="modal-overlay" @click.self="closeEdit">
      <div class="modal">
        <div class="modal-header">
          <h2>봇 설정 수정</h2>
          <button class="close-btn" @click="closeEdit">✕</button>
        </div>

        <!-- 봇 타입 탭 -->
        <div class="bot-type-tabs">
          <button class="type-tab" :class="{ active: editForm.bot_type === 'swing' }" @click="setEditBotType('swing')">
            📈 스윙 (Swing)
            <span class="tab-desc">일봉 기반 · 5분 주기</span>
          </button>
          <button class="type-tab" :class="{ active: editForm.bot_type === 'scalping' }" @click="setEditBotType('scalping')">
            ⚡ 단타 (Scalping)
            <span class="tab-desc">분봉 기반 · 1분 주기</span>
          </button>
        </div>

        <div class="modal-body">
          <!-- 단타 설정 -->
          <div v-if="editForm.bot_type === 'scalping'" class="scalping-section">
            <div class="section-title">⚡ 단타 설정</div>
            <div class="form-row">
              <div class="form-group">
                <label>분봉 단위</label>
                <select v-model.number="editForm.candle_interval">
                  <option :value="1">1분봉</option>
                  <option :value="3">3분봉</option>
                  <option :value="5">5분봉</option>
                  <option :value="10">10분봉</option>
                  <option :value="15">15분봉</option>
                </select>
              </div>
              <div class="form-group">
                <label>당일 강제 청산</label>
                <div class="toggle-row">
                  <label class="toggle-switch">
                    <input type="checkbox" v-model="editForm.intraday_close" />
                    <span class="toggle-slider"></span>
                  </label>
                  <input v-if="editForm.intraday_close" v-model="editForm.intraday_close_time" type="time" class="time-inline" />
                  <span v-else class="toggle-off-label">OFF</span>
                </div>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>트레일링 스탑 (%) <span class="label-hint">고가 대비 하락 시 청산. 비워두면 비활성화</span></label>
                <input v-model.number="editForm.trailing_stop_pct" type="number" min="0.1" max="10" step="0.1" placeholder="비활성화=빈칸" />
              </div>
              <div class="form-group">
                <label>연속 신호 확인 봉 수 <span class="label-hint">1=즉시 진입, 2=2봉 연속 확인</span></label>
                <input v-model.number="editForm.confirm_bars" type="number" min="1" max="5" step="1" />
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>봇 이름 *</label>
            <input v-model="editForm.name" type="text" />
          </div>
          <div class="form-group">
            <label>전략</label>
            <select v-model="editForm.strategy_id">
              <option :value="null">전략 없음</option>
              <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>종목 (쉼표로 구분)</label>
            <input v-model="editTickersInput" type="text" placeholder="예: 005930,000660" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>손절 (%)</label>
              <input v-model.number="editForm.stop_loss_pct" type="number" min="0" step="0.5" />
            </div>
            <div class="form-group">
              <label>익절 (%)</label>
              <input v-model.number="editForm.take_profit_pct" type="number" min="0" step="0.5" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>최대 낙폭 (%)</label>
              <input v-model.number="editForm.max_drawdown_pct" type="number" min="0" step="0.5" />
            </div>
            <div class="form-group">
              <label>포지션 크기 (%)</label>
              <input v-model.number="editForm.position_size_pct" type="number" min="1" max="100" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>최대 동시 포지션</label>
              <input v-model.number="editForm.max_positions" type="number" min="1" max="20" />
            </div>
            <div class="form-group">
              <label>일일 최대 거래 수</label>
              <input v-model.number="editForm.max_daily_trades" type="number" min="1" />
            </div>
          </div>
          <div class="form-group">
            <label>단일 주문 최대 금액 (원)</label>
            <input v-model.number="editForm.max_order_amount" type="number" min="0" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>거래 시작 시간</label>
              <input v-model="editForm.trading_start_time" type="time" />
            </div>
            <div class="form-group">
              <label>거래 종료 시간</label>
              <input v-model="editForm.trading_end_time" type="time" />
            </div>
          </div>
          <p v-if="editError" class="error-msg">{{ editError }}</p>
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="closeEdit">취소</button>
          <button class="btn-primary" @click="submitEdit" :disabled="editSubmitting">
            {{ editSubmitting ? '저장 중...' : '저장' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="loading">불러오는 중...</div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BotCanvas from '@/components/BotCanvas.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const API = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

const bot = ref(null)
const perf = ref(null)
const positions = ref([])
const orders = ref([])
const executions = ref([])
const reports = ref([])
const reportScore = ref(null)
const reportScoreInsufficient = ref(null)
const strategies = ref([])
const activeTab = ref('canvas')
const lineChartEl = ref(null)
const barChartEl = ref(null)
let lineChart = null
let barChart = null
const execChartEl = ref(null)
let execChart = null
const execTickers = ref([])
const selectedExecTicker = ref('')
const execChartLoading = ref(false)
const stockNames = ref({})

// 수정 모달
const showEdit = ref(false)
const editSubmitting = ref(false)
const editError = ref('')
const editTickersInput = ref('')
const editForm = ref({})

function headers() {
  return { Authorization: `Bearer ${auth.token}` }
}

function jsonHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

const botId = route.params.id

async function fetchBot() {
  const res = await fetch(`${API}/bots/${botId}`, { headers: headers() })
  if (res.ok) bot.value = await res.json()
}

async function fetchStrategies() {
  const res = await fetch(`${API}/strategies`, { headers: headers() })
  if (res.ok) strategies.value = await res.json()
}

function openEdit() {
  const b = bot.value
  editForm.value = {
    name: b.name,
    strategy_id: b.strategy_id ?? null,
    stop_loss_pct: b.stop_loss_pct,
    take_profit_pct: b.take_profit_pct,
    max_drawdown_pct: b.max_drawdown_pct,
    position_size_pct: b.position_size_pct,
    max_positions: b.max_positions,
    max_daily_trades: b.max_daily_trades,
    max_order_amount: b.max_order_amount,
    trading_start_time: fmtTime(b.trading_start_time),
    trading_end_time: fmtTime(b.trading_end_time),
    bot_type: b.bot_type ?? 'swing',
    candle_interval: b.candle_interval ?? 1,
    intraday_close: b.intraday_close ?? false,
    intraday_close_time: fmtTime(b.intraday_close_time) || '14:50',
    trailing_stop_pct: b.trailing_stop_pct ?? null,
    confirm_bars: b.confirm_bars ?? 1,
  }
  editTickersInput.value = (b.tickers || []).join(',')
  editError.value = ''
  showEdit.value = true
}

function closeEdit() {
  showEdit.value = false
}

function setEditBotType(type) {
  editForm.value.bot_type = type
}

async function submitEdit() {
  if (!editForm.value.name?.trim()) { editError.value = '봇 이름을 입력하세요'; return }
  editError.value = ''
  editSubmitting.value = true
  try {
    const payload = {
      ...editForm.value,
      tickers: editTickersInput.value.split(',').map(t => t.trim()).filter(Boolean),
    }
    const res = await fetch(`${API}/bots/${botId}`, {
      method: 'PUT',
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      editError.value = data.detail || '저장 실패'
      return
    }
    closeEdit()
    await fetchBot()
  } finally {
    editSubmitting.value = false
  }
}

async function fetchPerf() {
  const res = await fetch(`${API}/bots/${botId}/performance`, { headers: headers() })
  if (res.ok) perf.value = await res.json()
}

async function fetchPositions() {
  const res = await fetch(`${API}/bots/${botId}/positions`, { headers: headers() })
  if (res.ok) positions.value = await res.json()
}

async function fetchOrders() {
  const res = await fetch(`${API}/bots/${botId}/orders`, { headers: headers() })
  if (res.ok) orders.value = await res.json()
}

async function fetchExecutions() {
  const res = await fetch(`${API}/bots/${botId}/executions`, { headers: headers() })
  if (res.ok) {
    executions.value = await res.json()
    await nextTick()
    renderExecChart(executions.value)
  }
}

async function fetchStockNames() {
  const res = await fetch(`${API}/market/stocks?limit=200`, { headers: headers() })
  if (res.ok) {
    const data = await res.json()
    const map = {}
    for (const s of data.items) map[s.ticker] = s.company_name
    stockNames.value = map
  }
}

function tickerName(ticker) {
  return stockNames.value[ticker] || ticker
}

async function fetchReports() {
  const [rRes, sRes] = await Promise.all([
    fetch(`${API}/bots/${botId}/reports`, { headers: headers() }),
    fetch(`${API}/bots/${botId}/report-score`, { headers: headers() }),
  ])
  if (rRes.ok) {
    const data = await rRes.json()
    reports.value = data
    await nextTick()
    renderCharts(data.slice().reverse())
  }
  if (sRes.ok) {
    const score = await sRes.json()
    reportScore.value = score.insufficient ? null : score
    reportScoreInsufficient.value = score.insufficient ? score.reason : null
  }
}

async function renderCharts(data) {
  if (!data.length) return
  const { createChart, LineSeries, HistogramSeries } = await import('lightweight-charts')

  const commonOpts = {
    layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
    grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
    rightPriceScale: { borderColor: '#2a2d3e' },
    timeScale: { borderColor: '#2a2d3e', timeVisible: false },
  }

  // 누적 손익 라인 차트
  if (lineChartEl.value) {
    if (lineChart) { lineChart.remove(); lineChart = null }
    lineChart = createChart(lineChartEl.value, { ...commonOpts, height: 180 })
    const ls = lineChart.addSeries(LineSeries, {
      color: '#4f9eff',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    ls.setData(data.map(r => ({ time: r.date, value: r.total_pnl })))
    lineChart.timeScale().fitContent()
  }

  // 일일 손익 히스토그램 차트
  if (barChartEl.value) {
    if (barChart) { barChart.remove(); barChart = null }
    barChart = createChart(barChartEl.value, { ...commonOpts, height: 180 })
    const hs = barChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    hs.setData(data.map(r => ({
      time: r.date,
      value: r.daily_pnl,
      color: r.daily_pnl >= 0 ? 'rgba(239,68,68,0.7)' : 'rgba(16,185,129,0.7)',
    })))
    barChart.timeScale().fitContent()
  }
}

async function renderExecChart(data) {
  if (!data.length) return
  // 종목 목록 추출
  const tickers = [...new Set(data.map(e => e.ticker))]
  execTickers.value = tickers
  if (!selectedExecTicker.value || !tickers.includes(selectedExecTicker.value)) {
    selectedExecTicker.value = tickers[0]
  }
  await nextTick()
  await renderExecChartForTicker(data, selectedExecTicker.value)
}

async function onExecTickerChange() {
  await renderExecChartForTicker(executions.value, selectedExecTicker.value)
}

async function renderExecChartForTicker(data, ticker) {
  if (!execChartEl.value) return
  const { createChart, CandlestickSeries, LineSeries } = await import('lightweight-charts')

  if (execChart) { execChart.remove(); execChart = null }

  const tickerExecs = data.filter(e => e.ticker === ticker)
  if (!tickerExecs.length) return

  // 날짜 범위 계산
  const dates = tickerExecs.map(e => e.executed_at.slice(0, 10)).sort()
  const startDate = dates[0]
  const endDate = dates[dates.length - 1]

  // 주가 데이터 조회
  execChartLoading.value = true
  let priceData = []
  try {
    const res = await fetch(
      `${API}/market/stocks/${ticker}/prices?start_date=${startDate}&end_date=${endDate}`,
      { headers: headers() }
    )
    if (res.ok) priceData = await res.json()
  } finally {
    execChartLoading.value = false
  }

  execChart = createChart(execChartEl.value, {
    layout: { background: { color: '#1a1d27' }, textColor: '#9ca3af' },
    grid: { vertLines: { color: '#2a2d3e' }, horzLines: { color: '#2a2d3e' } },
    rightPriceScale: { borderColor: '#2a2d3e' },
    timeScale: { borderColor: '#2a2d3e', timeVisible: false },
    crosshair: { mode: 1 },
    height: 260,
  })

  // 마커 생성 (날짜 기준, 중복은 첫 번째만 text 표시)
  const sorted = [...tickerExecs].sort((a, b) => new Date(a.executed_at) - new Date(b.executed_at))
  const markers = sorted.map(e => {
    const isBuy = e.execution_type === 'BUY'
    const isProfit = e.profit_loss != null && e.profit_loss >= 0
    const pctText = e.profit_loss_pct != null
      ? (e.profit_loss_pct >= 0 ? '+' : '') + e.profit_loss_pct.toFixed(1) + '%'
      : ''
    return {
      time: e.executed_at.slice(0, 10),
      position: isBuy ? 'belowBar' : 'aboveBar',
      color: isBuy ? '#60a5fa' : (isProfit ? '#ef4444' : '#10b981'),
      shape: isBuy ? 'arrowUp' : 'arrowDown',
      text: isBuy ? '매수' : `매도 ${pctText}`,
      size: 1,
    }
  })

  if (priceData.length) {
    // 캔들스틱 차트
    const cs = execChart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#10b981',
      borderUpColor: '#ef4444',
      borderDownColor: '#10b981',
      wickUpColor: '#ef4444',
      wickDownColor: '#10b981',
    })
    cs.setData(priceData.map(p => ({
      time: String(p.date),
      open: p.open_price ?? p.close_price,
      high: p.high_price ?? p.close_price,
      low: p.low_price ?? p.close_price,
      close: p.close_price,
    })))
    execChart.createSeriesMarkers(cs, markers)
  } else {
    // 가격 데이터 없음 — 체결가 기준 라인 차트 대체
    const lineData = sorted.map(e => ({
      time: e.executed_at.slice(0, 10),
      value: e.price,
    }))
    // 날짜 중복 제거 (같은 날 여러 체결 시 마지막 값)
    const dedupedLine = Object.values(
      Object.fromEntries(lineData.map(d => [d.time, d]))
    ).sort((a, b) => a.time.localeCompare(b.time))

    const ls = execChart.addSeries(LineSeries, {
      color: '#4f9eff',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    ls.setData(dedupedLine)
    execChart.createSeriesMarkers(ls, markers)
  }

  execChart.timeScale().fitContent()
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'positions') await fetchPositions()
  else if (tab === 'orders') await fetchOrders()
  else if (tab === 'executions') await fetchExecutions()
  else if (tab === 'reports') await fetchReports()
  // canvas는 BotCanvas 컴포넌트가 자체 fetch
}

async function startBot() {
  await fetch(`${API}/bots/${botId}/start`, { method: 'POST', headers: headers() })
  fetchBot()
  fetchPerf()
}

async function stopBot() {
  await fetch(`${API}/bots/${botId}/stop`, { method: 'POST', headers: headers() })
  fetchBot()
}

function statusClass(s) {
  if (s === 'RUNNING') return 'badge-green'
  if (s === 'ERROR') return 'badge-red'
  return 'badge-gray'
}

function tabLabel(tab) {
  return {
    canvas: '캔버스',
    positions: '보유 포지션',
    orders: '주문 내역',
    executions: '체결 내역',
    reports: '일별 보고서',
  }[tab]
}

function fmtMoney(v) {
  if (!v) return '0원'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtPrice(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('ko-KR') + '원'
}

function fmtPnl(v) {
  if (v == null) return '-'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toLocaleString('ko-KR') + '원'
}

function fmtTime(t) {
  if (!t) return '-'
  return String(t).slice(0, 5)
}

function fmtDatetime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function pnlClass(v) {
  const n = Number(v)
  if (n > 0) return 'profit'
  if (n < 0) return 'loss'
  return ''
}

function gradeClass(g) {
  return { S: 'grade-s', A: 'grade-a', B: 'grade-b', C: 'grade-c', D: 'grade-d', F: 'grade-f' }[g] || ''
}

function barColor(v) {
  if (v >= 75) return 'bar-good'
  if (v >= 50) return 'bar-mid'
  return 'bar-bad'
}

onMounted(async () => {
  await fetchBot()
  await Promise.all([fetchPositions(), fetchPerf(), fetchStrategies(), fetchStockNames()])
})
</script>

<style scoped>
.bot-detail { max-width: 1200px; }

.loading { text-align: center; color: #6b7280; padding: 80px 0; }

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.back-btn {
  background: none;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #9ca3af;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.back-btn:hover { color: #e5e7eb; border-color: #4b5563; }

h1 { margin: 0; font-size: 20px; font-weight: 700; color: #e5e7eb; }

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green { background: rgba(16,185,129,.2); color: #10b981; }
.badge-red { background: rgba(239,68,68,.2); color: #ef4444; }
.badge-gray { background: rgba(107,114,128,.2); color: #9ca3af; }

.header-actions { display: flex; gap: 8px; }

.btn-start, .btn-stop {
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 14px;
  border: none;
  cursor: pointer;
  font-weight: 600;
}
.btn-start { background: rgba(16,185,129,.2); color: #10b981; }
.btn-start:hover { background: rgba(16,185,129,.3); }
.btn-stop { background: rgba(239,68,68,.2); color: #ef4444; }
.btn-stop:hover { background: rgba(239,68,68,.3); }

/* 설정 요약 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.s-label { font-size: 11px; color: #6b7280; }
.s-value { font-size: 14px; color: #e5e7eb; font-weight: 600; }

.summary-card.s-total {
  background: rgba(79, 158, 255, 0.08);
  border-color: rgba(79, 158, 255, 0.35);
}
.summary-card.s-total .s-value { color: #4f9eff; }

/* 종합 성과 카드 */
.perf-section {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.perf-card {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.perf-pos { border-color: rgba(239,68,68,.3); }
.perf-neg { border-color: rgba(16,185,129,.3); }

.p-label { font-size: 11px; color: #6b7280; }
.p-main { font-size: 18px; font-weight: 700; color: #e5e7eb; }
.p-sub { font-size: 11px; color: #6b7280; }

.val-good { color: #ef4444; }
.val-bad  { color: #60a5fa; }

/* 종목 태그 */
.tickers-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding: 12px 16px;
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
}

.tickers-label { font-size: 12px; color: #6b7280; white-space: nowrap; }
.ticker-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.ticker-tag {
  background: #2a2d3e;
  color: #9ca3af;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.no-tickers { font-size: 12px; color: #4b5563; }

/* 탭 */
.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  border-bottom: 1px solid #2a2d3e;
}

.tab-btn {
  padding: 10px 20px;
  background: none;
  border: none;
  color: #6b7280;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab-btn:hover { color: #e5e7eb; }
.tab-btn.active { color: #4f9eff; border-bottom-color: #4f9eff; }

.empty-tab {
  text-align: center;
  color: #4b5563;
  padding: 60px 0;
  font-size: 14px;
}

/* 차트 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.chart-container {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 8px;
  padding: 16px;
}

.chart-title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}

.chart-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.exec-chart-legend {
  display: flex;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #9ca3af;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.ticker-select {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 12px;
  padding: 3px 8px;
  cursor: pointer;
}

.chart-ticker-label {
  font-size: 12px;
  color: #e5e7eb;
  font-weight: 600;
}

.chart-loading {
  text-align: center;
  color: #6b7280;
  font-size: 12px;
  padding: 8px 0;
}

/* 테이블 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th {
  padding: 10px 12px;
  text-align: right;
  color: #6b7280;
  font-weight: 500;
  border-bottom: 1px solid #2a2d3e;
  white-space: nowrap;
}
.data-table th:first-child { text-align: left; }

.data-table td {
  padding: 10px 12px;
  text-align: right;
  color: #e5e7eb;
  border-bottom: 1px solid #1f2235;
}
.data-table td:first-child { text-align: left; }

.data-table tbody tr:hover { background: #1f2235; }

.ticker-cell { font-weight: 600; color: #4f9eff; }
.time-cell { color: #9ca3af; font-size: 12px; }
.buy-cell { color: #ef4444; font-weight: 600; }
.sell-cell { color: #10b981; font-weight: 600; }
.fee-cell { color: #6b7280; font-size: 12px; }
.mdd-cell { color: #ef4444; }

.profit { color: #ef4444; }
.loss { color: #60a5fa; }

.exec-profit { background: rgba(239,68,68,.06); }
.exec-loss   { background: rgba(96,165,250,.06); }
.data-table tbody tr.exec-profit:hover { background: rgba(239,68,68,.12); }
.data-table tbody tr.exec-loss:hover   { background: rgba(96,165,250,.12); }

/* 수정 버튼 */
.btn-edit {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  border: 1px solid #2a2d3e;
  background: none;
  color: #9ca3af;
  cursor: pointer;
  font-weight: 500;
}
.btn-edit:hover { border-color: #4b5563; color: #e5e7eb; }

/* 모달 */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}

.modal {
  background: #1a1d27;
  border: 1px solid #2a2d3e;
  border-radius: 12px;
  width: 560px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #2a2d3e;
}
.modal-header h2 { margin: 0; font-size: 17px; color: #e5e7eb; }

.close-btn { background: none; border: none; color: #6b7280; font-size: 18px; cursor: pointer; }

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid #2a2d3e;
}

.form-group { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.form-group label { font-size: 12px; color: #9ca3af; }
.form-group input,
.form-group select {
  background: #0f1117;
  border: 1px solid #2a2d3e;
  border-radius: 6px;
  color: #e5e7eb;
  padding: 8px 10px;
  font-size: 14px;
}
.form-group input:focus,
.form-group select:focus { outline: none; border-color: #4f9eff; }

.form-row { display: flex; gap: 12px; }

/* 봇 타입 탭 */
.bot-type-tabs { display: flex; border-bottom: 1px solid #2a2d3e; }
.type-tab {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 12px 16px; background: none; border: none;
  border-bottom: 2px solid transparent; color: #6b7280;
  font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s; margin-bottom: -1px;
}
.type-tab:hover { color: #9ca3af; background: rgba(255,255,255,.03); }
.type-tab.active { color: #e5e7eb; border-bottom-color: #4f9eff; }
.type-tab.active:last-child { border-bottom-color: #fbbf24; color: #fbbf24; }
.tab-desc { font-size: 11px; font-weight: 400; color: #4b5563; }
.type-tab.active .tab-desc { color: #6b7280; }

/* 단타 섹션 */
.scalping-section {
  background: rgba(251,191,36,.05);
  border: 1px solid rgba(251,191,36,.2);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.section-title { font-size: 12px; font-weight: 700; color: #fbbf24; letter-spacing: 0.05em; }
.toggle-row { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.toggle-switch { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; inset: 0;
  background: #2a2d3e; border-radius: 999px; cursor: pointer; transition: background 0.2s;
}
.toggle-slider::before {
  content: ''; position: absolute;
  width: 14px; height: 14px; left: 3px; top: 3px;
  background: #6b7280; border-radius: 50%; transition: transform 0.2s, background 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: rgba(251,191,36,.2); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(16px); background: #fbbf24; }
.time-inline {
  background: #0f1117; border: 1px solid #2a2d3e; border-radius: 6px;
  color: #e5e7eb; padding: 5px 8px; font-size: 13px; width: 100px;
}
.time-inline:focus { outline: none; border-color: #fbbf24; }
.toggle-off-label { font-size: 12px; color: #4b5563; }
.label-hint { font-size: 10px; color: #4b5563; font-weight: 400; }

.btn-primary {
  background: #4f9eff; color: #fff; border: none;
  border-radius: 6px; padding: 8px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-primary:hover { background: #3b8ae8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: none; border: 1px solid #2a2d3e;
  border-radius: 6px; color: #9ca3af; padding: 8px 18px; font-size: 14px; cursor: pointer;
}
.btn-secondary:hover { border-color: #4b5563; color: #e5e7eb; }

.error-msg { color: #ef4444; font-size: 13px; }

/* ── 종합 점수 섹션 ─────────────────────────────────── */
.score-section {
  background: #1a1d27; border: 1px solid #2a2d3e; border-radius: 14px;
  padding: 24px; display: flex; flex-direction: column; gap: 20px;
}

/* 원형 점수 + 등급 */
.score-main {
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
}
.score-circle {
  width: 88px; height: 88px; border-radius: 50%;
  border: 4px solid #2a2d3e;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.score-num { font-size: 26px; font-weight: 800; line-height: 1; }
.score-denom { font-size: 11px; color: #6b7280; }
.score-grade-badge {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800; flex-shrink: 0;
}
.score-summary { flex: 1; font-size: 13px; color: #d1d5db; line-height: 1.6; min-width: 200px; }

.grade-s { border-color: #a78bfa; color: #a78bfa; background: rgba(167,139,250,.12); }
.grade-a { border-color: #f59e0b; color: #f59e0b; background: rgba(245,158,11,.12); }
.grade-b { border-color: #4f9eff; color: #4f9eff; background: rgba(79,158,255,.12); }
.grade-c { border-color: #10b981; color: #10b981; background: rgba(16,185,129,.12); }
.grade-d { border-color: #9ca3af; color: #9ca3af; background: rgba(156,163,175,.12); }
.grade-f { border-color: #ef4444; color: #ef4444; background: rgba(239,68,68,.12); }

/* 카테고리 바 */
.score-categories { display: flex; flex-direction: column; gap: 8px; }
.score-cat-row { display: flex; align-items: center; gap: 10px; }
.cat-label { width: 72px; font-size: 11px; color: #9ca3af; flex-shrink: 0; text-align: right; }
.cat-bar-wrap { flex: 1; height: 8px; background: #2a2d3e; border-radius: 4px; overflow: hidden; }
.cat-bar { height: 100%; border-radius: 4px; transition: width .4s ease; }
.cat-val { width: 34px; font-size: 12px; font-weight: 600; text-align: right; flex-shrink: 0; }
.bar-good { background: #10b981; color: #10b981; }
.bar-mid  { background: #f59e0b; color: #f59e0b; }
.bar-bad  { background: #ef4444; color: #ef4444; }

/* 인사이트 */
.score-insights { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.insight-block { background: #111318; border-radius: 10px; padding: 14px; }
.insight-title { font-size: 12px; font-weight: 600; color: #e5e7eb; margin-bottom: 8px; }
.insight-block ul { margin: 0; padding-left: 16px; }
.insight-block li { font-size: 11px; color: #9ca3af; line-height: 1.6; }
.insight-strength .insight-title { color: #10b981; }
.insight-weakness .insight-title { color: #f59e0b; }
.insight-rec .insight-title { color: #4f9eff; }

/* 보조 지표 메타 */
.meta-row {
  display: flex; flex-wrap: wrap; gap: 10px;
  padding: 14px; background: #111318; border-radius: 10px;
}
.meta-item { display: flex; flex-direction: column; gap: 3px; min-width: 90px; }
.mi-label { font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }
.mi-val { font-size: 13px; font-weight: 600; color: #e5e7eb; }
.insufficient-notice {
  background: #1e2030;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 16px 20px;
  color: #9ca3af;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 16px;
}
.insufficient-reason { color: #6b7280; font-size: 12px; }
</style>
