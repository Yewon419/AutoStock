"""봇별 참고자료 KB CRUD 라우터.

source_type: 'text' | 'url' | 'pdf' | 'youtube'
  - text/url/youtube: JSON body로 POST /knowledge-sources
  - pdf            : multipart/form-data로 POST /knowledge-sources/upload
                     업로드 시점에 pdfplumber로 텍스트 추출 → raw_text 저장,
                     파일 자체는 디스크에 남기지 않음 (저작권·디스크 가드)

등록 즉시 Celery task로 비동기 ingestion 큐잉. 같은 (bot_id, source_ref) 중복은 409.
text 타입은 source_ref=NULL이라 중복 허용.

소속: 봇별. 봇 삭제 시 ON DELETE CASCADE로 자동 정리.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.knowledge import KnowledgeSource
from models.trading import TradingBot


_PDF_MAX_BYTES = 20_000_000  # 20MB


router = APIRouter(tags=["knowledge-sources"])


def _user_id(current_user: dict) -> int:
    return int(current_user['sub'])


def _verify_bot_ownership(db: Session, bot_id: int, user_id: int) -> TradingBot:
    bot = (
        db.query(TradingBot)
        .filter(TradingBot.id == bot_id, TradingBot.user_id == user_id)
        .first()
    )
    if not bot:
        raise HTTPException(status_code=404, detail="봇을 찾을 수 없습니다")
    return bot


# ── 스키마 ────────────────────────────────────────────────────────

class CreateKnowledgeRequest(BaseModel):
    source_type: Literal['text', 'url', 'youtube']  # pdf는 별도 multipart 엔드포인트
    source_ref: Optional[str] = None                 # url/youtube: 필수, text: NULL
    title: str
    raw_text: Optional[str] = None                   # text 타입에 한해 본문


class KnowledgeSourceItem(BaseModel):
    id: int
    bot_id: int
    source_type: str
    source_ref: Optional[str] = None
    title: str
    status: str
    summary: Optional[str] = None
    mentioned_tickers: list[str] = []
    error_msg: Optional[str] = None
    created_at: datetime
    ingested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 엔드포인트 ─────────────────────────────────────────────────────

@router.post(
    "/trading/bots/{bot_id}/knowledge-sources",
    response_model=KnowledgeSourceItem,
)
def create_knowledge_source(
    bot_id: int,
    req: CreateKnowledgeRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _verify_bot_ownership(db, bot_id, _user_id(current_user))

    if req.source_type in ("url", "youtube"):
        if not req.source_ref or not req.source_ref.strip():
            raise HTTPException(
                status_code=400,
                detail=f"{req.source_type} 타입은 source_ref가 필요합니다",
            )
    else:  # text
        if not req.raw_text or not req.raw_text.strip():
            raise HTTPException(status_code=400, detail="text 타입은 raw_text가 필요합니다")

    if req.source_ref:
        existing = (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.bot_id == bot_id,
                KnowledgeSource.source_ref == req.source_ref,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"이미 등록된 자료입니다 (id={existing.id}, status={existing.status})",
            )

    src = KnowledgeSource(
        bot_id=bot_id,
        source_type=req.source_type,
        source_ref=req.source_ref,
        title=req.title,
        status="pending",
        raw_text=req.raw_text if req.source_type == "text" else None,
        mentioned_tickers=[],
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    # ingestion 비동기 큐잉 (실패해도 사용자는 retry로 재시도 가능)
    from tasks.knowledge_ingestion import ingest_knowledge_source
    ingest_knowledge_source.delay(src.id)

    return src


@router.get(
    "/trading/bots/{bot_id}/knowledge-sources",
    response_model=list[KnowledgeSourceItem],
)
def list_knowledge_sources(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _verify_bot_ownership(db, bot_id, _user_id(current_user))
    rows = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.bot_id == bot_id)
        .order_by(KnowledgeSource.created_at.desc())
        .all()
    )
    return rows


class KbUnreadBot(BaseModel):
    bot_id: int
    bot_name: str
    count: int
    max_id: int = 0


class KbUnreadSummary(BaseModel):
    total: int
    by_bot: list[KbUnreadBot]


@router.get("/trading/bots/knowledge-sources/unread-summary", response_model=KbUnreadSummary)
def kb_unread_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """전 봇 ready KB 자료 합산 카운트 + 봇별 분포 + 봇별 max_id (헤더 🔔 unread 추적용).

    pending-summary와 동일 패턴 — 프론트 localStorage(`as:lastSeenKbByBot`) 비교로
    봇별 unread 판정.
    """
    user_id = _user_id(current_user)
    rows = (
        db.query(TradingBot.id, TradingBot.name, KnowledgeSource.id)
        .join(KnowledgeSource, KnowledgeSource.bot_id == TradingBot.id)
        .filter(TradingBot.user_id == user_id, KnowledgeSource.status == 'ready')
        .all()
    )
    by_bot_map: dict[int, dict] = {}
    for bot_id, bot_name, kb_id in rows:
        if bot_id not in by_bot_map:
            by_bot_map[bot_id] = {'bot_id': bot_id, 'bot_name': bot_name, 'count': 0, 'max_id': 0}
        by_bot_map[bot_id]['count'] += 1
        if kb_id > by_bot_map[bot_id]['max_id']:
            by_bot_map[bot_id]['max_id'] = kb_id
    by_bot = [KbUnreadBot(**v) for v in by_bot_map.values()]
    return KbUnreadSummary(total=sum(b.count for b in by_bot), by_bot=by_bot)


@router.delete(
    "/trading/bots/{bot_id}/knowledge-sources/{source_id}",
    status_code=204,
)
def delete_knowledge_source(
    bot_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _verify_bot_ownership(db, bot_id, _user_id(current_user))
    src = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.id == source_id, KnowledgeSource.bot_id == bot_id)
        .first()
    )
    if not src:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다")
    db.delete(src)
    db.commit()
    return None


@router.post(
    "/trading/bots/{bot_id}/knowledge-sources/{source_id}/retry",
    response_model=KnowledgeSourceItem,
)
def retry_knowledge_source(
    bot_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """실패한 ingestion 재시도. status=pending으로 되돌리고 task 재큐잉."""
    _verify_bot_ownership(db, bot_id, _user_id(current_user))
    src = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.id == source_id, KnowledgeSource.bot_id == bot_id)
        .first()
    )
    if not src:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다")
    if src.status == "ingesting":
        raise HTTPException(status_code=400, detail="이미 처리 중입니다")
    src.status = "pending"
    src.error_msg = None
    db.commit()
    db.refresh(src)

    from tasks.knowledge_ingestion import ingest_knowledge_source
    ingest_knowledge_source.delay(src.id)
    return src


@router.post(
    "/trading/bots/{bot_id}/knowledge-sources/upload",
    response_model=KnowledgeSourceItem,
)
async def upload_pdf_knowledge_source(
    bot_id: int,
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """PDF 파일 업로드 → 즉시 pdfplumber로 텍스트 추출 → raw_text 저장.

    파일 자체는 디스크에 남기지 않음. source_ref에 파일명만 기록 (중복 검사용).
    추출 후 ticker 매칭 + LLM 요약은 비동기 ingestion task가 처리.
    """
    _verify_bot_ownership(db, bot_id, _user_id(current_user))

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다 (.pdf 확장자 필수)")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다")
    if len(pdf_bytes) > _PDF_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"파일 크기 초과 ({len(pdf_bytes):,} > {_PDF_MAX_BYTES:,} bytes)",
        )

    source_ref = f"pdf:{file.filename}"
    existing = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.bot_id == bot_id, KnowledgeSource.source_ref == source_ref)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"같은 파일명이 이미 등록됨 (id={existing.id}, status={existing.status})",
        )

    from tasks.knowledge_ingestion import extract_pdf_text, ingest_knowledge_source

    try:
        raw_text = extract_pdf_text(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF 텍스트 추출 실패: {type(e).__name__}: {e}")

    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="PDF에서 텍스트를 추출하지 못했습니다 (이미지 PDF 또는 빈 파일)",
        )

    src = KnowledgeSource(
        bot_id=bot_id,
        source_type="pdf",
        source_ref=source_ref,
        title=title,
        status="pending",
        raw_text=raw_text,
        mentioned_tickers=[],
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    ingest_knowledge_source.delay(src.id)
    return src
