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
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests
import feedparser

# ─── CONFIG ──────────────────────────────────────────────────────────────────

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
MAX_SIGNALS = 100

# ─── TICKER NAMES (expanded — all major S&P sectors) ─────────────────────────

TICKER_NAMES = {
    # ── Mega-cap tech ─────────────────────────────────────────────────────────
    "AAPL": "Apple", "GOOGL": "Alphabet", "MSFT": "Microsoft",
    "AMZN": "Amazon", "META": "Meta Platforms", "NVDA": "NVIDIA",
    "TSLA": "Tesla", "AMD": "Advanced Micro Devices", "INTC": "Intel",
    "QCOM": "Qualcomm", "TSM": "Taiwan Semiconductor", "ORCL": "Oracle",
    "AVGO": "Broadcom", "TXN": "Texas Instruments", "MU": "Micron",
    "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA Corp",
    "ASML": "ASML", "CRM": "Salesforce", "ADBE": "Adobe",
    "NOW": "ServiceNow", "SNOW": "Snowflake", "PLTR": "Palantir",
    "CRWD": "CrowdStrike", "PANW": "Palo Alto Networks", "NET": "Cloudflare",
    "DDOG": "Datadog", "OKTA": "Okta", "ZS": "Zscaler",
    "UBER": "Uber", "LYFT": "Lyft", "ABNB": "Airbnb",
    "NFLX": "Netflix", "SPOT": "Spotify", "RBLX": "Roblox",
    "SHOP": "Shopify", "PYPL": "PayPal", "SQ": "Block",
    "INTU": "Intuit", "WDAY": "Workday", "HUBS": "HubSpot",
    "IBM": "IBM", "CSCO": "Cisco", "HPQ": "HP Inc", "DELL": "Dell",
    "ACN": "Accenture", "CACI": "CACI International",
    "SAIC": "SAIC", "BAH": "Booz Allen Hamilton",
    # ── Financials ────────────────────────────────────────────────────────────
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "WFC": "Wells Fargo", "C": "Citigroup",
    "BLK": "BlackRock", "SCHW": "Charles Schwab", "AXP": "American Express",
    "V": "Visa", "MA": "Mastercard", "COF": "Capital One",
    "USB": "US Bancorp", "PNC": "PNC Financial", "TFC": "Truist Financial",
    "BK": "Bank of New York Mellon", "STT": "State Street",
    "ICE": "Intercontinental Exchange", "CME": "CME Group",
    "SPGI": "S&P Global", "MCO": "Moodys", "COIN": "Coinbase",
    "MSTR": "MicroStrategy", "AON": "Aon", "MMC": "Marsh McLennan",
    "PRU": "Prudential Financial", "MET": "MetLife", "AIG": "AIG",
    "ALL": "Allstate", "TRV": "Travelers", "AFL": "Aflac",
    # ── Energy ────────────────────────────────────────────────────────────────
    "XOM": "ExxonMobil", "CVX": "Chevron", "COP": "ConocoPhillips",
    "OXY": "Occidental Petroleum", "SLB": "SLB", "HAL": "Halliburton",
    "BKR": "Baker Hughes", "DVN": "Devon Energy", "EOG": "EOG Resources",
    "MPC": "Marathon Petroleum", "PSX": "Phillips 66", "VLO": "Valero Energy",
    "HES": "Hess Corp", "APA": "APA Corp", "MRO": "Marathon Oil",
    "FSLR": "First Solar", "ENPH": "Enphase Energy", "RUN": "Sunrun",
    "NEE": "NextEra Energy", "DUK": "Duke Energy", "SO": "Southern Company",
    "AEP": "American Electric Power", "EXC": "Exelon", "PCG": "PGE Corp",
    # ── Healthcare / Pharma ───────────────────────────────────────────────────
    "LLY": "Eli Lilly", "PFE": "Pfizer", "JNJ": "Johnson & Johnson",
    "MRK": "Merck", "ABBV": "AbbVie", "BMY": "Bristol Myers Squibb",
    "AMGN": "Amgen", "GILD": "Gilead Sciences", "BIIB": "Biogen",
    "MRNA": "Moderna", "BNTX": "BioNTech", "REGN": "Regeneron",
    "VRTX": "Vertex Pharmaceuticals", "ILMN": "Illumina",
    "UNH": "UnitedHealth Group", "CVS": "CVS Health", "CI": "Cigna",
    "HUM": "Humana", "CNC": "Centene", "HCA": "HCA Healthcare",
    "MDT": "Medtronic", "ABT": "Abbott Labs", "BSX": "Boston Scientific",
    "SYK": "Stryker", "ISRG": "Intuitive Surgical",
    # ── Defense ───────────────────────────────────────────────────────────────
    "LMT": "Lockheed Martin", "RTX": "RTX Corp", "NOC": "Northrop Grumman",
    "GD": "General Dynamics", "BA": "Boeing", "KTOS": "Kratos Defense",
    "HII": "Huntington Ingalls", "L3H": "L3Harris Technologies",
    # ── Consumer ──────────────────────────────────────────────────────────────
    "WMT": "Walmart", "COST": "Costco", "TGT": "Target",
    "HD": "Home Depot", "LOW": "Lowes",
    "MCD": "McDonalds", "SBUX": "Starbucks", "CMG": "Chipotle",
    "NKE": "Nike", "LULU": "Lululemon",
    "PG": "Procter & Gamble", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "PM": "Philip Morris", "MO": "Altria",
    "GIS": "General Mills", "TSN": "Tyson Foods", "HSY": "Hershey",
    "DIS": "Disney", "CMCSA": "Comcast", "WBD": "Warner Bros Discovery",
    # ── Industrials ───────────────────────────────────────────────────────────
    "GE": "GE Aerospace", "HON": "Honeywell", "MMM": "3M",
    "CAT": "Caterpillar", "DE": "Deere & Company",
    "UPS": "UPS", "FDX": "FedEx",
    "DAL": "Delta Air Lines", "UAL": "United Airlines",
    "AAL": "American Airlines", "LUV": "Southwest Airlines",
    "CCL": "Carnival Corp", "RCL": "Royal Caribbean",
    # ── Materials ─────────────────────────────────────────────────────────────
    "X": "US Steel", "NUE": "Nucor", "STLD": "Steel Dynamics",
    "AA": "Alcoa", "FCX": "Freeport-McMoRan", "NEM": "Newmont",
    "DOW": "Dow Inc", "LYB": "LyondellBasell",
    "CF": "CF Industries", "MOS": "Mosaic", "NTR": "Nutrien",
    # ── Crypto ────────────────────────────────────────────────────────────────
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
    "DOGE": "Dogecoin", "XRP": "XRP Ripple",
    # ── ETFs / macro ──────────────────────────────────────────────────────────
    "SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF", "DIA": "Dow Jones ETF",
    "IWM": "Russell 2000 ETF", "GLD": "Gold ETF", "TLT": "20yr Treasury ETF",
    "VXX": "Volatility ETF", "ARKK": "ARK Innovation ETF",
    "XLE": "Energy ETF", "XLF": "Financial ETF", "XLK": "Technology ETF",
    "XLV": "Healthcare ETF", "XLI": "Industrial ETF", "XLB": "Materials ETF",
    "CORN": "Corn ETF", "SOYB": "Soybean ETF", "WEAT": "Wheat ETF",
}

