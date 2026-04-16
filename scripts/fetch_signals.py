#!/usr/bin/env python3
"""
PolitiSignal — Free Social Media Fetcher
Sources: .gov RSS feeds, Truth Social (Mastodon API), YouTube Data API
Run every 10 minutes via GitHub Actions.
"""

import json
import os
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

import requests
import feedparser

# ─── CONFIG ──────────────────────────────────────────────────────────────────

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")  # Set in GitHub Secrets
MAX_SIGNALS = 50  # Keep latest 50 signals in the JSON

# ─── POLITICIANS ─────────────────────────────────────────────────────────────

POLITICIANS = [
    {
        "name": "Sen. Elizabeth Warren",
        "initials": "EW",
        "role": "Senate Banking Committee Chair",
        "color": {"bg": "#1b3a2a", "fg": "#4ade80"},
        "rss": "https://www.warren.senate.gov/newsroom/press-releases/rss/feed/",
        "youtube_channel": "UCxqHrKEtEAFqLiUiD_zhbfQ",
        "truth_social": None,
        "keywords": ["antitrust", "big tech", "amazon", "google", "apple", "bank", "wall street", "crypto"],
    },
    {
        "name": "Sen. Marco Rubio",
        "initials": "MR",
        "role": "Senate Foreign Relations Committee",
        "color": {"bg": "#1e3a5f", "fg": "#60a5fa"},
        "rss": "https://www.rubio.senate.gov/public/index.cfm/press-releases?ContentType_id=&MonthDisplay=0&YearDisplay=0&format=RSS",
        "youtube_channel": "UCn3YWMT3D-mXKDYdDpFQnxA",
        "truth_social": None,
        "keywords": ["china", "tariff", "semiconductor", "trade", "taiwan", "military", "sanctions"],
    },
    {
        "name": "Sen. Bernie Sanders",
        "initials": "BS",
        "role": "Senate HELP Committee Chair",
        "color": {"bg": "#1e2a4a", "fg": "#818cf8"},
        "rss": "https://www.sanders.senate.gov/latest-news/feed/",
        "youtube_channel": "UCH1dpzjCEqy3GFnDES5kCNw",
        "truth_social": None,
        "keywords": ["drug", "pharma", "healthcare", "medicare", "insulin", "price", "insurance"],
    },
    {
        "name": "Rep. Kevin Hern",
        "initials": "KH",
        "role": "House Agriculture Committee",
        "color": {"bg": "#2a1f0a", "fg": "#fbbf24"},
        "rss": "https://hern.house.gov/rss.xml",
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["oil", "energy", "drilling", "subsidy", "clean energy", "agriculture"],
    },
    {
        "name": "Rep. Patrick McHenry",
        "initials": "PM",
        "role": "House Financial Services Committee",
        "color": {"bg": "#2d1e5f", "fg": "#c084fc"},
        "rss": "https://mchenry.house.gov/rss.xml",
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["crypto", "stablecoin", "bitcoin", "fintech", "bank", "financial"],
    },
    {
        "name": "Donald Trump",
        "initials": "DT",
        "role": "President of the United States",
        "color": {"bg": "#3b1818", "fg": "#f87171"},
        "rss": None,
        "youtube_channel": "UCAql2DyGU2un1Ei2nMYsqOA",
        "truth_social": "realDonaldTrump",
        "keywords": ["tariff", "china", "trade", "economy", "stock", "deal", "tax", "energy", "oil"],
    },
]

# ─── KEYWORD → TICKER MAPPING ─────────────────────────────────────────────────

