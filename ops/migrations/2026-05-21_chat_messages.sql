-- AI 튜닝 어시스턴트 대화 기록 영속화
-- 실행일: 2026-05-21
-- 사전: 무중단. CREATE TABLE 한 건이라 락 영향 없음.

BEGIN;

CREATE TABLE chat_messages (
    id         SERIAL PRIMARY KEY,
    bot_id     INTEGER NOT NULL REFERENCES trading_bots(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL,           -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_chat_messages_bot_id_id ON chat_messages(bot_id, id);

COMMIT;
