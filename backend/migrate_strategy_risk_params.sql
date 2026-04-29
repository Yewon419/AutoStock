-- Phase 0a: AI 팔레트가 전략별로 결정한 패턴/리스크 파라미터 컬럼
-- 봇 생성 시 strategy.risk_params가 있으면 SCALPING_PROFILE/SWING_PROFILE 디폴트보다 우선 적용
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS pattern VARCHAR(40);

ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS risk_params JSON;
