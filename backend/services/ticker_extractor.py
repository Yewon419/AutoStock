"""KRX 종목 사전 기반 ticker 추출 서비스.

KnowledgeSource ingestion에서 본문 텍스트로부터 언급된 한국 종목 ticker를 뽑는다.
scanner universe 합집합 후보 확장(Phase 3)·UI 표시·LLM 요약 힌트에 사용.

매칭 정책:
- 6자리 코드: 본문에 등장 + KRX active stocks에 존재
- 회사명: 본문에 substring 등장 + 단어 경계 검사.
  - 매칭 영역 마스킹으로 부분 매칭 차단. 예: "SK하이닉스" → 000660만, 034730·452400 차단.
  - 단어 경계: 앞은 한글/영숫자 아니면 OK. 뒤는 한글/영숫자 아니면 OK +
    한글이어도 자주 쓰이는 조사 첫 글자(은/는/이/가/을/를/의/에/와/과/로/도/만/나)면 OK.
  - 예: "카카오와"·"기아가"·"현대차는" → 조사 통과 ✓
  - 예: "하이브리드"·"기아자동차" → 조사 아닌 한글 뒤따라 거부.
- 회사명 최소 길이: 순한글 3자, 영문/숫자 1자라도 포함되면 2자 (LG·SK 등 약어 허용).
  한글 2자 회사명(두산·한화·롯데 등)은 사전 제외 — false positive 가드.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from threading import Lock

from sqlalchemy.orm import Session

from models.market import Stock


_TICKER_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")

# 회사명 뒤에 흔히 붙는 조사 첫 글자. 정확한 형태소 분석 없이 단어 경계로 인정.
_JOSA_FIRST_CHARS: frozenset[str] = frozenset(
    {'은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '로', '도', '만', '나'}
)


def _name_passes_length(name: str) -> bool:
    """순한글이면 3자 이상, 영문/숫자 1자라도 포함되면 2자 이상."""
    if not name or len(name) < 2:
        return False
    has_alnum = any(c.isascii() and c.isalnum() for c in name)
    return len(name) >= (2 if has_alnum else 3)


def _is_left_boundary(text: str, pos: int) -> bool:
    """매칭 시작 직전 위치가 단어 경계인지. 범위 밖·마스킹 영역은 경계로 인정."""
    if pos < 0:
        return True
    c = text[pos]
    if c == '\x00':
        return True
    if '가' <= c <= '힣':
        return False
    if c.isascii() and c.isalnum():
        return False
    return True


def _is_right_boundary(text: str, pos: int) -> bool:
    """매칭 종료 직후 위치가 단어 경계인지. 한글이어도 조사 첫 글자는 경계로 인정."""
    if pos >= len(text):
        return True
    c = text[pos]
    if c == '\x00':
        return True
    if c in _JOSA_FIRST_CHARS:
        return True
    if '가' <= c <= '힣':
        return False
    if c.isascii() and c.isalnum():
        return False
    return True


@dataclass(frozen=True)
class _TickerDict:
    code_to_name: dict[str, str]
    names_sorted: tuple[tuple[str, str], ...]  # (company_name, ticker) — 길이 내림차순


_cache: _TickerDict | None = None
_cache_lock = Lock()


def _load_dict(db: Session) -> _TickerDict:
    rows = (
        db.query(Stock.ticker, Stock.company_name)
        .filter(Stock.is_active.is_(True))
        .all()
    )
    code_to_name: dict[str, str] = {ticker: name for ticker, name in rows if ticker and name}
    names_sorted = tuple(
        sorted(
            (
                (name, ticker)
                for ticker, name in rows
                if _name_passes_length(name)
            ),
            key=lambda x: -len(x[0]),
        )
    )
    return _TickerDict(code_to_name=code_to_name, names_sorted=names_sorted)


def _get_dict(db: Session, refresh: bool = False) -> _TickerDict:
    global _cache
    with _cache_lock:
        if _cache is None or refresh:
            _cache = _load_dict(db)
        return _cache


def extract_tickers(text: str, db: Session, refresh: bool = False) -> list[str]:
    """텍스트에서 KRX ticker 추출. 중복 제거, 등장 순서 보존."""
    if not text:
        return []
    d = _get_dict(db, refresh=refresh)
    found: list[str] = []
    seen: set[str] = set()

    for m in _TICKER_PATTERN.finditer(text):
        code = m.group(1)
        if code in d.code_to_name and code not in seen:
            found.append(code)
            seen.add(code)

    haystack = list(text)
    for name, ticker in d.names_sorted:
        if ticker in seen:
            continue
        joined = ''.join(haystack)
        start = 0
        matched = False
        while True:
            pos = joined.find(name, start)
            if pos < 0:
                break
            end = pos + len(name)
            if _is_left_boundary(joined, pos - 1) and _is_right_boundary(joined, end):
                matched = True
                for k in range(pos, end):
                    haystack[k] = '\x00'
            start = end
        if matched:
            found.append(ticker)
            seen.add(ticker)

    return found


def invalidate_cache() -> None:
    """KRX 종목 사전 캐시 무효화 (Stock 테이블 갱신 후 명시 호출)."""
    global _cache
    with _cache_lock:
        _cache = None