TICKER_MAP = [
    (["amazon", "amzn", "aws"],                          ["AMZN"]),
    (["google", "googl", "alphabet", "youtube"],         ["GOOGL"]),
    (["apple", "aapl", "iphone"],                        ["AAPL"]),
    (["meta", "facebook", "instagram", "whatsapp"],      ["META"]),
    (["antitrust", "big tech", "monopol", "divestiture"],["AMZN", "GOOGL", "AAPL", "META"]),
    (["nvidia", "nvda", "gpu", "ai chip"],               ["NVDA"]),
    (["semiconductor", "chip", "tsmc", "taiwan"],        ["NVDA", "TSM", "AMD", "QCOM"]),
    (["china", "tariff", "trade war", "export ban"],     ["NVDA", "TSM", "QCOM", "AAPL"]),
    (["bitcoin", "btc", "crypto", "stablecoin", "coin"], ["BTC", "ETH", "COIN"]),
    (["oil", "drilling", "petroleum", "opec"],           ["XOM", "CVX"]),
    (["energy", "clean energy", "solar", "subsidy"],     ["XOM", "FSLR", "ENPH"]),
    (["pharma", "drug", "insulin", "medicare", "pfizer", "lilly"], ["LLY", "PFE", "JNJ", "MRK"]),
    (["healthcare", "hospital", "insurance", "medicaid"],["UNH", "HCA", "CVS"]),
    (["agriculture", "corn", "soybean", "grain", "farm"],["CORN", "SOYB", "DE"]),
    (["bank", "banking", "wall street", "fed ", "interest rate"], ["JPM", "BAC", "GS"]),
    (["defense", "military", "weapon", "nato"],          ["LMT", "RTX", "NOC"]),
    (["steel", "aluminum", "metal", "manufacturing"],    ["X", "AA", "NUE"]),
]

SEVERITY_KEYWORDS = {
    "critical": ["legislation", "bill", "ban", "tariff", "sanction", "executive order",
                 "introduce", "force", "must", "emergency", "immediately", "existential"],
    "high":     ["push", "propos", "call for", "demand", "urge", "announce", "confirm",
                 "agreement", "deal", "vote", "pass"],
    "medium":   ["discuss", "meeting", "consider", "review", "study", "support", "oppose"],
    "low":      ["statement", "comment", "note", "mention", "tweet", "post"],
}

