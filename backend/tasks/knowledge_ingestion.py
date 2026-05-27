"""봇 참고자료 ingestion task.

source_type 분기:
  - text     : raw_text 그대로 (사용자 입력)
  - url      : requests + BeautifulSoup로 본문 추출
  - pdf      : 업로드 엔드포인트가 즉시 pdfplumber로 추출 후 raw_text 저장.
               본 task는 raw_text를 그대로 사용. 디스크에 파일 잔존 X.
  - youtube  : youtube-transcript-api로 자막 가져옴 (한국어 우선, 영어 fallback)

흐름: pending → ingesting → (raw_text 확보 → ticker 매칭 → LLM 요약) → ready | failed
실패 시 status='failed' + error_msg. 사용자는 retry API로 재큐잉.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import redis as _redis_sync
import requests
from bs4 import BeautifulSoup

from core.config import settings
from core.database import SessionLocal
from models.knowledge import KnowledgeSource
from services.ticker_extractor import extract_tickers
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_ALERTS_KEY = "autostock:alerts"
_ALERTS_TRIM = 999  # 다른 alert push 코드와 동일

_URL_TIMEOUT_SEC = 15
_URL_MAX_BYTES = 2_000_000      # URL 본문 크기 가드 (메모리·LLM 비용)
_PDF_MAX_BYTES = 20_000_000     # PDF 업로드 크기 가드 (20MB)
_RAW_TEXT_TRUNCATE = 50_000     # DB 저장 상한
_SUMMARY_INPUT_TRUNCATE = 20_000  # LLM 입력 상한
_YOUTUBE_LANGS = ('ko', 'en')   # 자막 우선순위
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})"
)


def _fetch_url_text(url: str) -> str:
    """URL 본문을 받아 script/style 제거한 순수 텍스트로 반환."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AutoStock-KB-Ingestion/1.0)",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
    }
    resp = requests.get(url, headers=headers, timeout=_URL_TIMEOUT_SEC, stream=True)
    resp.raise_for_status()

    content = resp.raw.read(_URL_MAX_BYTES + 1, decode_content=True)
    if len(content) > _URL_MAX_BYTES:
        raise RuntimeError(f"본문 크기 초과 (> {_URL_MAX_BYTES:,} bytes)")

    encoding = resp.encoding or "utf-8"
    try:
        html = content.decode(encoding, errors="replace")
    except LookupError:
        html = content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _summarize_with_llm(title: str, text: str, mentioned_tickers: list[str]) -> str:
    """sonnet-4-6로 본문 2~3문장 요약. ANTHROPIC_API_KEY 부재 시 빈 문자열."""
    if not settings.ANTHROPIC_API_KEY:
        logger.info("[knowledge_ingestion] ANTHROPIC_API_KEY 미설정 — 요약 생략")
        return ""

    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    tickers_hint = (
        ", ".join(mentioned_tickers[:20])
        if mentioned_tickers
        else "(자동 매칭된 종목 없음)"
    )
    truncated = text[:_SUMMARY_INPUT_TRUNCATE]
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=(
            "당신은 한국 주식 자동매매 봇의 참고자료를 요약하는 어시스턴트입니다. "
            "본문을 한국어 2~3문장으로 핵심만 요약하세요. "
            "투자 추천이 아닌 사실 요약만. 가능하면 언급된 종목·섹터·이벤트를 포함하세요."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"제목: {title}\n"
                f"자동 매칭된 종목: {tickers_hint}\n\n"
                f"본문:\n{truncated}"
            ),
        }],
    )
    block = response.content[0]
    text_attr = getattr(block, "text", None)
    return text_attr.strip() if isinstance(text_attr, str) else ""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF 바이트에서 텍스트 추출. 업로드 엔드포인트에서 동기 호출.

    파일 자체는 호출자가 폐기 (디스크 잔존 X). 페이지별 텍스트를 줄바꿈으로 연결.
    크기 초과는 호출자가 가드, 본 함수는 받은 바이트를 모두 처리.
    """
    import io
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                pages.append(page_text)
    return "\n".join(pages)


def _parse_youtube_video_id(url: str) -> str:
    m = _YOUTUBE_VIDEO_ID_PATTERN.search(url)
    if not m:
        raise ValueError(f"YouTube video_id를 URL에서 찾지 못함: {url}")
    return m.group(1)


def _fetch_youtube_transcript(url: str) -> str:
    """YouTube 영상의 공개 자막을 받아 공백 연결한 텍스트로 반환.

    한국어 자막 우선, 없으면 영어 fallback. 둘 다 없으면 NoTranscriptFound 전파.
    youtube-transcript-api는 공개 자막 endpoint만 호출하므로 ToS 회색지대 아님.

    v1.x API (인스턴스 메서드 + FetchedTranscriptSnippet) 기준.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = _parse_youtube_video_id(url)
    fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(_YOUTUBE_LANGS))
    return " ".join(snippet.text for snippet in fetched if getattr(snippet, "text", ""))


