-- Phase 0: 봇 단위 strategy 분리 + 튜닝 어시스턴트 기반 테이블
-- 실행일: 2026-05-15
-- 사전: 봇 19~22 STOPPED, pg_dump 백업 (backups/phase0_*.sql)
-- 위험: ALTER TABLE 짧은 락. 트랜잭션 안에서 일괄 처리.

BEGIN;

-- 1. 53개 고아 strategy DELETE (봇 미연결분)
DELETE FROM strategies WHERE id NOT IN (34, 47, 48, 49, 50);

-- 2. strategies.bot_id 컬럼 추가 (임시 nullable)
ALTER TABLE strategies ADD COLUMN bot_id INTEGER;

-- 3. 5개 strategy의 bot_id 자동 채움 (trading_bots.strategy_id 역참조)
UPDATE strategies s SET bot_id = b.id
FROM trading_bots b WHERE b.strategy_id = s.id;

-- 4. NOT NULL + UNIQUE + FK 제약
ALTER TABLE strategies ALTER COLUMN bot_id SET NOT NULL;
ALTER TABLE strategies ADD CONSTRAINT strategies_bot_id_unique UNIQUE (bot_id);
ALTER TABLE strategies ADD CONSTRAINT strategies_bot_id_fkey
    FOREIGN KEY (bot_id) REFERENCES trading_bots(id) ON DELETE CASCADE;
CREATE INDEX ix_strategies_bot_id ON strategies(bot_id);

-- 5. strategy_history (undo·감사 로그)
CREATE TABLE strategy_history (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES trading_bots(id) ON DELETE CASCADE,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    before_conditions JSON,
    after_conditions JSON,
    before_risk_params JSON,
    after_risk_params JSON,
    source VARCHAR(20) NOT NULL,  -- manual | ai_chat | ai_suggestion
    llm_reasoning TEXT
);
CREATE INDEX ix_strategy_history_bot_id ON strategy_history(bot_id);
CREATE INDEX ix_strategy_history_applied_at ON strategy_history(applied_at DESC);

-- 6. tuning_suggestions (08:30 자동 제안함)
CREATE TABLE tuning_suggestions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES trading_bots(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | applied | dismissed
    suggested_conditions JSON,
    suggested_risk_params JSON,
    diagnosis_text TEXT NOT NULL,
    applied_at TIMESTAMPTZ,
    applied_history_id INTEGER REFERENCES strategy_history(id) ON DELETE SET NULL
);
CREATE INDEX ix_tuning_suggestions_bot_id_status ON tuning_suggestions(bot_id, status);
CREATE INDEX ix_tuning_suggestions_created_at ON tuning_suggestions(created_at DESC);

COMMIT;
