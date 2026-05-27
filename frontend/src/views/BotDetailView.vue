<template>
  <div v-if="bot" class="bot-detail">
    <!-- 헤더 -->
    <header class="detail-header">
      <div class="header-left">
        <button class="back-btn" type="button" @click="router.push('/bots')">
          <span aria-hidden="true">←</span>
          <span>목록</span>
        </button>
        <h1 class="bot-title">{{ bot.name }}</h1>
        <span class="badge" :class="statusClass(bot.status)">
          <span class="badge-dot"></span>
          {{ bot.status }}
        </span>
      </div>
      <div class="header-actions">
        <button
          v-if="bot.status !== 'RUNNING'"
          class="btn-ghost"
          type="button"
          @click="openEdit"
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
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
          <span>수정</span>
        </button>
        <button
          v-if="bot.status !== 'RUNNING'"
          class="btn-start"
          type="button"
          @click="startBot"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <polygon points="6 4 20 12 6 20 6 4" />
          </svg>
          <span>START</span>
        </button>
        <button
          v-if="bot.status === 'RUNNING'"
          class="btn-stop"
          type="button"
          @click="stopBot"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="1.5" />
          </svg>
          <span>STOP</span>
        </button>
      </div>
    </header>

    <!-- 설정 요약 카드 -->
    <section class="summary-grid">
      <div class="summary-card">
        <span class="s-label">초기 자금</span>
        <span class="s-value mono">{{ fmtMoney(bot.initial_cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">현재 캐시</span>
        <span class="s-value mono">{{ fmtMoney(bot.cash) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">보유 평가</span>
        <span class="s-value mono">{{ fmtMoney(bot.holdings_value || 0) }}</span>
      </div>
      <div class="summary-card s-total">
        <span class="s-label">총자산</span>
        <span class="s-value mono accent">{{ fmtMoney(bot.total_assets || 0) }}</span>
      </div>
      <div class="summary-card">
        <span class="s-label">총수익률</span>
        <span class="s-value mono" :class="pnlClass(totalReturnPct)">
          {{ totalReturnPct > 0 ? '+' : '' }}{{ totalReturnPct.toFixed(2) }}%
        </span>
      </div>
      <div class="summary-card">
        <span class="s-label">손절 / 익절</span>
        <span class="s-value mono">
          {{ bot.stop_loss_pct }}% / {{ bot.take_profit_pct }}%
        </span>
      </div>
      <div class="summary-card">
        <span class="s-label">최대 낙폭</span>
        <span class="s-value mono">{{ bot.max_drawdown_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">포지션 크기</span>
        <span class="s-value mono">{{ bot.position_size_pct }}%</span>
      </div>
      <div class="summary-card">
        <span class="s-label">거래 시간</span>
        <span class="s-value mono">
          {{ fmtTime(bot.trading_start_time) }} – {{ fmtTime(bot.trading_end_time) }}
        </span>
      </div>
      <template v-if="bot.bot_type === 'scalping'">
        <div class="summary-card">
          <span class="s-label">트레일링 스탑</span>
          <span class="s-value mono">
            {{ bot.trailing_stop_pct != null ? bot.trailing_stop_pct + '%' : 'OFF' }}
          </span>
        </div>
        <div class="summary-card">
          <span class="s-label">연속 확인 봉</span>
          <span class="s-value mono">{{ bot.confirm_bars ?? 1 }}봉</span>
        </div>
      </template>
    </section>

    <!-- 종합 성과 카드 -->
    <section v-if="perf" class="perf-section">
      <div class="perf-card" :class="perf.total_pnl >= 0 ? 'perf-pos' : 'perf-neg'">
        <span class="p-label">누적 손익</span>
        <span class="p-main mono">{{ fmtPnl(perf.total_pnl) }}</span>
        <span class="p-sub mono" :class="pnlClass(perf.total_return_pct)">
          {{ perf.total_return_pct >= 0 ? '+' : '' }}{{ perf.total_return_pct.toFixed(2) }}%
        </span>
      </div>
      <div class="perf-card">
        <span class="p-label">승률</span>
        <span class="p-main mono">{{ perf.win_rate.toFixed(1) }}%</span>
        <span class="p-sub mono">
          {{ perf.winning_trades }}승 {{ perf.losing_trades }}패 · {{ perf.total_trades }}건
        </span>
      </div>
      <div class="perf-card">
        <span class="p-label">손익비</span>
        <span class="p-main mono" :class="perf.profit_factor >= 1 ? 'profit' : 'loss'">
          {{ perf.profit_factor > 0 ? perf.profit_factor.toFixed(2) : '-' }}
        </span>
        <span class="p-sub mono">평균수익 {{ fmtPnl(perf.avg_win) }}</span>
      </div>
      <div class="perf-card">
        <span class="p-label">샤프 비율</span>
        <span
          class="p-main mono"
          :class="perf.sharpe_ratio >= 1 ? 'profit' : perf.sharpe_ratio >= 0 ? '' : 'loss'"
        >
          {{ perf.sharpe_ratio !== 0 ? perf.sharpe_ratio.toFixed(2) : '-' }}
        </span>
        <span class="p-sub">위험 대비 수익</span>
      </div>
      <div class="perf-card">
        <span class="p-label">최대 낙폭</span>
        <span class="p-main mono loss">
          {{ perf.max_drawdown > 0 ? '-' + perf.max_drawdown.toFixed(2) + '%' : '-' }}
        </span>
        <span class="p-sub">최고점 대비</span>
      </div>
      <div class="perf-card">
        <span class="p-label">총 수수료+세금</span>
        <span class="p-main mono">{{ fmtMoney(perf.total_fee) }}</span>
        <span class="p-sub mono">최대손실 {{ fmtPnl(perf.worst_trade) }}</span>
      </div>
    </section>

    <!-- 종목 태그 -->
    <section class="tickers-row">
      <span class="tickers-label">TICKERS · 대상 종목</span>
      <div class="ticker-tags">
        <StockLink v-for="t in bot.tickers || []" :key="t" :ticker="t" class="ticker-tag">{{ t }}</StockLink>
        <span v-if="!(bot.tickers || []).length" class="no-tickers">종목 없음</span>
      </div>
    </section>

    <!-- 탭 -->
    <nav class="tabs" role="tablist">
      <button
        v-for="tab in tabKeys"
        :key="tab"
        class="tab-btn"
        type="button"
        :class="{ active: activeTab === tab }"
        role="tab"
        :aria-selected="activeTab === tab"
        @click="switchTab(tab)"
      >{{ tabLabel(tab) }}</button>
    </nav>

    <!-- 캔버스 탭 -->
    <div v-if="activeTab === 'canvas'" class="tab-pane canvas-pane">
      <div class="canvas-main">
        <BotCanvas :bot-id="Number(botId)" />
      </div>
      <aside class="canvas-side">
        <header class="canvas-side-head">
          <span class="cs-title">보유 종목</span>
          <span class="cs-count">{{ positions.length }}건</span>
        </header>
        <div v-if="positions.length === 0" class="cs-empty">
          보유 종목이 없습니다
        </div>
        <div v-else class="cs-list">
          <div v-for="p in positions" :key="p.id" class="cs-row">
            <div class="cs-name">
              <span class="cs-company">{{ p.company_name || p.ticker }}</span>
              <StockLink :ticker="p.ticker" class="cs-ticker" />
            </div>
            <div class="cs-mid mono">
              <span class="cs-qty">{{ p.quantity.toLocaleString() }}주</span>
              <span class="cs-mv">{{ fmtMoney(p.market_value) }}</span>
            </div>
            <div class="cs-pnl mono" :class="pnlClass(p.unrealized_pnl)">
              <span>{{ fmtPnl(p.unrealized_pnl) }}</span>
              <span class="cs-pct">
                {{ (p.unrealized_pct || 0) >= 0 ? '+' : '' }}{{ (p.unrealized_pct || 0).toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 포지션 탭 -->
    <div v-if="activeTab === 'positions'" class="tab-pane">
      <div v-if="positions.length === 0" class="empty-tab">보유 포지션이 없습니다</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>종목</th>
              <th class="th-num">수량</th>
              <th class="th-num">평균단가</th>
              <th class="th-num">현재가</th>
              <th class="th-num">전일대비</th>
              <th class="th-num">매입금액</th>
              <th class="th-num">평가금액</th>
              <th class="th-num">평가손익</th>
              <th class="th-num">수익률</th>
              <th class="th-num">비중</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pos in positions" :key="pos.id">
              <td class="ticker-cell">
                <div class="ticker-stack">
                  <span class="ticker-name">{{ pos.company_name || pos.ticker }}</span>
                  <StockLink :ticker="pos.ticker" class="ticker-code" />
                </div>
              </td>
              <td class="td-num">{{ pos.quantity.toLocaleString() }}</td>
              <td class="td-num">{{ fmtPrice(pos.avg_price) }}</td>
              <td class="td-num">{{ fmtPrice(pos.current_price) }}</td>
              <td class="td-num" :class="pnlClass(pos.day_change)">
                <template v-if="pos.day_change != null">
                  <div>{{ pos.day_change > 0 ? '+' : '' }}{{ fmtPrice(pos.day_change) }}</div>
                  <div class="day-change-pct">
                    {{ pos.day_change_pct > 0 ? '+' : '' }}{{ pos.day_change_pct.toFixed(2) }}%
                  </div>
                </template>
                <template v-else>-</template>
              </td>
              <td class="td-num">{{ fmtPrice(pos.buy_amount) }}</td>
              <td class="td-num">{{ fmtPrice(pos.market_value) }}</td>
              <td class="td-num" :class="pnlClass(pos.unrealized_pnl)">
                {{ fmtPnl(pos.unrealized_pnl) }}
              </td>
              <td class="td-num" :class="pnlClass(pos.unrealized_pct)">
                {{ pos.unrealized_pct > 0 ? '+' : '' }}{{ pos.unrealized_pct.toFixed(2) }}%
              </td>
              <td class="td-num weight-cell">
                <div class="weight-bar-wrap">
                  <div class="weight-bar" :style="{ width: Math.min(pos.weight_pct, 100) + '%' }"></div>
                </div>
                <span class="weight-pct-text">{{ pos.weight_pct.toFixed(1) }}%</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 주문 탭 -->
    <div v-if="activeTab === 'orders'" class="tab-pane">
      <div v-if="orders.length === 0" class="empty-tab">주문 내역이 없습니다</div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>시각</th>
              <th>종목</th>
              <th>구분</th>
              <th class="th-num">수량</th>
              <th class="th-num">체결가</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id">
              <td class="time-cell">{{ fmtDatetime(o.created_at) }}</td>
              <td class="ticker-cell"><StockLink :ticker="o.ticker" /></td>
              <td>
                <span class="type-badge" :class="o.order_type === 'BUY' ? 'type-buy' : 'type-sell'">
                  {{ o.order_type }}
                </span>
              </td>
              <td class="td-num">{{ o.quantity.toLocaleString() }}</td>
              <td class="td-num">{{ fmtPrice(o.price) }}</td>
              <td>
                <span class="status-pill">{{ o.status }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 체결 탭 -->
    <div v-if="activeTab === 'executions'" class="tab-pane">
      <div v-if="executions.length === 0" class="empty-tab">체결 내역이 없습니다</div>
      <template v-else>
        <div class="chart-block">
          <div class="chart-head">
            <div class="chart-head-left">
              <span class="chart-label">CANDLE · 체결 포인트</span>
              <select
                v-if="execTickers.length > 1"
                v-model="selectedExecTicker"
                class="ticker-select"
                @change="onExecTickerChange"
              >
                <option v-for="t in execTickers" :key="t" :value="t">
                  {{ tickerName(t) }}
                </option>
              </select>
              <span v-else class="chart-ticker-label">{{ tickerName(selectedExecTicker) }}</span>
            </div>
            <div class="exec-chart-legend">
              <span class="legend-item">
                <span class="legend-dot" style="background: #60a5fa"></span>
                매수
              </span>
              <span class="legend-item">
                <span class="legend-dot" style="background: #ef4444"></span>
                매도 · 수익
              </span>
              <span class="legend-item">
                <span class="legend-dot" style="background: #10b981"></span>
                매도 · 손실
              </span>
            </div>
          </div>
          <div v-if="execChartLoading" class="chart-loading">차트 불러오는 중...</div>
          <div ref="execChartEl" class="exec-chart"></div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>체결 시각</th>
                <th>종목</th>
                <th>구분</th>
                <th class="th-num">수량</th>
                <th class="th-num">체결가</th>
                <th class="th-num">손익</th>
                <th class="th-num">수익률</th>
                <th class="th-num">수수료+세금</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="e in executions"
                :key="e.id"
                :class="
                  e.profit_loss != null && e.profit_loss > 0
                    ? 'exec-profit'
                    : e.profit_loss != null && e.profit_loss < 0
                      ? 'exec-loss'
                      : ''
                "
              >
                <td class="time-cell">{{ fmtDatetime(e.executed_at) }}</td>
                <td class="ticker-cell"><StockLink :ticker="e.ticker">{{ tickerName(e.ticker) }}</StockLink></td>
                <td>
                  <span
                    class="type-badge"
                    :class="e.execution_type === 'BUY' ? 'type-buy' : 'type-sell'"
                  >{{ e.execution_type }}</span>
                </td>
                <td class="td-num">{{ e.quantity.toLocaleString() }}</td>
                <td class="td-num">{{ fmtPrice(e.price) }}</td>
                <td class="td-num" :class="pnlClass(e.profit_loss)">
                  {{ e.profit_loss != null ? fmtPnl(e.profit_loss) : '-' }}
                </td>
                <td class="td-num" :class="pnlClass(e.profit_loss_pct)">
                  {{
                    e.profit_loss_pct != null
                      ? (e.profit_loss_pct >= 0 ? '+' : '') + e.profit_loss_pct.toFixed(2) + '%'
                      : '-'
                  }}
                </td>
                <td class="td-num fee-cell">
                  {{ fmtPrice((e.fee || 0) + (e.tax || 0)) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <!-- 보고서 탭 -->
    <div v-if="activeTab === 'reports'" class="tab-pane">
      <div
        v-if="reports.length === 0 && !reportScore && !reportScoreInsufficient"
        class="empty-tab"
      >일별 보고서가 없습니다</div>

      <div v-else>
        <!-- 데이터 부족 안내 -->
        <div v-if="reportScoreInsufficient" class="insufficient-notice">
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
          <div class="insufficient-text">
            <strong>성과 평가 데이터 부족</strong>
            <span class="insufficient-reason">{{ reportScoreInsufficient }}</span>
          </div>
        </div>

        <!-- ① 종합 점수 카드 -->
        <div v-if="reportScore" class="score-section">
          <div class="score-main">
            <div class="score-circle" :class="gradeClass(reportScore.grade)">
              <div class="score-num">{{ reportScore.total_score }}</div>
              <div class="score-denom">/ 100</div>
            </div>
            <div class="score-grade-badge" :class="gradeClass(reportScore.grade)">
              {{ reportScore.grade }}
            </div>
            <div class="score-summary">{{ reportScore.summary }}</div>
          </div>

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
              <div class="cat-val mono" :class="barColor(val)">{{ val }}</div>
            </div>
          </div>

          <div class="score-insights">
            <div class="insight-block insight-strength">
              <div class="insight-title">
                <span class="insight-icon">+</span>
                강점
              </div>
              <ul>
                <li v-for="s in reportScore.strengths" :key="s">{{ s }}</li>
              </ul>
            </div>
            <div class="insight-block insight-weakness">
              <div class="insight-title">
                <span class="insight-icon">!</span>
                약점
              </div>
              <ul>
                <li v-for="w in reportScore.weaknesses" :key="w">{{ w }}</li>
              </ul>
            </div>
            <div class="insight-block insight-rec">
              <div class="insight-title">
                <span class="insight-icon">→</span>
                권장사항
              </div>
              <ul>
                <li v-for="r in reportScore.recommendations" :key="r">{{ r }}</li>
              </ul>
            </div>
          </div>

          <div class="meta-row">
            <div class="meta-item">
              <span class="mi-label">수익률</span>
              <span
                class="mi-val mono"
                :class="reportScore.meta.total_return_pct >= 0 ? 'profit' : 'loss'"
              >
                {{ reportScore.meta.total_return_pct >= 0 ? '+' : ''
                }}{{ reportScore.meta.total_return_pct }}%
              </span>
            </div>
            <div class="meta-item">
              <span class="mi-label">샤프</span>
              <span class="mi-val mono">{{ reportScore.meta.sharpe_ratio }}</span>
            </div>
            <div class="meta-item">
              <span class="mi-label">최대 낙폭</span>
              <span class="mi-val mono loss">-{{ reportScore.meta.max_drawdown }}%</span>
            </div>
            <div class="meta-item">
              <span class="mi-label">승률</span>
              <span class="mi-val mono">{{ reportScore.meta.win_rate }}%</span>
            </div>
            <div class="meta-item">
              <span class="mi-label">손익비</span>
              <span class="mi-val mono">{{ reportScore.meta.profit_factor }}</span>
            </div>
            <div class="meta-item">
              <span class="mi-label">수익일 비율</span>
              <span class="mi-val mono">{{ reportScore.meta.winning_days_pct }}%</span>
            </div>
            <div class="meta-item">
              <span class="mi-label">최대연속손실</span>
              <span
                class="mi-val mono"
                :class="reportScore.meta.max_consecutive_losses > 5 ? 'loss' : ''"
              >{{ reportScore.meta.max_consecutive_losses }}일</span>
            </div>
          </div>
        </div>

        <!-- ② 차트 영역 -->
        <div v-if="reports.length" class="charts-row">
          <div class="chart-block">
            <div class="chart-head">
              <span class="chart-label">누적 손익</span>
            </div>
            <div ref="lineChartEl" class="report-chart"></div>
          </div>
          <div class="chart-block">
            <div class="chart-head">
              <span class="chart-label">일일 손익</span>
            </div>
            <div ref="barChartEl" class="report-chart"></div>
          </div>
        </div>

        <!-- ③ 보고서 테이블 -->
        <div v-if="reports.length" class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th class="th-num">총 자산</th>
                <th class="th-num">캐시</th>
                <th class="th-num">보유 평가</th>
                <th class="th-num">일일 손익</th>
                <th class="th-num">누적 손익</th>
                <th class="th-num">승률</th>
                <th class="th-num">거래수</th>
                <th class="th-num">MDD</th>
                <th class="th-num">샤프</th>
                <th class="th-num">손익비</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in reports" :key="r.id">
                <td class="mono">{{ r.date }}</td>
                <td class="td-num">{{ fmtPrice(r.total_assets) }}</td>
                <td class="td-num">{{ fmtPrice(r.cash) }}</td>
                <td class="td-num">{{ fmtPrice(r.holdings_value) }}</td>
                <td class="td-num" :class="pnlClass(r.daily_pnl)">
                  {{ fmtPnl(r.daily_pnl) }}
                </td>
                <td class="td-num" :class="pnlClass(r.total_pnl)">
                  {{ fmtPnl(r.total_pnl) }}
                </td>
                <td class="td-num">{{ r.win_rate.toFixed(1) }}%</td>
                <td class="td-num">{{ r.total_trades }}</td>
                <td class="td-num loss">
                  {{ r.max_drawdown > 0 ? '-' + r.max_drawdown.toFixed(2) + '%' : '-' }}
                </td>
                <td
                  class="td-num"
                  :class="r.sharpe_ratio >= 1 ? 'profit' : r.sharpe_ratio < 0 ? 'loss' : ''"
                >
                  {{ r.sharpe_ratio !== 0 ? r.sharpe_ratio.toFixed(2) : '-' }}
                </td>
                <td
                  class="td-num"
                  :class="r.profit_factor >= 1 ? 'profit' : r.profit_factor > 0 ? 'loss' : ''"
                >
                  {{ r.profit_factor > 0 ? r.profit_factor.toFixed(2) : '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 수정 모달 -->
    <Teleport to="body">
      <div v-if="showEdit" class="modal-overlay" @click.self="closeEdit">
        <div class="modal" role="dialog" aria-modal="true">
          <div class="modal-header">
            <div class="modal-head-text">
              <span class="modal-eyebrow">EDIT · 봇 설정</span>
              <h2 class="modal-title">{{ bot.name }}</h2>
            </div>
            <button class="close-btn" type="button" aria-label="닫기" @click="closeEdit">
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

          <div class="bot-type-tabs" role="tablist">
            <button
              class="type-tab"
              type="button"
              :class="{ active: editForm.bot_type === 'swing' }"
              @click="setEditBotType('swing')"
            >
              <span class="type-tab-name">스윙</span>
              <span class="type-tab-desc">SWING · 일봉 · 5분 주기</span>
            </button>
            <button
              class="type-tab type-tab-scalp"
              type="button"
              :class="{ active: editForm.bot_type === 'scalping' }"
              @click="setEditBotType('scalping')"
            >
              <span class="type-tab-name">단타</span>
              <span class="type-tab-desc">SCALPING · 분봉 · 1분 주기</span>
            </button>
          </div>

          <div class="modal-body">
            <div v-if="editForm.bot_type === 'scalping'" class="scalping-section">
              <div class="section-head">
                <span class="section-tag">SCALPING</span>
                <span>단타 전용 설정</span>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="ef-interval">분봉 단위</label>
                  <select id="ef-interval" v-model.number="editForm.candle_interval">
                    <option :value="1">1분봉</option>
                    <option :value="3">3분봉</option>
                    <option :value="5">5분봉</option>
                    <option :value="10">10분봉</option>
                    <option :value="15">15분봉</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">당일 강제 청산</label>
                  <div class="toggle-row">
                    <label class="toggle-switch">
                      <input v-model="editForm.intraday_close" type="checkbox" />
                      <span class="toggle-slider"></span>
                    </label>
                    <input
                      v-if="editForm.intraday_close"
                      v-model="editForm.intraday_close_time"
                      type="time"
                      class="time-inline"
                    />
                    <span v-else class="toggle-off-label">OFF</span>
                  </div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="ef-trail">
                    트레일링 스탑
                    <span class="label-hint">고가 대비 하락 시 청산 (비우면 OFF)</span>
                  </label>
                  <input
                    id="ef-trail"
                    v-model.number="editForm.trailing_stop_pct"
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    placeholder="0.1 ~ 10"
                  />
                </div>
                <div class="form-group">
                  <label class="form-label" for="ef-conf">
                    연속 확인 봉
                    <span class="label-hint">1 = 즉시 진입</span>
                  </label>
                  <input
                    id="ef-conf"
                    v-model.number="editForm.confirm_bars"
                    type="number"
                    min="1"
                    max="5"
                    step="1"
                  />
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label" for="ef-name">봇 이름 *</label>
              <input id="ef-name" v-model="editForm.name" type="text" />
            </div>
            <div class="form-group">
              <label class="form-label" for="ef-strat">전략</label>
              <select id="ef-strat" v-model="editForm.strategy_id">
                <option :value="null">전략 없음</option>
                <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label" for="ef-tickers">종목 (쉼표 구분)</label>
              <input
                id="ef-tickers"
                v-model="editTickersInput"
                type="text"
                placeholder="005930, 000660"
              />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">손절 (%)</label>
                <input v-model.number="editForm.stop_loss_pct" type="number" min="0" step="0.5" />
              </div>
              <div class="form-group">
                <label class="form-label">익절 (%)</label>
                <input v-model.number="editForm.take_profit_pct" type="number" min="0" step="0.5" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">최대 낙폭 (%)</label>
                <input v-model.number="editForm.max_drawdown_pct" type="number" min="0" step="0.5" />
              </div>
              <div class="form-group">
                <label class="form-label">포지션 크기 (%)</label>
                <input v-model.number="editForm.position_size_pct" type="number" min="1" max="100" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">최대 동시 포지션</label>
                <input v-model.number="editForm.max_positions" type="number" min="1" max="20" />
              </div>
              <div class="form-group">
                <label class="form-label">일일 최대 거래</label>
                <input v-model.number="editForm.max_daily_trades" type="number" min="1" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">단일 주문 최대 (원)</label>
              <input v-model.number="editForm.max_order_amount" type="number" min="0" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">거래 시작 시간</label>
                <input v-model="editForm.trading_start_time" type="time" />
              </div>
              <div class="form-group">
                <label class="form-label">거래 종료 시간</label>
                <input v-model="editForm.trading_end_time" type="time" />
              </div>
            </div>
            <p v-if="editError" class="msg msg-fail">
              <span class="msg-tag">ERR</span>
              <span>{{ editError }}</span>
            </p>
          </div>

          <div class="modal-footer">
            <button class="btn-ghost" type="button" @click="closeEdit">취소</button>
            <button
              class="btn-primary"
              type="button"
              :disabled="editSubmitting"
              @click="submitEdit"
            >
              {{ editSubmitting ? 'SAVING' : '저장' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>

  <div v-else class="loading">LOADING...</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BotCanvas from '@/components/BotCanvas.vue'
import StockLink from '@/components/StockLink.vue'

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

const totalReturnPct = computed(() => {
  const b = bot.value
  if (!b) return 0
  const init = Number(b.initial_cash || 0)
  const total = Number(b.total_assets || 0)
  if (init <= 0) return 0
  return ((total - init) / init) * 100
})
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

const tabKeys = ['canvas', 'positions', 'orders', 'executions', 'reports']

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
  if (!editForm.value.name?.trim()) {
    editError.value = '봇 이름을 입력하세요'
    return
  }
  editError.value = ''
  editSubmitting.value = true
  try {
    const payload = {
      ...editForm.value,
      tickers: editTickersInput.value.split(',').map((t) => t.trim()).filter(Boolean),
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

// 차트 공통 옵션 (디자인 토큰 톤)
const CHART_BG = '#0d1118'
const CHART_TEXT = '#a1a1aa'
const CHART_GRID = 'rgba(255,255,255,0.04)'
const CHART_BORDER = 'rgba(255,255,255,0.08)'

function commonChartOpts() {
  return {
    layout: { background: { color: CHART_BG }, textColor: CHART_TEXT },
    grid: { vertLines: { color: CHART_GRID }, horzLines: { color: CHART_GRID } },
    rightPriceScale: { borderColor: CHART_BORDER },
    timeScale: { borderColor: CHART_BORDER, timeVisible: false },
  }
}

async function renderCharts(data) {
  if (!data.length) return
  const { createChart, LineSeries, HistogramSeries } = await import('lightweight-charts')

  if (lineChartEl.value) {
    if (lineChart) {
      lineChart.remove()
      lineChart = null
    }
    lineChart = createChart(lineChartEl.value, { ...commonChartOpts(), height: 180 })
    const ls = lineChart.addSeries(LineSeries, {
      color: '#60a5fa',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    ls.setData(data.map((r) => ({ time: r.date, value: r.total_pnl })))
    lineChart.timeScale().fitContent()
  }

  if (barChartEl.value) {
    if (barChart) {
      barChart.remove()
      barChart = null
    }
    barChart = createChart(barChartEl.value, { ...commonChartOpts(), height: 180 })
    const hs = barChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    hs.setData(
      data.map((r) => ({
        time: r.date,
        value: r.daily_pnl,
        color: r.daily_pnl >= 0 ? 'rgba(239,68,68,0.75)' : 'rgba(96,165,250,0.75)',
      })),
    )
    barChart.timeScale().fitContent()
  }
}

async function renderExecChart(data) {
  if (!data.length) return
  const tickers = [...new Set(data.map((e) => e.ticker))]
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

  if (execChart) {
    execChart.remove()
    execChart = null
  }

  const tickerExecs = data.filter((e) => e.ticker === ticker)
  if (!tickerExecs.length) return

  const dates = tickerExecs.map((e) => e.executed_at.slice(0, 10)).sort()
  const startDate = dates[0]
  const endDate = dates[dates.length - 1]

  execChartLoading.value = true
  let priceData = []
  try {
    const res = await fetch(
      `${API}/market/stocks/${ticker}/prices?start_date=${startDate}&end_date=${endDate}`,
      { headers: headers() },
    )
    if (res.ok) priceData = await res.json()
  } finally {
    execChartLoading.value = false
  }

  execChart = createChart(execChartEl.value, {
    ...commonChartOpts(),
    crosshair: { mode: 1 },
    height: 260,
  })

  const sorted = [...tickerExecs].sort(
    (a, b) => new Date(a.executed_at) - new Date(b.executed_at),
  )
  const markers = sorted.map((e) => {
    const isBuy = e.execution_type === 'BUY'
    const isProfit = e.profit_loss != null && e.profit_loss >= 0
    const pctText =
      e.profit_loss_pct != null
        ? (e.profit_loss_pct >= 0 ? '+' : '') + e.profit_loss_pct.toFixed(1) + '%'
        : ''
    return {
      time: e.executed_at.slice(0, 10),
      position: isBuy ? 'belowBar' : 'aboveBar',
      color: isBuy ? '#60a5fa' : isProfit ? '#ef4444' : '#10b981',
      shape: isBuy ? 'arrowUp' : 'arrowDown',
      text: isBuy ? '매수' : `매도 ${pctText}`,
      size: 1,
    }
  })

  if (priceData.length) {
    const cs = execChart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#60a5fa',
      borderUpColor: '#ef4444',
      borderDownColor: '#60a5fa',
      wickUpColor: '#ef4444',
      wickDownColor: '#60a5fa',
    })
    cs.setData(
      priceData.map((p) => ({
        time: String(p.date),
        open: p.open_price ?? p.close_price,
        high: p.high_price ?? p.close_price,
        low: p.low_price ?? p.close_price,
        close: p.close_price,
      })),
    )
    execChart.createSeriesMarkers(cs, markers)
  } else {
    const lineData = sorted.map((e) => ({
      time: e.executed_at.slice(0, 10),
      value: e.price,
    }))
    const dedupedLine = Object.values(
      Object.fromEntries(lineData.map((d) => [d.time, d])),
    ).sort((a, b) => a.time.localeCompare(b.time))

    const ls = execChart.addSeries(LineSeries, {
      color: '#60a5fa',
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
  if (tab === 'canvas') startCanvasPolling()
  else stopCanvasPolling()
  if (tab === 'positions') await fetchPositions()
  else if (tab === 'orders') await fetchOrders()
  else if (tab === 'executions') await fetchExecutions()
  else if (tab === 'reports') await fetchReports()
}

let canvasPollTimer = null

function startCanvasPolling() {
  stopCanvasPolling()
  canvasPollTimer = setInterval(() => {
    fetchPositions()
    fetchBot()
  }, 30000)
}

function stopCanvasPolling() {
  if (canvasPollTimer) {
    clearInterval(canvasPollTimer)
    canvasPollTimer = null
  }
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
  if (s === 'RUNNING') return 'badge-running'
  if (s === 'ERROR') return 'badge-error'
  return 'badge-stopped'
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
  return (
    { S: 'grade-s', A: 'grade-a', B: 'grade-b', C: 'grade-c', D: 'grade-d', F: 'grade-f' }[g] || ''
  )
}

function barColor(v) {
  if (v >= 75) return 'bar-good'
  if (v >= 50) return 'bar-mid'
  return 'bar-bad'
}

onMounted(async () => {
  await fetchBot()
  await Promise.all([fetchPositions(), fetchPerf(), fetchStrategies(), fetchStockNames()])
  if (activeTab.value === 'canvas') startCanvasPolling()
})

onUnmounted(() => {
  stopCanvasPolling()
})
</script>

<style scoped>
.bot-detail {
  max-width: var(--content-max);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.loading {
  text-align: center;
  color: var(--text-muted);
  padding: var(--space-20) 0;
  font-family: var(--font-mono);
  letter-spacing: var(--tracking-wider);
}

/* ==========================================================================
   Header
   ========================================================================== */

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-faint);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  min-width: 0;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-3);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.back-btn:hover {
  border-color: var(--accent-border);
  color: var(--accent);
}

.bot-title {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  padding: 4px var(--space-2);
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
}

.badge-running {
  background: var(--up-bg);
  color: var(--up-strong);
}
.badge-running .badge-dot {
  background: var(--up-strong);
  box-shadow: 0 0 6px var(--up-strong);
  animation: dotPulse 2s ease-in-out infinite;
}

.badge-stopped {
  background: var(--surface-2);
  color: var(--text-muted);
}
.badge-stopped .badge-dot {
  background: var(--text-muted);
}

.badge-error {
  background: var(--profit-bg);
  color: var(--profit);
}
.badge-error .badge-dot {
  background: var(--profit);
  box-shadow: 0 0 6px var(--profit);
}

@keyframes dotPulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

.header-actions {
  display: flex;
  gap: var(--space-2);
}

.btn-ghost,
.btn-start,
.btn-stop {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  border: 1px solid;
  background: transparent;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.btn-ghost svg,
.btn-start svg,
.btn-stop svg {
  width: 13px;
  height: 13px;
}

.btn-ghost {
  border-color: var(--border);
  color: var(--text-tertiary);
}
.btn-ghost:hover {
  border-color: var(--accent-border);
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-start {
  border-color: rgba(34, 197, 94, 0.3);
  color: var(--up-strong);
}
.btn-start:hover {
  background: var(--up-bg);
}

.btn-stop {
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--profit);
}
.btn-stop:hover {
  background: var(--profit-bg);
}

/* ==========================================================================
   Summary
   ========================================================================== */

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-2);
}

.summary-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-card.s-total {
  border-color: var(--accent-border);
  background: linear-gradient(135deg, var(--surface-1), rgba(245, 158, 11, 0.06));
}

.s-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.s-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 600;
}

.s-value.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--tracking-wide);
}

.s-value.accent {
  color: var(--accent);
}

/* ==========================================================================
   Perf cards
   ========================================================================== */

.perf-section {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-3);
}

.perf-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.perf-pos {
  border-color: rgba(239, 68, 68, 0.3);
}

.perf-neg {
  border-color: rgba(96, 165, 250, 0.3);
}

.p-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.p-main {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
}

.p-main.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.p-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.p-sub.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.profit {
  color: var(--profit);
}

.loss {
  color: var(--loss);
}

/* ==========================================================================
   Tickers row
   ========================================================================== */

.tickers-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.tickers-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  white-space: nowrap;
}

.ticker-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.ticker-tag {
  font-family: var(--font-mono);
  background: var(--surface-2);
  color: var(--text-tertiary);
  padding: 3px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  letter-spacing: var(--tracking-wide);
}

.no-tickers {
  font-size: var(--text-sm);
  color: var(--text-faint);
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

.tab-btn:hover {
  color: var(--text-primary);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.canvas-pane {
  flex-direction: row;
  align-items: stretch;
  gap: var(--space-4);
}

.canvas-main {
  flex: 1;
  min-width: 0;
}

.canvas-side {
  flex: 0 0 300px;
  background: var(--surface-1, var(--surface-2));
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 80vh;
  overflow-y: auto;
  align-self: flex-start;
  position: sticky;
  top: var(--space-3);
}

.canvas-side-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-faint);
}

.cs-title {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.cs-count {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cs-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-xs);
  padding: var(--space-4) 0;
}

.cs-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cs-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px var(--space-2);
  background: var(--surface-2);
  border-radius: var(--radius-xs);
  border-left: 2px solid transparent;
  transition: border-color 120ms ease;
}

.cs-row:hover {
  border-left-color: var(--accent, #60a5fa);
}

.cs-name {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
  min-width: 0;
}

.cs-company {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-ticker {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: var(--tracking-wide);
  flex-shrink: 0;
}

.cs-mid {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.cs-qty {
  color: var(--text-muted);
}

.cs-mv {
  color: var(--text-primary);
}

.cs-pnl {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.cs-pct {
  font-size: 10px;
  opacity: 0.85;
}

@media (max-width: 1100px) {
  .canvas-pane {
    flex-direction: column;
  }

  .canvas-side {
    flex: none;
    position: static;
    max-height: 320px;
  }
}

.empty-tab {
  text-align: center;
  color: var(--text-faint);
  padding: var(--space-16) 0;
  font-size: var(--text-sm);
  background: var(--surface-1);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-lg);
}

/* ==========================================================================
   Tables
   ========================================================================== */

.table-wrap {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

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
  white-space: nowrap;
}

.data-table th.th-num {
  text-align: right;
}

.data-table td {
  padding: var(--space-3) var(--space-4);
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-faint);
}

.data-table td.td-num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.data-table tbody tr:hover td {
  background: var(--surface-2);
}

.ticker-cell {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
}

.ticker-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 110px;
}

.ticker-name {
  font-family: var(--font-sans, inherit);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: normal;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

.ticker-stack .ticker-code {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
}

.day-change-pct {
  font-size: 10px;
  opacity: 0.85;
  margin-top: 1px;
}

.weight-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.weight-bar-wrap {
  flex: 0 0 56px;
  height: 6px;
  background: var(--surface-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.weight-bar {
  height: 100%;
  background: var(--accent, #60a5fa);
  opacity: 0.7;
  transition: width 200ms ease;
}

.weight-pct-text {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  min-width: 38px;
  text-align: right;
}

.time-cell {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: var(--text-xs);
  white-space: nowrap;
}

.fee-cell {
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.type-badge {
  font-family: var(--font-mono);
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wide);
}

.type-buy {
  background: var(--profit-bg);
  color: var(--profit);
}

.type-sell {
  background: var(--up-bg);
  color: var(--up-strong);
}

.status-pill {
  display: inline-block;
  font-family: var(--font-mono);
  background: var(--surface-2);
  color: var(--text-muted);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.exec-profit {
  background: rgba(239, 68, 68, 0.05);
}
.exec-loss {
  background: rgba(96, 165, 250, 0.05);
}
.data-table tbody tr.exec-profit:hover td {
  background: rgba(239, 68, 68, 0.1);
}
.data-table tbody tr.exec-loss:hover td {
  background: rgba(96, 165, 250, 0.1);
}

/* ==========================================================================
   Chart blocks
   ========================================================================== */

.chart-block {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-faint);
  background: var(--bg-elevated);
}

.chart-head-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chart-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.chart-ticker-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-primary);
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
}

.ticker-select {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  padding: 4px var(--space-2);
  cursor: pointer;
  letter-spacing: var(--tracking-wide);
}

.ticker-select:focus {
  outline: none;
  border-color: var(--accent);
}

.exec-chart-legend {
  display: flex;
  gap: var(--space-3);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-tertiary);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  display: inline-block;
}

.exec-chart {
  height: 260px;
}

.report-chart {
  height: 180px;
}

.chart-loading {
  text-align: center;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  padding: var(--space-3) 0;
  letter-spacing: var(--tracking-wide);
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

/* ==========================================================================
   Reports — Score section
   ========================================================================== */

.insufficient-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.insufficient-notice svg {
  width: 18px;
  height: 18px;
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.insufficient-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.insufficient-text strong {
  color: var(--accent);
  font-weight: 700;
}

.insufficient-reason {
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.score-section {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.score-main {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.score-circle {
  width: 96px;
  height: 96px;
  border-radius: var(--radius-full);
  border: 4px solid var(--border-strong);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.score-num {
  font-family: var(--font-mono);
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.score-denom {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
}

.score-grade-badge {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 800;
  flex-shrink: 0;
}

.score-summary {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-loose);
  min-width: 200px;
}

.grade-s {
  border-color: var(--violet);
  color: var(--violet);
  background: var(--violet-bg);
}
.grade-a {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-bg);
}
.grade-b {
  border-color: var(--info);
  color: var(--info);
  background: rgba(96, 165, 250, 0.12);
}
.grade-c {
  border-color: var(--up-strong);
  color: var(--up-strong);
  background: var(--up-bg);
}
.grade-d {
  border-color: var(--text-muted);
  color: var(--text-muted);
  background: var(--surface-2);
}
.grade-f {
  border-color: var(--profit);
  color: var(--profit);
  background: var(--profit-bg);
}

.score-categories {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.score-cat-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.cat-label {
  width: 90px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  text-align: right;
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.cat-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--surface-2);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.cat-bar {
  height: 100%;
  border-radius: var(--radius-xs);
  transition: width var(--dur-slow) var(--ease-out);
}

.cat-val {
  width: 36px;
  font-size: var(--text-xs);
  font-weight: 700;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.bar-good {
  background: var(--up-strong);
  color: var(--up-strong);
}
.bar-mid {
  background: var(--accent);
  color: var(--accent);
}
.bar-bad {
  background: var(--profit);
  color: var(--profit);
}

.score-insights {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

.insight-block {
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.insight-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  margin-bottom: var(--space-2);
}

.insight-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 800;
}

.insight-block ul {
  margin: 0;
  padding-left: var(--space-4);
}

.insight-block li {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  line-height: var(--leading-loose);
}

.insight-strength .insight-title {
  color: var(--up-strong);
}
.insight-strength .insight-icon {
  background: var(--up-bg);
}

.insight-weakness .insight-title {
  color: var(--accent);
}
.insight-weakness .insight-icon {
  background: var(--accent-bg);
}

.insight-rec .insight-title {
  color: var(--info);
}
.insight-rec .insight-icon {
  background: rgba(96, 165, 250, 0.14);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-faint);
  border-radius: var(--radius-md);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 90px;
}

.mi-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
}

.mi-val {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
}

.mi-val.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* ==========================================================================
   Edit modal
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

.modal {
  width: 600px;
  max-width: 92vw;
  max-height: 88vh;
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

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.modal-head-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.modal-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--accent);
  letter-spacing: var(--tracking-hud);
  text-transform: uppercase;
  font-weight: 600;
}

.modal-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
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

.bot-type-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-faint);
}

.type-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: var(--space-3) var(--space-4);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: var(--text-md);
  font-weight: 600;
  cursor: pointer;
  margin-bottom: -1px;
  transition:
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.type-tab:hover {
  color: var(--text-primary);
}

.type-tab.active {
  color: var(--info);
  border-bottom-color: var(--info);
}

.type-tab.type-tab-scalp.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.type-tab-name {
  font-family: var(--font-sans);
  font-weight: 700;
}

.type-tab-desc {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  color: var(--text-faint);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
}

.modal-body {
  padding: var(--space-5);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-faint);
  background: var(--surface-1);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-4);
  background: var(--accent);
  color: var(--bg-base);
  border: none;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  cursor: pointer;
  box-shadow: var(--shadow-gold);
  transition:
    background var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-gold-strong);
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.form-label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wider);
  text-transform: uppercase;
  font-weight: 500;
}

.label-hint {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text-faint);
  font-weight: 400;
  letter-spacing: var(--tracking-wide);
  text-transform: none;
  margin-left: var(--space-2);
}

.form-group input,
.form-group select {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: inherit;
  padding: 8px var(--space-2);
  font-size: var(--text-sm);
  outline: none;
  transition:
    border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out);
}

.form-group input:focus,
.form-group select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.form-row {
  display: flex;
  gap: var(--space-3);
}

.scalping-section {
  background: var(--accent-bg);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.section-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--accent);
  font-weight: 600;
}

.section-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  padding: 3px 7px;
  background: var(--accent);
  color: var(--bg-base);
  border-radius: var(--radius-xs);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: 2px;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--surface-2);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  left: 3px;
  top: 3px;
  background: var(--text-muted);
  border-radius: var(--radius-full);
  transition:
    transform var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out);
}

.toggle-switch input:checked + .toggle-slider {
  background: var(--accent-bg);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(16px);
  background: var(--accent);
}

.time-inline {
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  padding: 5px var(--space-2);
  font-size: var(--text-sm);
  width: 110px;
  outline: none;
}

.time-inline:focus {
  border-color: var(--accent);
}

.toggle-off-label {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-faint);
  letter-spacing: var(--tracking-wider);
}

.msg {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  border: 1px solid;
  margin: 0;
}

.msg-fail {
  background: var(--profit-bg);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--profit-soft);
}

.msg-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: var(--tracking-wider);
  padding: 3px 7px;
  border-radius: var(--radius-xs);
  background: rgba(255, 255, 255, 0.08);
}

/* ==========================================================================
   Responsive
   ========================================================================== */

@media (max-width: 1024px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
  .score-insights {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .detail-header {
    flex-direction: column;
    align-items: stretch;
  }
  .header-actions {
    justify-content: stretch;
  }
  .header-actions > * {
    flex: 1;
    justify-content: center;
  }
  .perf-section {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
