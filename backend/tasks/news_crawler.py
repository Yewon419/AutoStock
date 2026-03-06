"""
시장 컨텍스트 수집기
- pykrx  : KOSPI/KOSDAQ 지수, 투자자별 매매 동향, 섹터별 등락
- yfinance: S&P500, 나스닥, VIX, 달러/원 환율
- 네이버 금융 뉴스: 시장 헤드라인 크롤링

반환값: MarketContext dict — llm_strategy.py에서 프롬프트 빌딩에 사용
"""
import logging
from datetime import date, timedelta
from typing import Optional

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
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        headlines = []
        for a in soup.select("dl dd.articleSubject a"):
            text = a.get_text(strip=True)
            if text and len(text) > 5:
                headlines.append(text)
            if len(headlines) >= limit:
                break

        # fallback: 다른 셀렉터
        if not headlines:
            for a in soup.select(".newsList .articleSubject a, .newsList a"):
                text = a.get_text(strip=True)
                if text and len(text) > 5:
                    headlines.append(text)
                if len(headlines) >= limit:
                    break

        logger.info("[crawler] 뉴스 %d건 수집", len(headlines))
        return headlines[:limit]
    except Exception as e:
        logger.warning("[crawler] 네이버 뉴스 수집 실패: %s", e)
        return []


# ── pykrx: 지수 / 투자자 동향 / 섹터 ───────────────────────────────

def _recent_trading_day() -> str:
    """pykrx용 최근 거래일 (오늘 포함 최근 5일 중 첫 번째 성공일)"""
    from pykrx import stock as krx
    for delta in range(5):
        d = (date.today() - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            df = krx.get_index_ohlcv_by_date(d, d, "1001")  # KOSPI
            if not df.empty:
                return d
        except Exception:
            continue
    return date.today().strftime("%Y%m%d")


def fetch_krx_indices(trading_day: Optional[str] = None) -> dict:
    """KOSPI / KOSDAQ 지수 현황"""
    try:
        from pykrx import stock as krx
        d = trading_day or _recent_trading_day()

        result = {}
        for name, idx_code in [("KOSPI", "1001"), ("KOSDAQ", "2001")]:
            df = krx.get_index_ohlcv_by_date(d, d, idx_code)
            if df.empty:
                continue
            row = df.iloc[-1]
            close = float(row["종가"])
            open_ = float(row["시가"])
            chg_pct = round((close - open_) / open_ * 100, 2) if open_ else 0
            result[name] = {"close": close, "change_pct": chg_pct}

        logger.info("[crawler] KRX 지수: %s", result)
        return result
    except Exception as e:
        logger.warning("[crawler] KRX 지수 수집 실패: %s", e)
        return {}


def fetch_investor_trend(trading_day: Optional[str] = None) -> dict:
    """KOSPI 투자자별 순매수 (외국인/기관/개인)"""
    try:
        from pykrx import stock as krx
        d = trading_day or _recent_trading_day()

        df = krx.get_market_trading_value_by_date(d, d, "KOSPI")
        if df.empty:
            return {}

        row = df.iloc[-1]
        trend = {}
        for col, key in [("외국인합계", "foreign"), ("기관합계", "institution"), ("개인", "retail")]:
            if col in row:
                trend[key] = int(row[col])

        logger.info("[crawler] 투자자 동향: %s", trend)
        return trend
    except Exception as e:
        logger.warning("[crawler] 투자자 동향 수집 실패: %s", e)
        return {}


def fetch_sector_trend(trading_day: Optional[str] = None) -> dict:
    """KOSPI 섹터별 등락률 상위/하위 3개"""
    try:
        from pykrx import stock as krx
        d = trading_day or _recent_trading_day()

        df = krx.get_index_ohlcv_by_date(d, d, "1028")  # KRX 섹터 인덱스
        if df.empty:
            # 대안: 업종 지수
            df = krx.get_index_portfolio_deposit_file("1028")

        # 섹터별 개별 조회
        sector_codes = {
            "에너지": "1015", "소재": "1016", "산업재": "1017",
            "경기소비재": "1018", "필수소비재": "1019", "건강관리": "1020",
            "금융": "1021", "IT": "1022", "통신서비스": "1023", "유틸리티": "1024",
        }
        sector_changes = {}
        for name, code in sector_codes.items():
            try:
                sdf = krx.get_index_ohlcv_by_date(d, d, code)
                if not sdf.empty:
                    row = sdf.iloc[-1]
                    close = float(row["종가"])
                    open_ = float(row["시가"])
                    chg = round((close - open_) / open_ * 100, 2) if open_ else 0
                    sector_changes[name] = chg
            except Exception:
                continue

        if not sector_changes:
            return {}

        sorted_sectors = sorted(sector_changes.items(), key=lambda x: x[1], reverse=True)
        return {
            "top": sorted_sectors[:3],
            "bottom": sorted_sectors[-3:],
        }
    except Exception as e:
        logger.warning("[crawler] 섹터 동향 수집 실패: %s", e)
        return {}


# ── yfinance: 미국 지수 / VIX / 환율 ────────────────────────────────

def fetch_global_indices() -> dict:
    """S&P500, 나스닥, VIX, 달러/원 환율"""
    try:
        import yfinance as yf

        symbols = {
            "SP500":  "^GSPC",
            "NASDAQ": "^IXIC",
            "VIX":    "^VIX",
            "USDKRW": "KRW=X",
        }
        result = {}
        for name, symbol in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d")
                if hist.empty:
                    continue
                close = float(hist["Close"].iloc[-1])
                prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else close
                chg_pct = round((close - prev) / prev * 100, 2) if prev else 0
                result[name] = {"close": round(close, 2), "change_pct": chg_pct}
            except Exception as e:
                logger.debug("[crawler] %s 수집 실패: %s", symbol, e)

        logger.info("[crawler] 글로벌 지수: %s", result)
        return result
    except ImportError:
        logger.warning("[crawler] yfinance 미설치 — 글로벌 지수 생략")
        return {}
    except Exception as e:
        logger.warning("[crawler] 글로벌 지수 수집 실패: %s", e)
        return {}


# ── 통합 수집 ────────────────────────────────────────────────────────

def collect_market_context() -> dict:
    """
    전체 시장 컨텍스트 수집 후 dict 반환.
    llm_strategy.py의 프롬프트 빌더에서 사용.
    """
    trading_day = _recent_trading_day()
    logger.info("[crawler] 시장 컨텍스트 수집 시작 (기준일: %s)", trading_day)

    ctx = {
        "trading_day":    trading_day,
        "news":           fetch_naver_news(limit=10),
        "krx_indices":    fetch_krx_indices(trading_day),
        "investor_trend": fetch_investor_trend(trading_day),
        "sector_trend":   fetch_sector_trend(trading_day),
        "global_indices": fetch_global_indices(),
    }

    logger.info("[crawler] 수집 완료 — 뉴스 %d건, 지수 %d개",
                len(ctx["news"]), len(ctx["krx_indices"]))
    return ctx