# ─── COMPANY → TICKER (direct name matching in post text) ────────────────────
# Maps distinctive company keywords to tickers.
# These are matched with word boundaries in the post body — highest confidence.

COMPANY_KEYWORDS: dict[str, str] = {
    "apple": "AAPL", "iphone": "AAPL", "app store": "AAPL", "tim cook": "AAPL",
    "alphabet": "GOOGL", "google": "GOOGL", "youtube": "GOOGL", "waymo": "GOOGL",
    "microsoft": "MSFT", "azure": "MSFT", "openai": "MSFT",
    "amazon": "AMZN", "aws": "AMZN",
    "meta platforms": "META", "facebook": "META", "instagram": "META",
    "whatsapp": "META", "zuckerberg": "META",
    "nvidia": "NVDA", "jensen huang": "NVDA",
    "tesla": "TSLA", "elon musk": "TSLA", "spacex": "TSLA",
    "advanced micro devices": "AMD",
    "intel": "INTC",
    "qualcomm": "QCOM",
    "taiwan semiconductor": "TSM", "tsmc": "TSM",
    "oracle": "ORCL",
    "broadcom": "AVGO",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "palantir": "PLTR",
    "crowdstrike": "CRWD",
    "palo alto networks": "PANW",
    "cloudflare": "NET",
    "coinbase": "COIN",
    "microstrategy": "MSTR",
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "dogecoin": "DOGE",
    "ripple": "XRP",
    # Financials
    "jpmorgan": "JPM", "jp morgan": "JPM",
    "goldman sachs": "GS", "goldman": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "citigroup": "C", "citibank": "C",
    "blackrock": "BLK",
    "charles schwab": "SCHW",
    "american express": "AXP", "amex": "AXP",
    "mastercard": "MA",
    "capital one": "COF",
    "intercontinental exchange": "ICE",
    "s&p global": "SPGI",
    "moodys": "MCO",
    # Energy
    "exxonmobil": "XOM", "exxon": "XOM",
    "chevron": "CVX",
    "conocophillips": "COP",
    "occidental petroleum": "OXY",
    "halliburton": "HAL",
    "baker hughes": "BKR",
    "first solar": "FSLR",
    "enphase": "ENPH",
    "nextera": "NEE",
    "duke energy": "DUK",
    "pg&e": "PCG",
    # Healthcare / Pharma
    "eli lilly": "LLY", "lilly": "LLY",
    "pfizer": "PFE",
    "johnson & johnson": "JNJ", "j&j": "JNJ",
    "merck": "MRK",
    "abbvie": "ABBV",
    "bristol myers": "BMY", "bristol-myers": "BMY",
    "amgen": "AMGN",
    "gilead": "GILD",
    "moderna": "MRNA",
    "biontech": "BNTX",
    "regeneron": "REGN",
    "vertex pharmaceuticals": "VRTX",
    "unitedhealth": "UNH", "united health": "UNH",
    "cvs health": "CVS", "cvs": "CVS",
    "cigna": "CI",
    "humana": "HUM",
    "hca healthcare": "HCA",
    "medtronic": "MDT",
    "abbott labs": "ABT", "abbott": "ABT",
    "boston scientific": "BSX",
    "stryker": "SYK",
    # Defense
    "lockheed martin": "LMT", "lockheed": "LMT",
    "raytheon": "RTX",
    "northrop grumman": "NOC", "northrop": "NOC",
    "general dynamics": "GD",
    "boeing": "BA",
    "kratos": "KTOS",
    "l3harris": "L3H",
    "huntington ingalls": "HII",
    # Consumer / Retail
    "walmart": "WMT",
    "costco": "COST",
    "target corporation": "TGT",
    "home depot": "HD",
    "mcdonalds": "MCD", "mcdonald's": "MCD",
    "starbucks": "SBUX",
    "chipotle": "CMG",
    "nike": "NKE",
    "coca-cola": "KO", "coca cola": "KO",
    "pepsi": "PEP", "pepsico": "PEP",
    "philip morris": "PM",
    "altria": "MO",
    "tyson foods": "TSN",
    "disney": "DIS",
    "comcast": "CMCSA",
    # Industrials
    "ge aerospace": "GE", "general electric": "GE",
    "honeywell": "HON",
    "caterpillar": "CAT",
    "deere": "DE", "john deere": "DE",
    "fedex": "FDX",
    "united parcel service": "UPS",
    "delta air": "DAL",
    "united airlines": "UAL",
    "american airlines": "AAL",
    "southwest airlines": "LUV",
    "carnival": "CCL",
    "royal caribbean": "RCL",
    # Materials
    "us steel": "X", "u.s. steel": "X",
    "nucor": "NUE",
    "steel dynamics": "STLD",
    "alcoa": "AA",
    "freeport": "FCX",
    "newmont": "NEM",
    "mosaic": "MOS",
    "nutrien": "NTR",
}

