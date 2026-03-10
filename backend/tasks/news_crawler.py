"""
시장 컨텍스트 수집기
- yfinance : KOSPI/KOSDAQ/S&P500/나스닥/VIX/달러·원
- pykrx    : 투자자별 순매수(외국인/기관/개인) — 실패 시 skip
- 네이버 금융 뉴스: 시장 헤드라인 크롤링

반환값: MarketContext dict — llm_strategy.py에서 프롬프트 빌딩에 사용
"""
import logging
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── 네이버 금융 뉴스 ─────────────────────────────────────────────────

def fetch_naver_news(limit: int = 10) -> list[str]:
    """네이버 금융 뉴스 헤드라인 수집"""
    try:
        url = "https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258"
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        headlines = []
        for a in soup.select("dl dd.articleSubject a, .newsList .articleSubject a, .articleSubject a"):
            text = a.get_text(strip=True)
            if text and len(text) > 5 and text not in headlines:
                headlines.append(text)
            if len(headlines) >= limit:
                break

        logger.info("[crawler] 뉴스 %d건 수집", len(headlines))
        return headlines[:limit]
    except Exception as e:
        logger.warning("[crawler] 네이버 뉴스 수집 실패: %s", e)
        return []


# ── yfinance: 모든 지수 통합 ─────────────────────────────────────────

def fetch_all_indices() -> dict:
    """
    KOSPI, KOSDAQ, S&P500, 나스닥, VIX, 달러/원 — yfinance로 통합 수집
    반환: { "KOSPI": {"close": 2645.3, "change_pct": -0.3}, ... }
    """
    try:
        import yfinance as yf

        symbols = {
            "KOSPI":  "^KS11",
            "KOSDAQ": "^KQ11",
            "SP500":  "^GSPC",
            "NASDAQ": "^IXIC",
            "VIX":    "^VIX",
            "USDKRW": "KRW=X",
        }
        result = {}
        for name, sym in symbols.items():
            try:
                hist = yf.Ticker(sym).history(period="2d")
                if hist.empty:
                    continue
                close = float(hist["Close"].iloc[-1])
                prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
                chg   = round((close - prev) / prev * 100, 2) if prev else 0
                result[name] = {"close": round(close, 2), "change_pct": chg}
            except Exception as e:
                logger.debug("[crawler] %s 수집 실패: %s", sym, e)

        logger.info("[crawler] 지수 수집 완료: %s", list(result.keys()))
        return result
    except ImportError:
        logger.warning("[crawler] yfinance 미설치")
        return {}
    except Exception as e:
        logger.warning("[crawler] 지수 수집 실패: %s", e)
        return {}


# ── pykrx: 투자자별 순매수 ──────────────────────────────────────────

def _recent_trading_day() -> str:
    """최근 5거래일 중 데이터가 있는 날 반환"""
    for delta in range(7):
        d = (date.today() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            from pykrx import stock as krx
            df = krx.get_market_trading_value_by_date(d, d, "KOSPI")
            if df is not None and not df.empty and len(df.columns) > 0:
                return d
        except Exception:
            continue
    return (date.today() - timedelta(days=1)).strftime("%Y%m%d")


def fetch_investor_trend() -> dict:
    """KOSPI 투자자별 순매수 (외국인/기관/개인)"""
    try:
        from pykrx import stock as krx
        d = _recent_trading_day()
        df = krx.get_market_trading_value_by_date(d, d, "KOSPI")
        if df is None or df.empty or len(df.columns) == 0:
            return {}

        row = df.iloc[-1]
        trend = {}
        for col, key in [("외국인합계", "foreign"), ("기관합계", "institution"), ("개인", "retail")]:
            if col in row.index:
                trend[key] = int(row[col])
        logger.info("[crawler] 투자자 동향: %s", trend)
        return trend
    except Exception as e:
        logger.warning("[crawler] 투자자 동향 수집 실패 (skip): %s", e)
        return {}


# ── VIX 기반 시장 심리 ───────────────────────────────────────────────

def _market_sentiment(indices: dict) -> str:
    vix = indices.get("VIX", {}).get("close", 0)
    if vix == 0:
        return "알 수 없음"
    if vix > 30:
        return f"극도의 공포 (VIX {vix})"
    if vix > 20:
        return f"공포 (VIX {vix})"
    if vix > 15:
        return f"중립 (VIX {vix})"
    return f"탐욕 (VIX {vix})"


# ── 통합 수집 ────────────────────────────────────────────────────────

def collect_market_context() -> dict:
    """전체 시장 컨텍스트 수집"""
    logger.info("[crawler] 시장 컨텍스트 수집 시작")

    indices = fetch_all_indices()

    ctx = {
        "trading_day":    date.today().strftime("%Y-%m-%d"),
        "news":           fetch_naver_news(limit=10),
        "indices":        indices,            # KOSPI/KOSDAQ/SP500/NASDAQ/VIX/USDKRW 통합
        "investor_trend": fetch_investor_trend(),
        "sentiment":      _market_sentiment(indices),
    }

    logger.info("[crawler] 수집 완료 — 뉴스 %d건, 지수 %d개",
                len(ctx["news"]), len(ctx["indices"]))
    return ctx