PLATFORM_LABELS = {
    "rss": ".gov",
    "truthsocial": "Truth Social",
    "youtube": "YouTube",
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def guess_tickers(text: str) -> list[str]:
    text_lower = text.lower()
    tickers = []
    for keywords, t in TICKER_MAP:
        if any(k in text_lower for k in keywords):
            tickers.extend(t)
    return list(dict.fromkeys(tickers))[:5]  # dedupe, max 5

def guess_severity(text: str, politician: dict) -> str:
    text_lower = text.lower()
    # Committee chairs get bumped up a severity level
    is_chair = "chair" in politician["role"].lower() or "president" in politician["role"].lower()
    for level in ["critical", "high", "medium", "low"]:
        if any(k in text_lower for k in SEVERITY_KEYWORDS[level]):
            if is_chair and level == "high":
                return "critical"
            if is_chair and level == "medium":
                return "high"
            return level
    return "medium"

def extract_tags(text: str, politician: dict) -> list[str]:
    tags = []
    text_lower = text.lower()
    tag_map = {
        "Antitrust": ["antitrust", "monopol"],
        "Big Tech": ["big tech", "amazon", "google", "apple"],
        "Trade": ["trade", "tariff", "export", "import"],
        "China": ["china", "chinese"],
        "Semiconductors": ["semiconductor", "chip", "gpu"],
        "Crypto": ["crypto", "bitcoin", "stablecoin"],
        "Energy": ["energy", "oil", "drilling", "solar"],
        "Healthcare": ["healthcare", "medicare", "drug", "pharma", "insulin"],
        "Agriculture": ["agriculture", "corn", "soybean", "farm"],
        "Banking": ["bank", "wall street", "fed"],
        "Defense": ["defense", "military", "nato"],
        "Regulation": ["regulation", "legislation", "bill", "law"],
        "Taxes": ["tax", "tariff"],
        "Bipartisan": ["bipartisan"],
    }
    for tag, keywords in tag_map.items():
        if any(k in text_lower for k in keywords):
            tags.append(tag)
    return tags[:4]

def time_ago(dt: datetime) -> str:
    diff = datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else datetime.now(timezone.utc) - dt
    secs = int(diff.total_seconds())
    if secs < 60:    return "just now"
    if secs < 3600:  return f"{secs // 60} min ago"
    if secs < 86400: return f"{secs // 3600} hr ago"
    return f"{secs // 86400}d ago"

def make_signal(politician: dict, content: str, source: str, url: str = "", published: Optional[datetime] = None) -> dict:
    tickers = guess_tickers(content) or guess_tickers(" ".join(politician["keywords"]))
    severity = guess_severity(content, politician)
    pub = published or datetime.now(timezone.utc)
    return {
        "id": make_id(content[:80] + politician["initials"]),
        "politician": politician["name"],
        "initials": politician["initials"],
        "role": politician["role"],
        "color": politician["color"],
        "severity": severity,
        "content": content[:280],
        "tags": extract_tags(content, politician),
        "tickers": tickers,
        "source": source,
        "platform": PLATFORM_LABELS.get(source, source),
        "url": url,
        "published_iso": pub.isoformat() if hasattr(pub, 'isoformat') else now_iso(),
        "time_ago": time_ago(pub) if hasattr(pub, 'replace') else "recently",
    }

# ─── FETCHERS ─────────────────────────────────────────────────────────────────

def fetch_rss(politician: dict) -> list[dict]:
    url = politician.get("rss")
    if not url:
        return []
    signals = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            content = entry.get("summary", entry.get("title", ""))
            # Strip HTML tags
            content = re.sub(r"<[^>]+>", " ", content).strip()
            title = entry.get("title", "")
            full_text = f"{title}. {content}"
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            link = entry.get("link", "")
            signals.append(make_signal(politician, full_text, "rss", link, published))
        print(f"  RSS [{politician['initials']}]: {len(signals)} entries")
    except Exception as e:
        print(f"  RSS [{politician['initials']}] error: {e}")
    return signals


def fetch_truth_social(politician: dict) -> list[dict]:
    username = politician.get("truth_social")
    if not username:
        return []
    signals = []
    try:
        # Look up account ID
        r = requests.get(
            f"https://truthsocial.com/api/v1/accounts/search",
            params={"q": username, "limit": 1},
            headers={"User-Agent": "PolitiSignal/1.0"},
            timeout=10,
        )
        if r.status_code != 200 or not r.json():
            return []
        account_id = r.json()[0]["id"]

        # Fetch statuses
        r2 = requests.get(
            f"https://truthsocial.com/api/v1/accounts/{account_id}/statuses",
            params={"limit": 5, "exclude_replies": True},
            headers={"User-Agent": "PolitiSignal/1.0"},
            timeout=10,
        )
        if r2.status_code != 200:
            return []
        for status in r2.json():
            content = re.sub(r"<[^>]+>", " ", status.get("content", "")).strip()
            if len(content) < 20:
                continue
            published = datetime.fromisoformat(status["created_at"].replace("Z", "+00:00"))
            url = status.get("url", "")
            signals.append(make_signal(politician, content, "truthsocial", url, published))
        print(f"  Truth Social [{politician['initials']}]: {len(signals)} posts")
    except Exception as e:
        print(f"  Truth Social [{politician['initials']}] error: {e}")
    return signals


def fetch_youtube(politician: dict) -> list[dict]:
    channel_id = politician.get("youtube_channel")
    if not channel_id or not YOUTUBE_API_KEY:
        return []
    signals = []
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": YOUTUBE_API_KEY,
                "channelId": channel_id,
                "part": "snippet",
                "order": "date",
                "maxResults": 3,
                "type": "video",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return []
        for item in r.json().get("items", []):
            snippet = item["snippet"]
            title = snippet.get("title", "")
            desc = snippet.get("description", "")[:200]
            content = f"{title}. {desc}"
            published_str = snippet.get("publishedAt", "")
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00")) if published_str else None
            url = f"https://youtube.com/watch?v={item['id']['videoId']}"
            signals.append(make_signal(politician, content, "youtube", url, published))
        print(f"  YouTube [{politician['initials']}]: {len(signals)} videos")
    except Exception as e:
        print(f"  YouTube [{politician['initials']}] error: {e}")
    return signals

# ─── CRYPTO SYMBOL MAP (yfinance uses BTC-USD etc.) ──────────────────────────

YFINANCE_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "DOGE": "DOGE-USD",
}

