-- 포지션 중복 방지: (bot_id, ticker) UNIQUE 제약 추가.
-- Race condition 또는 reconcile 재진입 시 동일 (bot_id, ticker) 중복 row가
-- 생기면 평가금액 이중 계산, 매도 시 일부만 처리 → 고아 row 발생.
-- 기존 중복이 있으면 이 스크립트 실행 전에 수동 병합 필요.

ALTER TABLE positions
  ADD CONSTRAINT uq_positions_bot_ticker UNIQUE (bot_id, ticker);
