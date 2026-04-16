#!/usr/bin/env python3
"""
PolitiSignal — Political Market Intelligence Fetcher
Sources: .gov RSS, White House, GovTrack, Federal Register, SEC EDGAR,
         Truth Social, Bluesky, YouTube, Reddit, Politico, The Hill
Run every 5 minutes via GitHub Actions.
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

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
MAX_SIGNALS = 100

# ─── TICKER NAMES ─────────────────────────────────────────────────────────────

TICKER_NAMES = {
    "AAPL": "Apple Inc.", "GOOGL": "Alphabet Inc.", "MSFT": "Microsoft Corp.",
    "AMZN": "Amazon.com", "META": "Meta Platforms", "NVDA": "NVIDIA Corp.",
    "TSLA": "Tesla Inc.", "AMD": "Advanced Micro Devices", "INTC": "Intel Corp.",
    "QCOM": "Qualcomm Inc.", "TSM": "Taiwan Semiconductor", "ORCL": "Oracle Corp.",
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "WFC": "Wells Fargo", "C": "Citigroup",
    "BLK": "BlackRock Inc.", "SCHW": "Charles Schwab", "AXP": "American Express",
    "V": "Visa Inc.", "MA": "Mastercard",
    "XOM": "Exxon Mobil", "CVX": "Chevron Corp.", "COP": "ConocoPhillips",
    "SLB": "SLB (Schlumberger)", "HAL": "Halliburton", "OXY": "Occidental Petroleum",
    "LMT": "Lockheed Martin", "RTX": "RTX Corp.", "NOC": "Northrop Grumman",
    "GD": "General Dynamics", "BA": "Boeing Co.", "KTOS": "Kratos Defense",
    "PLTR": "Palantir Technologies", "CACI": "CACI International",
    "SAIC": "Science Applications", "BAH": "Booz Allen Hamilton",
    "LLY": "Eli Lilly", "PFE": "Pfizer Inc.", "JNJ": "Johnson & Johnson",
    "MRK": "Merck & Co.", "ABBV": "AbbVie Inc.", "MRNA": "Moderna Inc.",
    "UNH": "UnitedHealth Group", "HCA": "HCA Healthcare", "CVS": "CVS Health",
    "MDT": "Medtronic", "BMY": "Bristol Myers Squibb",
    "FSLR": "First Solar", "ENPH": "Enphase Energy",
    "COIN": "Coinbase Global", "MSTR": "MicroStrategy",
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
    "DOGE": "Dogecoin", "XRP": "XRP / Ripple",
    "SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF", "DIA": "Dow Jones ETF",
    "IWM": "Russell 2000 ETF", "GLD": "Gold ETF", "TLT": "20yr Treasury ETF",
    "VXX": "Volatility ETF", "ARKK": "ARK Innovation ETF",
    "XLE": "Energy Select ETF", "XLF": "Financial Select ETF",
    "DE": "Deere & Company", "CORN": "Corn ETF", "SOYB": "Soybean ETF",
    "X": "U.S. Steel", "AA": "Alcoa Corp.", "NUE": "Nucor Corp.",
}

# ─── POLITICIANS ─────────────────────────────────────────────────────────────

POLITICIANS = [
    # ── Executive ────────────────────────────────────────────────────────────
    {
        "name": "Donald Trump",
        "initials": "DT",
        "role": "President of the United States",
        "color": {"bg": "#3b1818", "fg": "#f87171"},
        "rss": None,
        "bluesky": None,
        "youtube_channel": "UCAql2DyGU2un1Ei2nMYsqOA",
        "truth_social": "realDonaldTrump",
        "keywords": ["tariff", "china", "trade", "economy", "stock", "deal", "tax", "energy", "oil", "sanction"],
    },
    # ── Senate ───────────────────────────────────────────────────────────────
    {
        "name": "Sen. Elizabeth Warren",
        "initials": "EW",
        "role": "Senate Banking Committee",
        "color": {"bg": "#1b3a2a", "fg": "#4ade80"},
        "rss": "https://warren.senate.gov/rss/",           # verified working
        "bluesky": "elizabethwarren.bsky.social",
        "youtube_channel": "UCxqHrKEtEAFqLiUiD_zhbfQ",
        "truth_social": None,
        "keywords": ["antitrust", "big tech", "amazon", "google", "apple", "bank", "crypto", "wall street"],
    },
    {
        "name": "Sen. Bernie Sanders",
        "initials": "BS",
        "role": "Senate HELP Committee",
        "color": {"bg": "#1e2a4a", "fg": "#818cf8"},
        "rss": "https://www.sanders.senate.gov/rss/",      # verified working
        "bluesky": "sensanders.bsky.social",
        "youtube_channel": "UCH1dpzjCEqy3GFnDES5kCNw",
        "truth_social": None,
        "keywords": ["drug", "pharma", "healthcare", "medicare", "insulin", "price", "insurance"],
    },
    {
        "name": "Sen. Rand Paul",
        "initials": "RP",
        "role": "Senate Foreign Relations Committee",
        "color": {"bg": "#2a1818", "fg": "#fbbf24"},
        "rss": "https://www.paul.senate.gov/rss/",         # verified working
        "bluesky": None,
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["spending", "debt", "fed", "gold", "regulation", "crypto", "liberty"],
    },
    {
        "name": "Sen. Cynthia Lummis",
        "initials": "CL",
        "role": "Senate Banking Subcommittee (Crypto)",
        "color": {"bg": "#1a1a2a", "fg": "#c4b5fd"},
        "rss": "https://www.lummis.senate.gov/press-releases/feed/",
        "bluesky": None,
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["bitcoin", "crypto", "stablecoin", "digital asset", "blockchain"],
    },
    {
        "name": "Sen. Marco Rubio",
        "initials": "MR",
        "role": "Senate Foreign Relations Committee",
        "color": {"bg": "#1e3a5f", "fg": "#60a5fa"},
        "rss": None,                                        # RSS broken, use YouTube
        "bluesky": None,
        "youtube_channel": "UCn3YWMT3D-mXKDYdDpFQnxA",
        "truth_social": None,
        "keywords": ["china", "tariff", "semiconductor", "trade", "taiwan", "military", "sanction"],
    },
    # ── House ────────────────────────────────────────────────────────────────
    {
        "name": "Rep. Nancy Pelosi",
        "initials": "NP",
        "role": "House Democratic Leader",
        "color": {"bg": "#1e2a4a", "fg": "#60a5fa"},
        "rss": "https://pelosi.house.gov/rss.xml",          # verified working
        "bluesky": "nancypelosi.bsky.social",
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["tech", "china", "semiconductor", "climate", "trade", "healthcare"],
    },
    {
        "name": "Rep. Mike Johnson",
        "initials": "MJ",
        "role": "Speaker of the House",
        "color": {"bg": "#2a1a1a", "fg": "#fbbf24"},
        "rss": "https://mikejohnson.house.gov/rss.xml",
        "bluesky": None,
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["budget", "spending", "tax", "debt", "energy", "defense"],
    },
    {
        "name": "Rep. Jim Jordan",
        "initials": "JJ",
        "role": "House Judiciary Committee Chair",
        "color": {"bg": "#2a1818", "fg": "#fca5a5"},
        "rss": "https://jordan.house.gov/rss.xml",          # verified working
        "bluesky": None,
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["big tech", "antitrust", "google", "amazon", "censorship", "doj"],
    },
    {
        "name": "Rep. Alexandria Ocasio-Cortez",
        "initials": "AOC",
        "role": "House Financial Services Committee",
        "color": {"bg": "#1e2a4a", "fg": "#93c5fd"},
        "rss": "https://ocasio-cortez.house.gov/rss.xml",   # verified working
        "bluesky": "aoc.bsky.social",
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["big tech", "green energy", "climate", "bank", "tax", "housing", "crypto"],
    },
    {
        "name": "Rep. Ro Khanna",
        "initials": "RK",
        "role": "House Armed Services Committee",
        "color": {"bg": "#1a2a1a", "fg": "#86efac"},
        "rss": "https://khanna.house.gov/rss.xml",
        "bluesky": "rokhanna.bsky.social",
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["semiconductor", "tech", "china", "defense", "manufacturing", "ai"],
    },
    {
        "name": "Rep. Patrick McHenry",
        "initials": "PM",
        "role": "House Financial Services Committee",
        "color": {"bg": "#2d1e5f", "fg": "#c084fc"},
        "rss": "https://mchenry.house.gov/rss.xml",
        "bluesky": None,
        "youtube_channel": None,
        "truth_social": None,
        "keywords": ["crypto", "stablecoin", "bitcoin", "fintech", "bank", "financial"],
    },
]

# ─── GLOBAL SOURCES (institutional, not individual politicians) ───────────────

GLOBAL_SOURCES = [
    {
        "name": "White House",
        "initials": "WH",
        "role": "Executive Branch",
        "color": {"bg": "#1a1a2a", "fg": "#e2e8f0"},
        "rss": "https://www.whitehouse.gov/news/feed/",
        "platform_key": "whitehouse",
        "keywords": ["tariff", "executive order", "trade", "economy", "energy", "sanction", "china", "deal"],
    },
    {
        "name": "GovTrack",
        "initials": "GT",
        "role": "Congressional Legislation",
        "color": {"bg": "#0a1a2a", "fg": "#7dd3fc"},
        "rss": "https://www.govtrack.us/events/events.rss?feeds=misc:allvotes",
        "platform_key": "govtrack",
        "keywords": ["bill", "act", "legislation", "introduced", "amendment", "tax", "trade", "energy"],
    },
    {
        "name": "Federal Register",
        "initials": "FR",
        "role": "Federal Regulations",
        "color": {"bg": "#0a1a0a", "fg": "#86efac"},
        "rss": "https://www.federalregister.gov/api/v1/documents.rss?conditions[type][]=RULE",
        "platform_key": "federal_register",
        "keywords": ["rule", "regulation", "compliance", "ban", "require", "final rule"],
    },
    {
        "name": "SEC EDGAR",
        "initials": "SEC",
        "role": "Insider & Congressional Stock Trades",
        "color": {"bg": "#0a0a1a", "fg": "#a5b4fc"},
        "rss": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=20&search_text=&output=atom",
        "platform_key": "sec",
        "keywords": ["purchase", "sale", "acquire", "dispose", "insider", "stock", "shares"],
    },
    {
        "name": "U.S. Trade Rep.",
        "initials": "USTR",
        "role": "Office of the U.S. Trade Representative",
        "color": {"bg": "#1a0a1a", "fg": "#d8b4fe"},
        "rss": "https://ustr.gov/rss.xml",
        "platform_key": "ustr",
        "keywords": ["tariff", "trade", "china", "wto", "deal", "agreement", "sanction"],
    },
    {
        "name": "Politico",
        "initials": "PO",
        "role": "Political News",
        "color": {"bg": "#1a0a0a", "fg": "#fca5a5"},
        "rss": "https://rss.politico.com/politics-news.xml",
        "platform_key": "politico",
        "keywords": ["tariff", "trade", "legislation", "bill", "vote", "congress", "senate", "house", "election", "economy"],
    },
    {
        "name": "The Hill",
        "initials": "TH",
        "role": "Political News",
        "color": {"bg": "#0a1a0a", "fg": "#bbf7d0"},
        "rss": "https://thehill.com/rss/syndicator/19109",
        "platform_key": "thehill",
        "keywords": ["tariff", "trade", "legislation", "bill", "vote", "congress", "senate", "house", "economy", "crypto"],
    },
]

# ─── KEYWORD → TICKER MAPPING ─────────────────────────────────────────────────

TICKER_MAP = [
    (["amazon", "amzn", "aws"],                             ["AMZN"]),
    (["google", "googl", "alphabet", "youtube", "waymo"],   ["GOOGL"]),
    (["apple", "aapl", "iphone", "app store", "tim cook"],  ["AAPL"]),
    (["microsoft", "msft", "azure", "openai", "copilot"],   ["MSFT"]),
    (["meta", "facebook", "instagram", "whatsapp", "zuckerberg"], ["META"]),
    (["nvidia", "nvda", "gpu", "ai chip", "jensen huang"],  ["NVDA"]),
    (["tesla", "tsla", "elon musk", "elon", "spacex"],      ["TSLA"]),
    (["palantir", "pltr"],                                   ["PLTR"]),
    (["antitrust", "big tech", "monopol", "divestiture"],   ["AMZN", "GOOGL", "AAPL", "META"]),
    (["semiconductor", "chip", "tsmc", "taiwan"],           ["NVDA", "TSM", "AMD", "QCOM"]),
    (["china", "tariff", "trade war", "export ban"],        ["NVDA", "TSM", "QCOM", "AAPL"]),
    (["bitcoin", "btc", "crypto", "blockchain"],            ["BTC", "ETH", "COIN"]),
    (["stablecoin", "digital asset", "cbdc"],               ["BTC", "ETH", "COIN", "XRP"]),
    (["oil", "drilling", "petroleum", "opec"],              ["XOM", "CVX", "COP", "OXY"]),
    (["energy", "clean energy", "solar", "wind", "climate"],["XOM", "FSLR", "ENPH", "XLE"]),
    (["pharma", "drug", "insulin", "pfizer", "lilly"],      ["LLY", "PFE", "JNJ", "MRK"]),
    (["healthcare", "hospital", "insurance", "medicaid"],   ["UNH", "HCA", "CVS"]),
    (["agriculture", "corn", "soybean", "grain", "farm"],   ["CORN", "SOYB", "DE"]),
    (["bank", "banking", "wall street", "fed ", "interest rate"], ["JPM", "BAC", "GS", "XLF"]),
    (["defense", "military", "weapon", "nato", "pentagon"], ["LMT", "RTX", "NOC", "GD"]),
    (["steel", "aluminum", "metal", "manufacturing"],       ["X", "AA", "NUE"]),
    (["sanction", "russia", "iran", "north korea"],         ["LMT", "RTX", "XOM"]),
    (["regulation", "sec ", "ftc ", "doj "],                ["GOOGL", "AMZN", "META", "AAPL"]),
    (["gold", "silver", "inflation", "bond", "treasury"],   ["GLD", "TLT", "SPY"]),
    (["lockheed", "lmt"],                                   ["LMT"]),
    (["raytheon", "rtx"],                                   ["RTX"]),
    (["boeing"],                                            ["BA"]),
]

SEVERITY_KEYWORDS = {
    "critical": ["legislation", "bill passed", "ban", "tariff", "sanction", "executive order",
                 "introduce", "force", "emergency", "immediately", "existential", "crisis",
                 "signed into law", "effective immediately", "national security"],
    "high":     ["push", "propos", "call for", "demand", "urge", "announce", "confirm",
                 "agreement", "deal", "vote", "pass", "introduced a bill", "new rule", "final rule"],
    "medium":   ["discuss", "meeting", "consider", "review", "study", "support", "oppose",
                 "statement", "hearing", "committee"],
    "low":      ["comment", "note", "mention", "tweet", "post", "remarks"],
}

PLATFORM_LABELS = {
    "rss": ".gov",
    "whitehouse": "White House",
    "govtrack": "GovTrack",
    "federal_register": "Fed. Register",
    "sec": "SEC EDGAR",
    "ustr": "USTR",
    "politico": "Politico",
    "thehill": "The Hill",
    "truthsocial": "Truth Social",
    "bluesky": "Bluesky",
    "youtube": "YouTube",
    "reddit": "Reddit",
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()

def guess_tickers(text: str) -> list:
    text_lower = text.lower()
    tickers = []
    for keywords, t in TICKER_MAP:
        if any(k in text_lower for k in keywords):
            tickers.extend(t)
    return list(dict.fromkeys(tickers))[:5]

def guess_severity(text: str, source: dict) -> str:
    text_lower = text.lower()
    is_high_authority = any(x in source.get("role", "").lower()
                            for x in ["president", "chair", "leader", "speaker", "secretary", "representative"])
    for level in ["critical", "high", "medium", "low"]:
        if any(k in text_lower for k in SEVERITY_KEYWORDS[level]):
            if is_high_authority and level == "high":
                return "critical"
            if is_high_authority and level == "medium":
                return "high"
            return level
    return "medium"

def extract_tags(text: str, source: dict) -> list:
    tags = []
    text_lower = text.lower()
    tag_map = {
        "Antitrust": ["antitrust", "monopol"],
        "Big Tech": ["big tech", "amazon", "google", "apple", "facebook", "meta"],
        "Trade": ["trade", "tariff", "export", "import", "wto"],
        "China": ["china", "chinese", "prc", "beijing"],
        "Semiconductors": ["semiconductor", "chip", "gpu", "tsmc"],
        "Crypto": ["crypto", "bitcoin", "stablecoin", "blockchain", "digital asset"],
        "Energy": ["energy", "oil", "drilling", "solar", "wind", "climate"],
        "Healthcare": ["healthcare", "medicare", "drug", "pharma", "insulin", "hospital"],
        "Agriculture": ["agriculture", "corn", "soybean", "farm"],
        "Banking": ["bank", "wall street", "federal reserve", "interest rate"],
        "Defense": ["defense", "military", "nato", "weapon", "pentagon"],
        "Regulation": ["regulation", "legislation", "bill", "law", "rule", "compliance"],
        "Taxes": ["tax", "irs", "revenue"],
        "Sanctions": ["sanction", "russia", "iran", "embargo"],
        "Insider Trade": ["purchase", "sale", "acquired", "disposed", "sec form 4"],
    }
    for tag, keywords in tag_map.items():
        if any(k in text_lower for k in keywords):
            tags.append(tag)
    return tags[:4]

def time_ago(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - dt
    secs = int(diff.total_seconds())
    if secs < 0:      return "just now"
    if secs < 60:     return "just now"
    if secs < 3600:   return f"{secs // 60}m ago"
    if secs < 86400:  return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"

def make_signal(source: dict, content: str, platform: str, url: str = "", published: Optional[datetime] = None) -> dict:
    tickers = guess_tickers(content) or guess_tickers(" ".join(source.get("keywords", [])))
    severity = guess_severity(content, source)
    pub = published or datetime.now(timezone.utc)
    return {
        "id": make_id(content[:80] + source["initials"]),
        "politician": source["name"],
        "initials": source["initials"],
        "role": source["role"],
        "color": source["color"],
        "severity": severity,
        "content": content[:320],
        "tags": extract_tags(content, source),
        "tickers": tickers,
        "source": platform,
        "platform": PLATFORM_LABELS.get(platform, platform),
        "url": url,
        "published_iso": pub.isoformat() if hasattr(pub, 'isoformat') else now_iso(),
        "time_ago": time_ago(pub) if hasattr(pub, 'replace') else "recently",
    }

# ─── FETCHERS ─────────────────────────────────────────────────────────────────

def fetch_rss_source(source: dict, platform_key: str = "rss", max_entries: int = 5) -> list:
    url = source.get("rss")
    if not url:
        return []
    signals = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "PolitiSignal/1.0 (hello@politisignal.com)"})
        for entry in feed.entries[:max_entries]:
            content = strip_html(entry.get("summary", entry.get("title", "")))
            title = entry.get("title", "")
            full_text = f"{title}. {content}".strip(". ")
            if len(full_text) < 20:
                continue
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
            link = entry.get("link", "")
            signals.append(make_signal(source, full_text, platform_key, link, published))
        print(f"  RSS [{source['initials']}]: {len(signals)} entries")
    except Exception as e:
        print(f"  RSS [{source['initials']}] error: {e}")
    return signals


def fetch_truth_social(source: dict) -> list:
    username = source.get("truth_social")
    if not username:
        return []
    signals = []
    try:
        r = requests.get(
            "https://truthsocial.com/api/v1/accounts/search",
            params={"q": username, "limit": 1},
            headers={"User-Agent": "PolitiSignal/1.0"},
            timeout=10,
        )
        if r.status_code != 200 or not r.json():
            return []
        account_id = r.json()[0]["id"]
        r2 = requests.get(
            f"https://truthsocial.com/api/v1/accounts/{account_id}/statuses",
            params={"limit": 5, "exclude_replies": True},
            headers={"User-Agent": "PolitiSignal/1.0"},
            timeout=10,
        )
        if r2.status_code != 200:
            return []
        for status in r2.json():
            content = strip_html(status.get("content", ""))
            if len(content) < 20:
                continue
            published = datetime.fromisoformat(status["created_at"].replace("Z", "+00:00"))
            url = status.get("url", "")
            signals.append(make_signal(source, content, "truthsocial", url, published))
        print(f"  Truth Social [{source['initials']}]: {len(signals)} posts")
    except Exception as e:
        print(f"  Truth Social [{source['initials']}] error: {e}")
    return signals


def fetch_youtube(source: dict) -> list:
    channel_id = source.get("youtube_channel")
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
            signals.append(make_signal(source, content, "youtube", url, published))
        print(f"  YouTube [{source['initials']}]: {len(signals)} videos")
    except Exception as e:
        print(f"  YouTube [{source['initials']}] error: {e}")
    return signals


def fetch_bluesky(source: dict) -> list:
    handle = source.get("bluesky")
    if not handle:
        return []
    signals = []
    try:
        r = requests.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
            params={"actor": handle, "limit": 10},
            headers={"User-Agent": "PolitiSignal/1.0"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  Bluesky [{source['initials']}]: HTTP {r.status_code}")
            return []
        posts = r.json().get("feed", [])
        for item in posts[:5]:
            post = item.get("post", {})
            record = post.get("record", {})
            text = record.get("text", "")
            if len(text) < 20:
                continue
            created_at = record.get("createdAt", "")
            published = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
            uri = post.get("uri", "")
            rkey = uri.split("/")[-1] if uri else ""
            url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
            signals.append(make_signal(source, text, "bluesky", url, published))
        print(f"  Bluesky [{source['initials']}]: {len(signals)} posts")
    except Exception as e:
        print(f"  Bluesky [{source['initials']}] error: {e}")
    return signals


def fetch_reddit(subreddit: str, limit: int = 8) -> list:
    """Fetch market-relevant posts from Reddit (free, no auth needed)."""
    signals = []
    reddit_source = {
        "name": f"r/{subreddit}",
        "initials": "r/",
        "role": "Reddit Community",
        "color": {"bg": "#1a0f00", "fg": "#fb923c"},
        "keywords": [],
    }
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": limit},
            headers={"User-Agent": "PolitiSignal/1.0 (hello@politisignal.com)"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  Reddit r/{subreddit}: HTTP {r.status_code}")
            return []
        for post in r.json()["data"]["children"]:
            data = post["data"]
            if data.get("stickied"):
                continue
            title = data.get("title", "")
            selftext = strip_html(data.get("selftext", ""))[:200]
            content = f"{title}. {selftext}".strip(". ")
            if len(content) < 30:
                continue
            tickers = guess_tickers(content)
            if not tickers and subreddit not in ["politics", "worldnews"]:
                continue  # Only include market-relevant posts for financial subreddits
            url = f"https://reddit.com{data.get('permalink', '')}"
            created = datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc)
            signals.append({
                "id": make_id(title + subreddit),
                "politician": f"r/{subreddit}",
                "initials": "r/",
                "role": "Reddit Community",
                "color": {"bg": "#1a0f00", "fg": "#fb923c"},
                "severity": "low",
                "content": content[:320],
                "tags": extract_tags(content, reddit_source),
                "tickers": tickers,
                "source": "reddit",
                "platform": "Reddit",
                "url": url,
                "published_iso": created.isoformat(),
                "time_ago": time_ago(created),
            })
        print(f"  Reddit r/{subreddit}: {len(signals)} relevant posts")
    except Exception as e:
        print(f"  Reddit r/{subreddit} error: {e}")
    return signals


# ─── CRYPTO SYMBOL MAP ────────────────────────────────────────────────────────

YFINANCE_MAP = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
    "DOGE": "DOGE-USD", "XRP": "XRP-USD",
}

# Comprehensive watchlist — always fetch prices for these regardless of signals
ALWAYS_FETCH = [
    "SPY", "QQQ", "DIA", "IWM",          # Indices
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",  # Mega cap tech
    "JPM", "BAC", "GS",                    # Banks
    "XOM", "CVX",                          # Energy
    "LMT", "RTX", "NOC",                   # Defense
    "LLY", "PFE", "JNJ",                   # Pharma
    "BTC", "ETH",                          # Crypto
    "GLD", "TLT",                          # Macro
    "PLTR", "COIN",                        # Political favorites
]

# ─── STOCK PRICES ─────────────────────────────────────────────────────────────

def fetch_stock_prices(signals: list) -> dict:
    """Fetch real-time prices from Yahoo Finance for all tickers."""
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed, skipping prices")
        return {}

    # Collect tickers from signals + always-fetch list
    signal_tickers = list(dict.fromkeys(t for s in signals for t in s.get("tickers", [])))
    all_tickers = list(dict.fromkeys(ALWAYS_FETCH + signal_tickers))

    print(f"\nFetching prices for {len(all_tickers)} tickers...")
    prices = {}

    yf_symbols = {t: YFINANCE_MAP.get(t, t) for t in all_tickers}
    symbols_list = list(set(yf_symbols.values()))

    try:
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
                    "price": round(curr, 4 if curr < 1 else 2),
                    "change_pct": round(change_pct, 2),
                    "name": TICKER_NAMES.get(ticker, ticker),
                    "_updated": now_iso(),
                }
                arrow = "▲" if change_pct >= 0 else "▼"
                print(f"  {ticker}: ${curr:.2f} {arrow}{abs(change_pct):.2f}%")
            except Exception as e:
                print(f"  {ticker} error: {e}")

    except Exception as e:
        print(f"  Batch download error: {e}")
        # Individual fallback
        for ticker, yf_sym in yf_symbols.items():
            try:
                t_obj = yf.Ticker(yf_sym)
                fi = t_obj.fast_info
                curr = float(fi.last_price)
                prev = float(fi.previous_close)
                if curr and prev and prev > 0:
                    change_pct = (curr - prev) / prev * 100
                    prices[ticker] = {
                        "price": round(curr, 4 if curr < 1 else 2),
                        "change_pct": round(change_pct, 2),
                        "name": TICKER_NAMES.get(ticker, ticker),
                        "_updated": now_iso(),
                    }
            except Exception:
                pass

    print(f"  Prices fetched: {len(prices)} tickers")
    return prices


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"PolitiSignal fetch started at {now_iso()}")
    print(f"{'='*60}\n")
    all_signals = []

    # Individual politicians
    print("── Politicians ──────────────────────────────────────────")
    for pol in POLITICIANS:
        print(f"\nFetching {pol['name']}...")
        all_signals.extend(fetch_rss_source(pol, "rss"))
        all_signals.extend(fetch_truth_social(pol))
        all_signals.extend(fetch_bluesky(pol))
        all_signals.extend(fetch_youtube(pol))

    # Global institutional sources
    print("\n── Institutional Sources ────────────────────────────────")
    for src in GLOBAL_SOURCES:
        print(f"\nFetching {src['name']}...")
        key = src.get("platform_key", "rss")
        all_signals.extend(fetch_rss_source(src, key, max_entries=8))

    # Reddit (free, no API key)
    print("\n── Reddit ───────────────────────────────────────────────")
    all_signals.extend(fetch_reddit("politics", limit=10))
    all_signals.extend(fetch_reddit("investing", limit=8))
    all_signals.extend(fetch_reddit("wallstreetbets", limit=5))
    all_signals.extend(fetch_reddit("StockMarket", limit=5))

    # Sort by published date, newest first
    def sort_key(s):
        try:
            return datetime.fromisoformat(s.get("published_iso", "2000-01-01T00:00:00+00:00"))
        except Exception:
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

    with open(os.path.join(base, "data", "signals.json"), "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n{'='*60}")
    print(f"Signals: {len(result)} written to data/signals.json")

    prices = fetch_stock_prices(result)
    with open(os.path.join(base, "data", "prices.json"), "w") as f:
        json.dump(prices, f, indent=2)
    print(f"Prices:  {len(prices)} tickers written to data/prices.json")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