# ─── STOCK PRICES ─────────────────────────────────────────────────────────────

def fetch_stock_prices(signals: list[dict]) -> dict:
    """Fetch real prices from Yahoo Finance for all tickers in signals."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed, skipping prices")
        return {}

    tickers = list(dict.fromkeys(t for s in signals for t in s.get("tickers", [])))
    if not tickers:
        return {}

    print(f"\nFetching prices for: {', '.join(tickers)}")
    prices = {}

    # Map tickers to yfinance symbols
    yf_symbols = {t: YFINANCE_MAP.get(t, t) for t in tickers}
    symbols_list = list(yf_symbols.values())

    try:
        # Batch download 2 days of data
        raw = yf.download(
            symbols_list,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )

        for ticker, yf_sym in yf_symbols.items():
            try:
                if len(symbols_list) == 1:
                    closes = raw["Close"].dropna()
                else:
                    closes = raw[yf_sym]["Close"].dropna()

                if len(closes) < 2:
                    continue

                curr = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                if prev <= 0:
                    continue

                change_pct = (curr - prev) / prev * 100
                prices[ticker] = {
                    "price": round(curr, 2),
                    "change_pct": round(change_pct, 2),
                    "name": TICKER_NAMES.get(ticker, ticker),
                }
                direction = "▲" if change_pct >= 0 else "▼"
                print(f"  {ticker}: ${curr:.2f} {direction}{abs(change_pct):.2f}%")
            except Exception as e:
                print(f"  {ticker} price error: {e}")

    except Exception as e:
        print(f"  Batch price fetch error: {e}")
        # Fallback: individual fetches
        for ticker, yf_sym in yf_symbols.items():
            try:
                t_obj = yf.Ticker(yf_sym)
                fi = t_obj.fast_info
                curr = float(fi.last_price)
                prev = float(fi.previous_close)
                if curr and prev and prev > 0:
                    change_pct = (curr - prev) / prev * 100
                    prices[ticker] = {
                        "price": round(curr, 2),
                        "change_pct": round(change_pct, 2),
                        "name": TICKER_NAMES.get(ticker, ticker),
                    }
                    print(f"  {ticker}: ${curr:.2f} ({change_pct:+.2f}%)")
            except Exception as e2:
                print(f"  {ticker} fallback error: {e2}")

    prices["_updated"] = now_iso()
    print(f"  Prices fetched: {len(prices) - 1} tickers")
    return prices


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"PolitiSignal fetch started at {now_iso()}")
    all_signals = []

    for pol in POLITICIANS:
        print(f"Fetching {pol['name']}...")
        all_signals.extend(fetch_rss(pol))
        all_signals.extend(fetch_truth_social(pol))
        all_signals.extend(fetch_youtube(pol))

    # Sort by published date, newest first
    def sort_key(s):
        try:
            return datetime.fromisoformat(s.get("published_iso", "2000-01-01T00:00:00+00:00"))
        except:
            return datetime.min.replace(tzinfo=timezone.utc)

    all_signals.sort(key=sort_key, reverse=True)

    # Dedupe by ID
    seen = set()
    unique = []
    for s in all_signals:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)

    result = unique[:MAX_SIGNALS]

    base = os.path.join(os.path.dirname(__file__), "..")

    # Write signals
    with open(os.path.join(base, "data", "signals.json"), "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nSignals: {len(result)} written to data/signals.json")

    # Fetch and write real stock prices
    prices = fetch_stock_prices(result)
    with open(os.path.join(base, "data", "prices.json"), "w") as f:
        json.dump(prices, f, indent=2)
    print(f"Prices: {len(prices) - 1} tickers written to data/prices.json")

if __name__ == "__main__":
    main()