def _push_ready_alert(src: KnowledgeSource) -> None:
    """KB ready 시 봇별 알림 LIST에 push. 디덥 없음 — 자료 등록당 1회 의도.

    실패해도 ingestion 본 흐름엔 영향 없음 (warning 로그만).
    """
    try:
        client = _redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
        payload = {
            "type": "KNOWLEDGE_READY",
            "bot_id": src.bot_id,
            "source_id": src.id,
            "source_type": src.source_type,
            "title": src.title,
            "summary": src.summary or "",
            "tickers": list(src.mentioned_tickers or []),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        client.lpush(_ALERTS_KEY, json.dumps(payload, ensure_ascii=False))
        client.ltrim(_ALERTS_KEY, 0, _ALERTS_TRIM)
    except Exception as e:
        logger.warning("[knowledge_ingestion] alert push 실패 source_id=%d: %r", src.id, e)


def _extract_raw_text(src: KnowledgeSource) -> str:
    if src.source_type == "url":
        if not src.source_ref:
            raise ValueError("url 타입에는 source_ref가 필요합니다")
        return _fetch_url_text(src.source_ref)
    if src.source_type == "youtube":
        if not src.source_ref:
            raise ValueError("youtube 타입에는 source_ref(영상 URL)가 필요합니다")
        return _fetch_youtube_transcript(src.source_ref)
    if src.source_type in ("text", "pdf"):
        # pdf는 업로드 엔드포인트가 이미 raw_text에 추출본을 채워 둠
        raw = src.raw_text or ""
        if not raw.strip():
            raise ValueError(f"{src.source_type} 타입에는 raw_text가 필요합니다")
        return raw
    raise ValueError(f"지원하지 않는 source_type: {src.source_type}")


@celery_app.task(name="tasks.knowledge_ingestion.ingest_knowledge_source")
def ingest_knowledge_source(source_id: int) -> dict[str, Any]:
    """KnowledgeSource 1건 ingestion. 실패해도 예외 전파하지 않고 status='failed'로 기록."""
    db = SessionLocal()
    try:
        src = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
        if not src:
            logger.warning("[knowledge_ingestion] source_id=%d 없음", source_id)
            return {"status": "missing", "source_id": source_id}

        src.status = "ingesting"
        src.error_msg = None
        db.commit()

        try:
            raw_text = _extract_raw_text(src)
            tickers = extract_tickers(raw_text, db)
            summary = _summarize_with_llm(src.title, raw_text, tickers)

            src.raw_text = raw_text[:_RAW_TEXT_TRUNCATE]
            src.mentioned_tickers = tickers
            src.summary = summary or None
            src.status = "ready"
            src.ingested_at = datetime.utcnow()
            db.commit()
            db.refresh(src)
            _push_ready_alert(src)
            logger.info(
                "[knowledge_ingestion] source_id=%d ready (tickers=%d, summary_chars=%d)",
                source_id, len(tickers), len(summary),
            )
            return {
                "status": "ready",
                "source_id": source_id,
                "tickers": tickers,
                "summary_chars": len(summary),
            }
        except Exception as e:
            db.rollback()
            failed_src = (
                db.query(KnowledgeSource)
                .filter(KnowledgeSource.id == source_id)
                .first()
            )
            if failed_src is not None:
                failed_src.status = "failed"
                failed_src.error_msg = f"{type(e).__name__}: {e}"
                db.commit()
            logger.exception("[knowledge_ingestion] source_id=%d 실패", source_id)
            return {"status": "failed", "source_id": source_id, "error": str(e)}
    finally:
        db.close()
