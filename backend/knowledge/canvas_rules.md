# AutoStock 캔버스 노드 규칙

## 노드 카탈로그

### 소스 노드 (데이터 수집, 입력 없음)
| 노드 | 출력 핸들 | 실제 동작 |
|------|----------|---------|
| `marketContext` | `market_data` | 뉴스·지수·투자자동향·VIX·달러/원 수집 |
| `techIndicators` | `indicator_data` | DB 최신 RSI/ADX 평균 등 지표 요약 반환 |
| `mlScores` | `ml_scores` | Redis에 캐시된 ML 스코어 조회 (mlModel 실행 후 유효) |
| `accountConfig` | `account_config` | 계좌·매매모드(mock/paper/real) 설정 |

### 전략 노드 (전략 정의)
| 노드 | 출력 핸들 | 실제 동작 |
|------|----------|---------|
| `strategy` | `strategy` | DB에서 기존 전략 선택, strategy_id 전달 |
| `strategyBuilder` | `strategy` | 조건 직접 입력 → DB 저장/업데이트, strategy_id 전달 |

### 처리 노드 (연산)
| 노드 | 입력 핸들 | 출력 핸들 | 실제 동작 |
|------|----------|----------|---------|
| `mlModel` | `indicator_data`* | `ml_scores` | RandomForest 학습 → 상위 50개 종목 매수확률 Redis 저장 |
| `llmGenerator` | `market_data`*, `ml_scores`* | `strategy` | Claude가 시장+ML 데이터 분석 → 전략 조건 생성·DB 저장 |
| `backtest` | `strategy` | `backtest_result` | ML상위30 or 거래량상위100 종목으로 전략 백테스트 |
| `strategyOptimize` | `strategy`, `backtest_result`* | `strategy` | 각 조건 value ±30% Grid Search → 샤프비율 최적값으로 DB 업데이트 |

*표시: 연결 선택사항 (시각적 의존 표현 용도, 해당 노드가 독립적으로 데이터 수집)

### 출력 노드
| 노드 | 입력 핸들 | 실제 동작 |
|------|----------|---------|
| `botApply` | `strategy`(필수), `tickers`(필수), `account_config`(선택) | 봇 생성/업데이트 → 전략·종목 적용 → 자동 시작 |

---

## 허용 연결 규칙 (엄격히 적용됨)

```
marketContext    [market_data]      → llmGenerator    [market_data]
techIndicators   [indicator_data]   → mlModel         [indicator_data]
mlScores         [ml_scores]        → llmGenerator    [ml_scores]
mlModel          [ml_scores]        → llmGenerator    [ml_scores]
mlModel          [ml_scores]        → botApply        [tickers]
llmGenerator     [strategy]         → backtest        [strategy]
llmGenerator     [strategy]         → strategyOptimize[strategy]
llmGenerator     [strategy]         → botApply        [strategy]
llmGenerator     [strategy]         → botApply        [tickers]   ← llmGenerator가 반환하는 종목 리스트를 tickers로 전달
strategy         [strategy]         → backtest        [strategy]
strategy         [strategy]         → strategyOptimize[strategy]
strategy         [strategy]         → botApply        [strategy]
strategyBuilder  [strategy]         → backtest        [strategy]
strategyBuilder  [strategy]         → strategyOptimize[strategy]
strategyBuilder  [strategy]         → botApply        [strategy]
backtest         [backtest_result]  → strategyOptimize[backtest_result]
backtest         [backtest_result]  → botApply        [tickers]
strategyOptimize [strategy]         → botApply        [strategy]
strategyOptimize [strategy]         → botApply        [tickers]
accountConfig    [account_config]   → botApply        [account_config]
```

규칙 위반 시 하단에 오류 토스트 표시, 연결 차단됨.

### 연결 동작 참고사항

**장식적 연결 (시각적 의존성 표현, 데이터 미전달)**
- `techIndicators → mlModel`: mlModel은 DB에서 독립적으로 지표 로드. 연결은 "mlModel 실행 전 지표 수집 필요"를 시각화하는 용도.
- `mlScores → llmGenerator`, `mlModel → llmGenerator`: llmGenerator는 Redis에서 독립적으로 ML 스코어 로드. 연결은 실행 순서 의존성 표현 용도.

**`llmGenerator → botApply[tickers]` 주의**
- llmGenerator의 출력 핸들명은 `strategy`이지만, botApply의 `tickers` 입력에 연결 가능.
- llmGenerator 실행 결과에 포함된 종목 리스트(`tickers` 필드)가 botApply로 전달됨.
- mlModel 또는 backtest 없이 llmGenerator만으로 전략+종목을 동시에 botApply에 전달할 때 사용.

**`backtest_result → strategyOptimize` 현재 한계**
- strategyOptimize는 연결된 backtest_result 데이터를 실제로 사용하지 않음.
- strategyOptimize는 항상 자체적으로 Grid Search + 백테스트 재실행.
- 연결은 "backtest 완료 후 최적화" 실행 순서를 시각화하는 용도.