# ─── MARKET RELEVANCE FILTER ──────────────────────────────────────────────────
# A signal must contain at least one of these to be included.
# Posts about constituent services, local events, personal milestones, etc. are dropped.

MARKET_RELEVANCE_KEYWORDS = {
    # Policy & legislation
    "bill", "legislation", "law", "act", "regulation", "executive order",
    "rule", "policy", "reform", "repeal", "vote", "passed", "signed",
    "tariff", "trade", "sanction", "embargo", "export", "import",
    "treaty", "agreement", "deal", "contract",
    # Economics
    "economy", "economic", "gdp", "recession", "inflation", "deflation",
    "interest rate", "federal reserve", "monetary", "fiscal", "stimulus",
    "budget", "deficit", "debt ceiling", "spending", "appropriation",
    "jobs", "unemployment", "payroll", "wage", "labor",
    "tax", "irs", "corporate tax", "capital gains",
    # Industries
    "pharmaceutical", "pharma", "drug price", "drug pricing", "vaccine",
    "fda approval", "clinical trial",
    "semiconductor", "chip", "chipmaker", "foundry",
    "artificial intelligence", "machine learning",
    "oil", "natural gas", "petroleum", "opec", "pipeline", "refinery",
    "clean energy", "solar", "wind power", "renewable energy", "nuclear",
    "defense contractor", "military spending", "weapons system",
    "healthcare", "health insurance", "medicaid", "medicare",
    "banking regulation", "financial regulation", "wall street",
    "agriculture", "farm bill", "crop", "commodity",
    "housing market", "mortgage", "real estate",
    "broadband", "telecommunications", "spectrum",
    "airline", "aviation", "faa",
    # Market terms
    "stock", "market", "shares", "equity", "bond", "treasury", "yield",
    "nasdaq", "nyse", "dow jones",
    "merger", "acquisition", "ipo", "buyback", "dividend",
    "investor", "investment", "hedge fund", "private equity",
    "antitrust", "monopoly", "competition", "ftc", "doj",
    # Crypto
    "bitcoin", "crypto", "cryptocurrency", "blockchain", "stablecoin",
    # International trade
    "china", "taiwan", "supply chain", "wto",
    # Specific companies (so posts mentioning them are always included)
    "amazon", "google", "apple", "microsoft", "facebook",
    "tesla", "nvidia", "boeing", "pfizer", "exxon",
    "lockheed", "goldman sachs", "jpmorgan",
}


