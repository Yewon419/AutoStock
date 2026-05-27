-- 봇 참고자료 KB (universe scanner 후보 확장 + 사용자 알림 용도)
-- 실행일: 2026-05-24
-- 사전: 무중단. CREATE TABLE 한 건. main.py의 Base.metadata.create_all로 자동 생성되므로
--       본 SQL은 백업·재현용 (멱등 — IF NOT EXISTS).

BEGIN;

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id                  SERIAL PRIMARY KEY,
    bot_id              INTEGER NOT NULL REFERENCES trading_bots(id) ON DELETE CASCADE,
    source_type         VARCHAR(20) NOT NULL,                       -- text | url | pdf | youtube
    source_ref          VARCHAR(2000),                              -- URL · 파일 경로 · NULL(text)
    title               VARCHAR(500) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',     -- pending | ingesting | ready | failed
    summary             TEXT,
    mentioned_tickers   JSON DEFAULT '[]'::json,
    raw_text            TEXT,
    error_msg           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at         TIMESTAMPTZ,
    CONSTRAINT uq_knowledge_sources_bot_ref UNIQUE (bot_id, source_ref)
);

CREATE INDEX IF NOT EXISTS ix_knowledge_sources_bot_status  ON knowledge_sources(bot_id, status);
CREATE INDEX IF NOT EXISTS ix_knowledge_sources_bot_created ON knowledge_sources(bot_id, created_at);

COMMIT;
