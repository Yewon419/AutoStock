from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from core.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    conditions = Column(JSON, nullable=False)
    strategy_type = Column(String(20), default='swing')   # swing | scalping
    source = Column(String(20), default='manual')          # manual | ai_generated
    ai_analysis = Column(Text)                             # LLM 분석 코멘트
    ai_confidence = Column(Integer)                        # LLM 신뢰도 0~100
    pattern = Column(String(40))                           # trend_breakout|pullback|volatility_squeeze|scalping_mean_reversion|scalping_breakout|null
    risk_params = Column(JSON)                             # AI 팔레트가 전략별 결정한 SL/TP/MDD/max_positions 등. 봇 생성 시 우선 적용
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