def is_market_relevant(text: str) -> bool:
    """Return True only if the text has a genuine connection to financial markets."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in MARKET_RELEVANCE_KEYWORDS)

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
        "bluesky": "warren.senate.gov",
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
        "bluesky": "sanders.senate.gov",
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
        "bluesky": "pelosi.house.gov",
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
        "bluesky": "khanna.house.gov",
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
        "name": "SEC Insider Trades",
        "initials": "SEC",
        # EDGAR = Electronic Data Gathering, Analysis, and Retrieval — the SEC's
        # public database where insiders (executives, directors, large shareholders)
        # must file Form 4 within 2 days of trading their company's stock.
        "role": "SEC EDGAR — Exec & Insider Stock Trades (Form 4)",
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
    # META: removed bare "meta" — too common in medical/scientific text (meta-analysis etc.)
    (["meta platforms", "facebook", "instagram", "whatsapp", "zuckerberg"], ["META"]),
    (["nvidia", "nvda", "gpu", "ai chip", "jensen huang"],  ["NVDA"]),
    (["tesla", "tsla", "elon musk", "spacex"],              ["TSLA"]),
    (["palantir", "pltr"],                                  ["PLTR"]),
    (["antitrust", "big tech", "monopol", "divestiture"],   ["AMZN", "GOOGL", "AAPL", "META"]),
    (["semiconductor", "chip", "tsmc", "taiwan"],           ["NVDA", "TSM", "AMD", "QCOM"]),
    (["china", "tariff", "trade war", "export ban"],        ["NVDA", "TSM", "QCOM", "AAPL"]),
    (["bitcoin", "btc", "crypto", "blockchain"],            ["BTC", "ETH", "COIN"]),
    (["stablecoin", "digital asset", "cbdc"],               ["BTC", "ETH", "COIN", "XRP"]),
    (["oil", "drilling", "petroleum", "opec"],              ["XOM", "CVX", "COP", "OXY"]),
    # Removed bare "energy" — too generic (appears in "energy levels", "high energy" etc.)
    (["clean energy", "solar", "wind power", "climate change", "renewable"], ["XOM", "FSLR", "ENPH", "XLE"]),
    (["pharma", "pharmaceutical", "drug price", "insulin", "pfizer", "eli lilly"], ["LLY", "PFE", "JNJ", "MRK"]),
    (["healthcare", "health care", "hospital", "health insurance", "medicaid", "medicare"], ["UNH", "HCA", "CVS"]),
    (["agriculture", "corn", "soybean", "grain", "farm"],   ["CORN", "SOYB", "DE"]),
    # Removed bare "bank" — too generic (blood bank, bank account in non-finance context)
    (["banking", "wall street", "federal reserve", "interest rate", "jpmorgan", "goldman"], ["JPM", "BAC", "GS", "XLF"]),
    (["defense", "military", "weapon", "nato", "pentagon"], ["LMT", "RTX", "NOC", "GD"]),
    (["steel", "aluminum", "manufacturing tariff"],         ["X", "AA", "NUE"]),
    (["sanction", "russia", "iran", "north korea"],         ["LMT", "RTX", "XOM"]),
    # Removed bare "regulation" — pulls tech stocks into healthcare/other regulatory posts
    (["ftc", "antitrust investigation", "doj lawsuit", "tech monopoly"], ["GOOGL", "AMZN", "META", "AAPL"]),
    (["gold", "silver", "inflation", "bond market", "treasury yield"], ["GLD", "TLT", "SPY"]),
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
    "sec": "SEC Form 4",
    "ustr": "USTR",
    "politico": "Politico",
    "thehill": "The Hill",
    "truthsocial": "Truth Social",
    "bluesky": "Bluesky",
    "youtube": "YouTube",
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()

def guess_tickers(text: str) -> list:
    """
    Two-phase ticker matching:
    1. Direct company name matching — highest confidence, uses COMPANY_KEYWORDS.
       e.g. "Pfizer" in text → PFE immediately, no guessing.
    2. Sector/topic fallback — uses TICKER_MAP only when no direct company match
       and the post is clearly about a sector (specific regulatory language etc.).
    Cap at 4 tickers to avoid noise.
    """
    text_lower = text.lower()
    tickers = []

    # ── Phase 0: extract SEC Form 4 tickers ───────────────────────────────────
    # SEC content is formatted as "… shares of Company Name (TICK) · …"
    # This pattern is unambiguous and authoritative — extract directly.
    for m in re.finditer(r'shares of [^(·]+\(([A-Z]{1,6})\)', text):
        tickers.append(m.group(1))

    # ── Phase 1: direct company name scan ─────────────────────────────────────
    for keyword, ticker in COMPANY_KEYWORDS.items():
        if ' ' in keyword:
            # Multi-word phrase — substring match is precise enough
            if keyword in text_lower:
                tickers.append(ticker)
        else:
            # Single word — word boundary to avoid partial matches
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                tickers.append(ticker)

    # ── Phase 2: sector keyword fallback (only if no direct company found) ────
    if not tickers:
        for keywords, sector_tickers in TICKER_MAP:
            for k in keywords:
                if ' ' in k:
                    matched = k in text_lower
                else:
                    matched = bool(re.search(r'\b' + re.escape(k) + r'(?![\w-])', text_lower))
                if matched:
                    tickers.extend(sector_tickers)
                    break

    return list(dict.fromkeys(tickers))[:4]

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

def make_signal(source: dict, content: str, platform: str, url: str = "", published: Optional[datetime] = None) -> Optional[dict]:
    # Drop posts with no market connection (unless it's a direct market source like SEC)
    if platform not in ("sec", "govtrack") and not is_market_relevant(content):
        return None

    # Only derive tickers from the actual post content — never from source's generic keywords
    # Limit to 320 chars — same window as what gets stored and shown to users,
    # so tickers always reflect visible content (avoids false matches from buried text)
    tickers = guess_tickers(content[:320])
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
            sig = make_signal(source, full_text, platform_key, link, published)
            if sig:
                signals.append(sig)
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
            sig = make_signal(source, content, "truthsocial", url, published)
            if sig:
                signals.append(sig)
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
            sig = make_signal(source, content, "youtube", url, published)
            if sig:
                signals.append(sig)
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
            sig = make_signal(source, text, "bluesky", url, published)
            if sig:
                signals.append(sig)
        print(f"  Bluesky [{source['initials']}]: {len(signals)} posts")
    except Exception as e:
        print(f"  Bluesky [{source['initials']}] error: {e}")
    return signals


_SEC_GENERIC_WORDS = {
    "INC", "INC.", "CORP", "CORP.", "CO", "CO.", "LTD", "LLC",
    "PLC", "GROUP", "HOLDINGS", "INTERNATIONAL", "GLOBAL", "THE",
    "BANK", "HEALTH", "FINANCIAL", "SERVICES", "TECHNOLOGIES", "TECHNOLOGY",
}

_TRANSACTION_CODES = {
    "P": "bought",
    "S": "sold",
    "A": "received",          # grant/award
    "D": "disposed of",       # non-market sale
    "M": "exercised options for",
    "X": "exercised derivative for",
    "C": "converted",
    "G": "gifted",
    "F": "withheld (tax)",
    "J": "acquired/disposed",
    "W": "inherited",
}

_SEC_CIK_TICKER_CACHE: dict = {}

def _load_sec_cik_tickers() -> dict:
    """Load SEC's CIK→ticker mapping (cached in memory). Returns {cik_int: ticker_str}."""
    global _SEC_CIK_TICKER_CACHE
    if _SEC_CIK_TICKER_CACHE:
        return _SEC_CIK_TICKER_CACHE
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "PolitiSignal/1.0 (hello@politisignal.com)"},
            timeout=10,
        )
        data = r.json()
        _SEC_CIK_TICKER_CACHE = {v["cik_str"]: v["ticker"] for v in data.values()}
    except Exception:
        pass
    return _SEC_CIK_TICKER_CACHE


