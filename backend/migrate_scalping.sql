-- 단타(Scalping) 기능을 위한 DB 마이그레이션
-- trading_bots 테이블에 단타 설정 컬럼 추가

ALTER TABLE trading_bots
  ADD COLUMN IF NOT EXISTS bot_type VARCHAR(10) DEFAULT 'swing',
  ADD COLUMN IF NOT EXISTS candle_interval INTEGER DEFAULT 5,
  ADD COLUMN IF NOT EXISTS intraday_close BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS intraday_close_time TIME DEFAULT '14:50:00';
