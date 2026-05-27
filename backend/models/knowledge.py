from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from core.database import Base


class KnowledgeSource(Base):
    """봇 strategy 수립 참고자료 (KB).

    universe scanner 후보 확장 + 사용자 알림 용도.
    Phase 1: source_type = text | url. Phase 2에서 pdf | youtube 추가.

    status: pending → ingesting → ready | failed
    mentioned_tickers: ['005430', '377030', ...] — ticker_extractor 결과
    raw_text: 추출 원문 (재처리·디버그용, 50K자 상한)
    """
    __tablename__ = "knowledge_sources"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("trading_bots.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(20), nullable=False)
    source_ref = Column(String(2000))
    title = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    summary = Column(Text)
    mentioned_tickers = Column(JSON, default=list)
    raw_text = Column(Text)
    error_msg = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ingested_at = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("bot_id", "source_ref", name="uq_knowledge_sources_bot_ref"),
        Index("ix_knowledge_sources_bot_status", "bot_id", "status"),
        Index("ix_knowledge_sources_bot_created", "bot_id", "created_at"),
    )