def _sec_ticker_for_company(company_upper: str) -> Optional[str]:
    """
    Find a known ticker symbol for a company name.
    Only returns a match when a distinctive (non-generic) keyword matches.
    """
    clean = re.sub(r"[^\w\s]", "", company_upper).strip()

    padded = f" {clean} "
    for sym in TICKER_NAMES:
        if f" {sym} " in padded:
            return sym

    for sym, name in TICKER_NAMES.items():
        words = [
            w for w in re.sub(r"[^\w\s]", "", name).upper().split()
            if len(w) > 4 and w not in _SEC_GENERIC_WORDS
        ]
        if words and any(w in clean for w in words):
            return sym

    return None


def _fetch_form4_transactions(reporter_cik: str, accno: str) -> list:
    """
    Fetch Form 4 XML for a given filer CIK + accession number.
    Returns list of dicts: {"code": "P"|"S"|..., "shares": float, "price": float}
    Returns [] on any failure.
    """
    try:
        accno_nodash = accno.replace("-", "")
        headers = {"User-Agent": "PolitiSignal/1.0 (hello@politisignal.com)"}

        # Get the filing directory listing to find the XML filename
        idx_url = f"https://www.sec.gov/Archives/edgar/data/{reporter_cik}/{accno_nodash}/"
        r = requests.get(idx_url, headers=headers, timeout=8)
        if r.status_code != 200:
            return []

        # Find XML file (exclude *-index.htm which is just the index)
        xml_match = re.search(
            r'href="(/Archives/edgar/data/[^"]+\.xml)"',
            r.text
        )
        if not xml_match:
            return []
        xml_url = "https://www.sec.gov" + xml_match.group(1)

        r2 = requests.get(xml_url, headers=headers, timeout=8)
        if r2.status_code != 200:
            return []

        root = ET.fromstring(r2.text)
        transactions = []
        for txn in root.findall(".//nonDerivativeTransaction"):
            code        = (txn.findtext("transactionCoding/transactionCode") or "").strip()
            shares_text = txn.findtext("transactionAmounts/transactionShares/value") or ""
            price_text  = txn.findtext("transactionAmounts/transactionPricePerShare/value") or ""
            try:
                shares = float(shares_text) if shares_text else 0.0
                price  = float(price_text)  if price_text  else 0.0
                if code and shares:
                    transactions.append({"code": code, "shares": shares, "price": price})
            except Exception:
                pass
        return transactions
    except Exception:
        return []