---

## 파이프라인 프리셋

**풀 파이프라인 (ML+LLM+최적화)**
```
techIndicators → mlModel → llmGenerator → strategyOptimize → botApply
marketContext  ↗(market_data)            ↗(strategy)          ↗(strategy+tickers)
                            (ml_scores) ↗
```
mlModel이 종목 스코어링 → llmGenerator가 ML 특성 반영해 전략 생성 → strategyOptimize가 파라미터 최적화 → botApply가 최적화된 전략+종목으로 봇 시작

**빠른 전략 (ML 캐시+LLM)**
```
marketContext → llmGenerator → botApply[strategy]
mlScores      ↗(ml_scores)
mlScores                    → botApply[tickers]
```
mlModel 재학습 없이 캐시된 ML 스코어 활용. 빠르지만 ML 스코어가 최신인지 확인 필요.

**백테스트+최적화**
```
strategyBuilder → backtest         → strategyOptimize → botApply[tickers]
              ↘(strategy)↗(backtest_result)↗(strategy)↗
               └──────────────────────────────────────→ botApply[strategy]
```
수동 전략 설계 → 성과 확인 → Grid Search 최적화 → 봇 적용

**기존 전략 재백테스트**
```
strategy → backtest[strategy]
strategy → botApply[strategy]
backtest → botApply[tickers]
```

---

## botApply 데이터 흐름 (중요)

- **`strategy` 핸들**: strategy_id 전달 → 봇의 전략 지정. strategy/strategyBuilder/llmGenerator/strategyOptimize 중 하나 연결 필수.
- **`tickers` 핸들**: 매매 종목 목록 전달. 반드시 연결 필요.
  - mlModel 연결 시: ML 상위 종목
  - backtest 연결 시: 백테스트 대상 종목
  - strategyOptimize 연결 시: 최적화 대상 종목
- **`account_config` 핸들**: 미연결 시 mock 모드 자동 적용

botApply는 봇이 없으면 전략명 기반으로 자동 생성 (초기자금 1000만원). auto_start 기본값 true → 즉시 RUNNING.

---

## 전략 조건 문법

**지원 지표 (indicator 필드값)**
- 스윙: `rsi`, `macd`, `macd_signal`, `macd_histogram`, `stoch_k`, `stoch_d`
- 볼린저: `bollinger_upper`, `bollinger_middle`, `bollinger_lower`
- 이동평균: `ma_5`, `ma_10`, `ma_20`, `ma_50`, `ma_200`
- 기타: `adx`, `obv`, `atr`, `volume_ratio`, `opening_gap`
- 단타 전용: `vwap`, `price_vs_vwap`, `ma5_minus_ma20`

**지원 조건 (condition 필드값)**
- `above`: 지표 > value
- `below`: 지표 < value
- `between`: value < 지표 < value2
- `golden_cross`: 이전 < value → 현재 ≥ value (상향돌파)
- `dead_cross`: 이전 ≥ value → 현재 < value (하향돌파)

**검증된 조합**
```
스윙 - RSI 과매도:      [{indicator: rsi, condition: below, value: 30}]
스윙 - 강세장 눌림목:   [{indicator: adx, condition: above, value: 25},
                         {indicator: rsi, condition: between, value: 40, value2: 60}]
스윙 - MACD 골든크로스: [{indicator: macd, condition: golden_cross, value: 0}]
단타 - 과매도+거래량:   [{indicator: rsi, condition: below, value: 35},
                         {indicator: volume_ratio, condition: above, value: 2.0}]
단타 - VWAP 돌파:       [{indicator: price_vs_vwap, condition: above, value: 0},
                         {indicator: volume_ratio, condition: above, value: 1.5}]
```

---

## 전략 평가 기준 (백테스트 품질 게이팅)

| 지표 | 최소 기준 (자동 거부) | 우수 기준 |
|------|-------------------|---------|
| 거래 횟수 | ≥ 3회 | ≥ 20회 |
| 총 수익률 | ≥ -15% | ≥ 5% |
| 승률 | ≥ 25% | ≥ 50% |
| 샤프 비율 | ≥ 0 | ≥ 1.0 |
| 최대 낙폭(MDD) | ≤ 30% | ≤ 15% |

게이팅 실패 시 대응:
- 거래 횟수 부족 → 조건 완화 (value 범위 확대, 조건 수 줄이기)
- 승률 낮음 → 조건 강화 (volume_ratio 또는 adx 추가)
- MDD 과대 → stop_loss_pct 축소
- llmGenerator 게이팅 실패 → 재실행하면 다른 전략 생성됨

strategyOptimize: 각 조건 value ±30% 11단계 탐색 → 샤프비율 최적값으로 DB 업데이트. golden_cross/dead_cross는 스킵.