def fetch_sec_edgar(source: dict, max_entries: int = 8) -> list:
    """
    Fetch SEC EDGAR Form 4 (insider transaction) filings and produce
    clear, readable summaries: "Jane Smith sold 5,000 shares of Apple (AAPL) at $185.50/share"

    The EDGAR Atom feed emits TWO entries per Form 4:
      - "4 - PersonName (CIK) (Reporting)"  ← the insider who filed
      - "4 - CompanyName (CIK) (Issuer)"    ← the company whose stock was traded

    We pair them by accession number, then fetch the Form 4 XML for transaction details.
    """
    url = source.get("rss")
    if not url:
        return []
    signals = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "PolitiSignal/1.0 (hello@politisignal.com)"})

        filings: dict = {}
        for entry in feed.entries:
            title = entry.get("title", "")
            if not (title.startswith("4 - ") or title.startswith("4/A - ")):
                continue

            entry_id = entry.get("id", "")
            if "accession-number=" not in entry_id:
                continue
            accno = entry_id.split("accession-number=")[-1].strip()

            if accno not in filings:
                filings[accno] = {"reporter": None, "reporter_cik": None, "issuer": None, "issuer_cik": None, "entry": entry}

            bare      = re.sub(r"^4(?:/A)? - ", "", title)
            name_part = re.sub(r"\s*\(\d+\)\s*\(\w+\)\s*$", "", bare).strip()
            cik_match = re.search(r"\((\d+)\)\s*\(\w+\)\s*$", title)
            cik       = cik_match.group(1) if cik_match else None

            if "(Reporting)" in title:
                filings[accno]["reporter"]     = name_part
                filings[accno]["reporter_cik"] = cik
            elif "(Issuer)" in title:
                filings[accno]["issuer"]     = name_part
                filings[accno]["issuer_cik"] = int(cik) if cik and cik.isdigit() else None

        for accno, data in list(filings.items())[:max_entries]:
            reporter     = data.get("reporter")
            reporter_cik = data.get("reporter_cik")
            issuer       = data.get("issuer")
            issuer_cik   = data.get("issuer_cik")
            entry        = data["entry"]
            if not reporter or not issuer:
                continue

            filer         = reporter.title()
            company       = issuer.title()
            company_upper = issuer.upper()
            # Try CIK→ticker lookup first (most accurate), then name matching
            cik_map       = _load_sec_cik_tickers()
            ticker        = (cik_map.get(issuer_cik) if issuer_cik else None) or _sec_ticker_for_company(company_upper)
            ticker_str    = f" ({ticker})" if ticker else ""

            # Fetch actual transaction details from Form 4 XML
            transactions = []
            if reporter_cik:
                time.sleep(0.3)  # be polite to SEC servers
                transactions = _fetch_form4_transactions(reporter_cik, accno)

            # Date from summary HTML
            date_match = re.search(r"Filed:</b>\s*([\d-]+)", entry.get("summary", ""))
            date_str   = date_match.group(1) if date_match else ""
            if date_str:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                    date_str = d.strftime("%b %-d")
                except Exception:
                    pass

            if transactions:
                txn    = transactions[0]
                action = _TRANSACTION_CODES.get(txn["code"])
                if not action:
                    continue
                shares = txn["shares"]
                price  = txn["price"]

                # Skip trades under $15,000 total value — filters tiny option exercises etc.
                trade_value = shares * price
                if price > 0 and trade_value < 15_000:
                    continue

                shares_fmt = f"{shares:,.0f}"
                total_str  = f"${trade_value:,.0f} total" if price else ""
                content = f"{filer} {action} {shares_fmt} shares of {company}{ticker_str}"
                if price:
                    content += f" · ${price:,.2f}/share"
                if total_str:
                    content += f" · {total_str}"
                if date_str:
                    content += f" · {date_str}"
                # Note if multiple blocks pushed total higher
                if len(transactions) > 1:
                    all_shares = sum(t["shares"] for t in transactions)
                    all_value  = sum(t["shares"] * t["price"] for t in transactions)
                    if all_shares != shares:
                        content += f" (${all_value:,.0f} across all blocks)"
            else:
                continue

            published = None
            parsed = getattr(entry, "updated_parsed", None) or getattr(entry, "published_parsed", None)
            if parsed:
                try:
                    published = datetime(*parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass

            signals.append(make_signal(source, content, "sec", entry.get("link", ""), published))

        print(f"  SEC EDGAR: {len(signals)} Form 4 filings summarized")
    except Exception as e:
        print(f"  SEC EDGAR error: {e}")
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
        if key == "sec":
            # Use dedicated parser that produces readable summaries
            all_signals.extend(fetch_sec_edgar(src, max_entries=10))
        else:
            all_signals.extend(fetch_rss_source(src, key, max_entries=8))

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
