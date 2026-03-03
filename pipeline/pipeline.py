#!/usr/bin/env python3
"""
PROSPERITY — VC Hiring Intelligence Pipeline
=============================================

A single-file, deployable scraping engine that pulls VC job opportunities from:
  1. Lever & Greenhouse ATS APIs (free, reliable — ~60% of fund career pages)
  2. Google Custom Search dorking for LinkedIn posts (free tier: 100 queries/day)
  3. Direct fund career page HTML scraping (BeautifulSoup)
  4. Twitter/X API v2 search (free tier: 500K reads/month)
  5. Proxycurl LinkedIn API (optional paid upgrade — ~$15-45/month)

All roles are normalized, freshness-scored, deduplicated, and exported as
roles.json for the frontend to consume.

DEPLOYMENT:
  - GitHub Actions cron (free, recommended) — see scrape.yml
  - Any server with Python 3.10+ and cron
  - Railway / Render one-off workers

SETUP:
  pip install requests beautifulsoup4 feedparser python-dateutil
  # Set env vars (see CONFIGURATION section below)

USAGE:
  python pipeline.py                    # Full scrape, output to ./output/roles.json
  python pipeline.py --source lever     # Only run Lever scraper
  python pipeline.py --dry-run          # Scrape but don't write output
"""

import os
import sys
import json
import hashlib
import logging
import re
import argparse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

try:
    import requests
except ImportError:
    print("Run: pip install requests"); sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    print("WARNING: beautifulsoup4 not installed — HTML scraping disabled")

try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None
    print("WARNING: python-dateutil not installed — date parsing will be limited")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prosperity")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# API keys — set as environment variables
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")      # Google Custom Search
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")                # Custom Search Engine ID
PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY", "")         # Optional paid LinkedIn API
TWITTER_BEARER = os.getenv("TWITTER_BEARER_TOKEN", "")         # X API v2

# Freshness thresholds
DAYS_HOT = 7       # < 1 week → "HOT"
DAYS_WARM = 30     # < 1 month → "WARM"
                    # > 1 month → "EXPIRED" (excluded from output)

# Output — writes to public/data/ so Vite serves it and Vercel deploys it
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./public/data"))
OUTPUT_FILE = OUTPUT_DIR / "roles.json"

# Request defaults
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
REQUEST_TIMEOUT = 15


# ═══════════════════════════════════════════════════════════════════════════════
# FUND REGISTRY — Loaded from discovery engine output
# ═══════════════════════════════════════════════════════════════════════════════

REGISTRY_FILE = Path(os.getenv("REGISTRY_FILE", "./public/data/funds_registry.json"))

@dataclass
class FundConfig:
    id: str
    name: str
    initials: str
    focus: str
    neighborhood: str
    aum: str
    founded: int
    map_x: float
    map_y: float
    lever_slug: str = ""
    greenhouse_slug: str = ""
    ashby_slug: str = ""
    careers_url: str = ""
    linkedin_company_url: str = ""
    twitter_handle: str = ""
    search_aliases: list = field(default_factory=list)


def load_funds_from_registry() -> list[FundConfig]:
    """
    Load fund configs from discovery engine output (funds_registry.json).
    Falls back to empty list if registry doesn't exist yet.
    
    Run `python pipeline/discovery.py` first to generate the registry.
    """
    if not REGISTRY_FILE.exists():
        log.warning(f"[Registry] {REGISTRY_FILE} not found — run discovery.py first")
        log.warning("[Registry] Pipeline will scrape 0 funds. Run: python pipeline/discovery.py")
        return []

    try:
        data = json.loads(REGISTRY_FILE.read_text())
        raw_funds = data.get("funds", [])
    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"[Registry] Failed to parse {REGISTRY_FILE}: {e}")
        return []

    funds = []
    for f in raw_funds:
        fund = FundConfig(
            id=f.get("id", ""),
            name=f.get("name", ""),
            initials=f.get("initials", ""),
            focus=f.get("focus_stage", ""),
            neighborhood=f.get("location", "London"),
            aum=f.get("aum", ""),
            founded=f.get("founded", 0),
            map_x=f.get("map_x", 50),
            map_y=f.get("map_y", 50),
            lever_slug=f.get("lever_slug", ""),
            greenhouse_slug=f.get("greenhouse_slug", ""),
            ashby_slug=f.get("ashby_slug", ""),
            careers_url=f.get("careers_url", ""),
            linkedin_company_url=f.get("linkedin_url", ""),
            twitter_handle=f.get("twitter_handle", ""),
        )
        if fund.id and fund.name:
            funds.append(fund)

    log.info(f"[Registry] Loaded {len(funds)} funds from {REGISTRY_FILE}")
    return funds


FUNDS = load_funds_from_registry()
FUND_MAP = {f.id: f for f in FUNDS}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Role:
    """Normalized role — universal format across all sources."""
    fund_id: str
    fund_name: str
    title: str
    description: str
    source: str                     # "linkedin" | "website" | "lever" | "greenhouse" | "twitter"
    source_url: str                 # Original URL — the "Apply" button links here
    posted_date: str = ""           # ISO 8601 date
    freshness: str = ""             # "HOT" | "WARM" | "EXPIRED"
    freshness_label: str = ""       # "< 1 week" | "< 1 month"
    posted_ago: str = ""            # "3 days ago"
    location: str = "London"
    seniority: str = ""             # "Analyst" | "Associate" | "VP" | "Principal" | "Partner"
    fund_focus: str = ""
    fund_neighborhood: str = ""
    fund_aum: str = ""
    fund_map_x: float = 0
    fund_map_y: float = 0
    fund_initials: str = ""
    scraped_at: str = ""
    dedup_hash: str = ""

    def __post_init__(self):
        self.scraped_at = datetime.now(timezone.utc).isoformat()
        # Dedup hash: same fund + similar title + same source = same role
        raw = f"{self.fund_id}|{normalize_title(self.title)}|{self.source}".lower()
        self.dedup_hash = hashlib.md5(raw.encode()).hexdigest()[:12]
        # Enrich from fund config
        fund = FUND_MAP.get(self.fund_id)
        if fund:
            self.fund_focus = fund.focus
            self.fund_neighborhood = fund.neighborhood
            self.fund_aum = fund.aum
            self.fund_map_x = fund.map_x
            self.fund_map_y = fund.map_y
            self.fund_initials = fund.initials
        # Score freshness
        if self.posted_date:
            self.freshness, self.freshness_label, self.posted_ago = compute_freshness(self.posted_date)
        # Classify seniority
        if not self.seniority:
            self.seniority = classify_seniority(self.title)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_title(title: str) -> str:
    """Normalize a role title for dedup comparison."""
    t = title.lower().strip()
    # Remove common suffixes/prefixes
    for noise in ["- london", "(london)", "– london", ", london", "uk", "- europe"]:
        t = t.replace(noise, "")
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def classify_seniority(title: str) -> str:
    """Infer seniority level from title text."""
    t = title.lower()
    if any(w in t for w in ["partner", "managing director", "md"]):
        return "Partner"
    if any(w in t for w in ["principal", "director", "head of"]):
        return "Principal"
    if any(w in t for w in ["vp", "vice president"]):
        return "VP"
    if any(w in t for w in ["associate", "investment manager"]):
        return "Associate"
    if any(w in t for w in ["analyst", "fellow", "intern", "research"]):
        return "Analyst"
    if any(w in t for w in ["platform", "operations", "portfolio"]):
        return "Platform"
    return "Other"


def compute_freshness(posted_date: str) -> tuple[str, str, str]:
    """
    Given an ISO date string, return (freshness, label, posted_ago).
    Uses Kealan's framework: <7d = HOT, <30d = WARM, else EXPIRED.
    """
    try:
        if dateutil_parser:
            dt = dateutil_parser.parse(posted_date)
        else:
            dt = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        delta = now - dt
        days = delta.days

        # Human-readable "ago"
        if days == 0:
            ago = "today"
        elif days == 1:
            ago = "1 day ago"
        elif days < 7:
            ago = f"{days} days ago"
        elif days < 14:
            ago = "1 week ago"
        elif days < 30:
            ago = f"{days // 7} weeks ago"
        elif days < 60:
            ago = "1 month ago"
        else:
            ago = f"{days // 30} months ago"

        if days < DAYS_HOT:
            return "HOT", "< 1 week", ago
        elif days < DAYS_WARM:
            return "WARM", "< 1 month", ago
        else:
            return "EXPIRED", "> 1 month", ago

    except Exception as e:
        log.warning(f"Could not parse date '{posted_date}': {e}")
        return "WARM", "< 1 month", "recently"


def safe_get(url: str, **kwargs) -> Optional[requests.Response]:
    """GET with error handling and timeout."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.warning(f"Request failed for {url}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 1: LEVER ATS API (free, reliable)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_lever(fund: FundConfig) -> list[Role]:
    """
    Lever exposes a public JSON API for job boards.
    GET https://api.lever.co/v0/postings/{company}?mode=json
    Returns all active listings. No auth required.
    """
    if not fund.lever_slug:
        return []

    url = f"https://api.lever.co/v0/postings/{fund.lever_slug}?mode=json"
    log.info(f"[Lever] Scraping {fund.name} → {url}")

    resp = safe_get(url)
    if not resp:
        return []

    try:
        postings = resp.json()
    except json.JSONDecodeError:
        log.warning(f"[Lever] Invalid JSON from {fund.name}")
        return []

    roles = []
    for p in postings:
        # Filter for investment/relevant roles (skip ops, legal, etc.)
        title = p.get("text", "")
        categories = p.get("categories", {})
        team = categories.get("team", "")

        # Only include investment-track and platform roles
        if not is_relevant_vc_role(title, team):
            continue

        # Lever gives createdAt as epoch ms
        created_ms = p.get("createdAt", 0)
        posted = ""
        if created_ms:
            posted = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()

        role = Role(
            fund_id=fund.id,
            fund_name=fund.name,
            title=title,
            description=p.get("descriptionPlain", "")[:500],
            source="lever",
            source_url=p.get("hostedUrl", p.get("applyUrl", "")),
            posted_date=posted,
            location=categories.get("location", "London"),
        )
        roles.append(role)

    log.info(f"[Lever] {fund.name}: found {len(roles)} relevant roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 2: GREENHOUSE ATS API (free, reliable)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_greenhouse(fund: FundConfig) -> list[Role]:
    """
    Greenhouse exposes a public JSON API for job boards.
    GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs
    No auth required.
    """
    if not fund.greenhouse_slug:
        return []

    url = f"https://boards-api.greenhouse.io/v1/boards/{fund.greenhouse_slug}/jobs?content=true"
    log.info(f"[Greenhouse] Scraping {fund.name} → {url}")

    resp = safe_get(url)
    if not resp:
        return []

    try:
        data = resp.json()
        jobs = data.get("jobs", [])
    except (json.JSONDecodeError, KeyError):
        log.warning(f"[Greenhouse] Invalid response from {fund.name}")
        return []

    roles = []
    for j in jobs:
        title = j.get("title", "")

        # Filter for investment-relevant roles
        departments = [d.get("name", "") for d in j.get("departments", [])]
        dept_str = " ".join(departments)

        if not is_relevant_vc_role(title, dept_str):
            continue

        # Greenhouse gives updated_at as ISO string
        posted = j.get("updated_at", j.get("created_at", ""))

        # Strip HTML from content
        content = j.get("content", "")
        if BeautifulSoup and content:
            content = BeautifulSoup(content, "html.parser").get_text(separator=" ")[:500]

        role = Role(
            fund_id=fund.id,
            fund_name=fund.name,
            title=title,
            description=content,
            source="greenhouse",
            source_url=j.get("absolute_url", ""),
            posted_date=posted,
            location=j.get("location", {}).get("name", "London"),
        )
        roles.append(role)

    log.info(f"[Greenhouse] {fund.name}: found {len(roles)} relevant roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 3: GOOGLE CUSTOM SEARCH → LINKEDIN POSTS (free tier)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_linkedin_via_google(fund: FundConfig) -> list[Role]:
    """
    Use Google Custom Search API to find recent LinkedIn posts about hiring.
    Free tier: 100 queries/day (enough for 50 funds × 2 queries each).

    Setup required:
    1. Create a Google Custom Search Engine at https://programmablesearchengine.google.com
    2. Configure it to search linkedin.com/posts and linkedin.com/feed
    3. Get API key from Google Cloud Console
    4. Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX env vars
    """
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return []

    queries = [
        f'site:linkedin.com/posts "{fund.name}" ("hiring" OR "join" OR "role" OR "looking for")',
        f'site:linkedin.com/feed "{fund.name}" ("analyst" OR "associate" OR "principal" OR "fellow")',
    ]

    roles = []
    for query in queries:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_CSE_API_KEY,
            "cx": GOOGLE_CSE_CX,
            "q": query,
            "dateRestrict": "m1",  # Last month only
            "num": 5,
        }

        log.info(f"[Google→LinkedIn] Searching: {query[:80]}...")
        resp = safe_get(url, params=params)
        if not resp:
            continue

        try:
            results = resp.json().get("items", [])
        except json.JSONDecodeError:
            continue

        for item in results:
            title_text = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")

            # Extract role title from post content
            extracted_title = extract_role_title_from_text(f"{title_text} {snippet}", fund.name)
            if not extracted_title:
                continue

            # Approximate date from Google metadata
            page_map = item.get("pagemap", {})
            metatags = page_map.get("metatags", [{}])[0]
            posted = metatags.get("article:published_time", "")

            role = Role(
                fund_id=fund.id,
                fund_name=fund.name,
                title=extracted_title,
                description=snippet[:500],
                source="linkedin",
                source_url=link,
                posted_date=posted,
            )
            roles.append(role)

    log.info(f"[Google→LinkedIn] {fund.name}: found {len(roles)} potential roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 4: TWITTER/X API v2 (free tier)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_twitter(fund: FundConfig) -> list[Role]:
    """
    Search X for hiring announcements from fund accounts.
    Free tier: Basic access, 500K tweet reads/month.

    Setup: Create X Developer account → get Bearer token → set TWITTER_BEARER_TOKEN
    """
    if not TWITTER_BEARER or not fund.twitter_handle:
        return []

    query = f'from:{fund.twitter_handle} ("hiring" OR "join" OR "role" OR "looking for" OR "apply")'
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": query,
        "max_results": 10,
        "tweet.fields": "created_at,text,entities",
    }
    auth_headers = {**HEADERS, "Authorization": f"Bearer {TWITTER_BEARER}"}

    log.info(f"[Twitter] Searching for hiring posts from @{fund.twitter_handle}")

    try:
        resp = requests.get(url, headers=auth_headers, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"[Twitter] Failed for {fund.name}: {e}")
        return []

    roles = []
    for tweet in data.get("data", []):
        text = tweet.get("text", "")
        created = tweet.get("created_at", "")
        tweet_id = tweet.get("id", "")

        extracted_title = extract_role_title_from_text(text, fund.name)
        if not extracted_title:
            continue

        # Find apply link in tweet
        urls = tweet.get("entities", {}).get("urls", [])
        apply_url = urls[0]["expanded_url"] if urls else f"https://x.com/{fund.twitter_handle}/status/{tweet_id}"

        role = Role(
            fund_id=fund.id,
            fund_name=fund.name,
            title=extracted_title,
            description=text[:500],
            source="twitter",
            source_url=apply_url,
            posted_date=created,
        )
        roles.append(role)

    log.info(f"[Twitter] {fund.name}: found {len(roles)} potential roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 5: PROXYCURL — LinkedIn Company Posts (optional, paid)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_linkedin_proxycurl(fund: FundConfig) -> list[Role]:
    """
    Proxycurl provides legal API access to LinkedIn data.
    ~$0.01-0.03 per call. Endpoint: Company Posts.

    Setup: Get API key at https://nubela.co/proxycurl → set PROXYCURL_API_KEY
    """
    if not PROXYCURL_API_KEY or not fund.linkedin_company_url:
        return []

    url = "https://nubela.co/proxycurl/api/linkedin/company/post"
    params = {"url": fund.linkedin_company_url, "category": "posts"}
    auth_headers = {"Authorization": f"Bearer {PROXYCURL_API_KEY}"}

    log.info(f"[Proxycurl] Fetching posts for {fund.name}")

    try:
        resp = requests.get(url, headers=auth_headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"[Proxycurl] Failed for {fund.name}: {e}")
        return []

    roles = []
    for post in data.get("posts", []):
        text = post.get("text", "")
        # Only process posts that mention hiring
        if not any(kw in text.lower() for kw in HIRING_KEYWORDS):
            continue

        extracted_title = extract_role_title_from_text(text, fund.name)
        if not extracted_title:
            continue

        posted = post.get("posted_date", {}).get("day", "")
        post_url = post.get("url", fund.linkedin_company_url)

        role = Role(
            fund_id=fund.id,
            fund_name=fund.name,
            title=extracted_title,
            description=text[:500],
            source="linkedin",
            source_url=post_url,
            posted_date=posted,
        )
        roles.append(role)

    log.info(f"[Proxycurl] {fund.name}: found {len(roles)} potential roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# NLP UTILITIES — Role title extraction from unstructured text
# ═══════════════════════════════════════════════════════════════════════════════

HIRING_KEYWORDS = [
    "hiring", "looking for", "join our team", "open role", "we're recruiting",
    "job opening", "position available", "come work with", "apply now",
    "seeking a", "searching for", "opportunity at",
]

ROLE_PATTERNS = [
    # "Hiring an Investment Analyst"
    r"(?:hiring|looking for|seeking|recruiting)\s+(?:an?\s+)?(.+?)(?:\.|,|!|\n|to\s+join|based\s+in|at\s+)",
    # "Investment Analyst role"
    r"([\w\s/\-]+(?:analyst|associate|principal|partner|fellow|intern|manager|director|VP))\s*(?:role|position|opening)",
    # "role: Investment Analyst"
    r"(?:role|position|title)[\s:]+(.+?)(?:\.|,|!|\n)",
    # "Our new Associate"
    r"(?:our|the)\s+(?:new\s+)?(.+?(?:analyst|associate|principal|partner|fellow|manager))",
    # "Join as [title]"
    r"join\s+(?:us\s+)?as\s+(?:an?\s+)?(.+?)(?:\.|,|!|\n)",
]

VC_ROLE_TITLES = [
    "analyst", "associate", "principal", "partner", "fellow", "intern",
    "investment manager", "venture fellow", "platform", "portfolio",
    "head of", "director", "vice president", "vp",
]


def extract_role_title_from_text(text: str, fund_name: str = "") -> Optional[str]:
    """
    Extract a job title from unstructured text (LinkedIn post, tweet, etc.)
    Returns cleaned title or None if no role detected.
    """
    text_lower = text.lower()

    # Quick check: does this text mention any VC role keywords?
    if not any(kw in text_lower for kw in VC_ROLE_TITLES):
        return None

    # Try regex patterns
    for pattern in ROLE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean up
            title = re.sub(r"\s+", " ", title)
            title = title.strip(".,!?:;-–— ")
            # Validate: must contain at least one VC role keyword
            if any(kw in title.lower() for kw in VC_ROLE_TITLES):
                # Capitalize properly
                title = title.title()
                # Remove fund name if it crept in
                if fund_name:
                    title = title.replace(fund_name, "").strip(" -–—,")
                return title if len(title) > 3 else None

    return None


def is_relevant_vc_role(title: str, department: str = "") -> bool:
    """
    Filter for investment-track and platform roles.
    Exclude: legal, accounting, IT, admin, HR, marketing (unless it's platform).
    """
    combined = f"{title} {department}".lower()

    # Exclude non-investment roles
    exclude = ["legal", "counsel", "accountant", "accounting", "receptionist",
               "office manager", "it support", "graphic design", "payroll"]
    if any(ex in combined for ex in exclude):
        return False

    # Include: investment roles, platform roles, research
    include = VC_ROLE_TITLES + ["platform", "research", "data", "operating"]
    return any(inc in combined for inc in include)


# ═══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def deduplicate(roles: list[Role]) -> list[Role]:
    """
    Remove duplicate roles across sources.
    Priority: lever/greenhouse (most reliable) > linkedin > twitter
    """
    SOURCE_PRIORITY = {"lever": 0, "greenhouse": 1, "website": 2, "linkedin": 3, "twitter": 4}

    seen = {}
    for role in roles:
        key = f"{role.fund_id}|{normalize_title(role.title)}"
        if key not in seen:
            seen[key] = role
        else:
            # Keep the one from the more reliable source
            existing_priority = SOURCE_PRIORITY.get(seen[key].source, 99)
            new_priority = SOURCE_PRIORITY.get(role.source, 99)
            if new_priority < existing_priority:
                seen[key] = role

    return list(seen.values())


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(sources: list[str] = None, dry_run: bool = False) -> dict:
    """
    Run the full pipeline. Returns stats dict.
    
    Args:
        sources: List of source names to run. None = all.
                 Options: "lever", "greenhouse", "google", "twitter", "proxycurl"
        dry_run: If True, scrape but don't write output file.
    """
    all_sources = sources or ["lever", "greenhouse", "google", "twitter", "proxycurl"]
    all_roles = []
    errors = []

    scrapers = {
        "lever": scrape_lever,
        "greenhouse": scrape_greenhouse,
        "google": scrape_linkedin_via_google,
        "twitter": scrape_twitter,
        "proxycurl": scrape_linkedin_proxycurl,
    }

    for fund in FUNDS:
        for source_name in all_sources:
            scraper = scrapers.get(source_name)
            if not scraper:
                continue
            try:
                roles = scraper(fund)
                all_roles.extend(roles)
            except Exception as e:
                error_msg = f"{source_name}/{fund.id}: {str(e)}"
                log.error(f"[Pipeline] Error — {error_msg}")
                errors.append(error_msg)

    log.info(f"[Pipeline] Raw roles found: {len(all_roles)}")

    # Deduplicate
    deduped = deduplicate(all_roles)
    log.info(f"[Pipeline] After dedup: {len(deduped)}")

    # Filter expired
    fresh = [r for r in deduped if r.freshness != "EXPIRED"]
    log.info(f"[Pipeline] After freshness filter (excluding >30d): {len(fresh)}")

    # Sort: HOT first, then WARM; within each, newest first
    fresh.sort(key=lambda r: (0 if r.freshness == "HOT" else 1, r.posted_date or ""), reverse=False)
    fresh.sort(key=lambda r: (0 if r.freshness == "HOT" else 1))

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_roles": len(fresh),
            "hot_roles": sum(1 for r in fresh if r.freshness == "HOT"),
            "warm_roles": sum(1 for r in fresh if r.freshness == "WARM"),
            "funds_hiring": len(set(r.fund_id for r in fresh)),
            "sources_used": list(set(r.source for r in fresh)),
            "errors": errors,
        },
        # Group roles by fund for frontend consumption
        "funds": {},
        # Also provide flat list
        "roles": [asdict(r) for r in fresh],
    }

    # Group by fund
    for role in fresh:
        if role.fund_id not in output["funds"]:
            fund = FUND_MAP[role.fund_id]
            output["funds"][role.fund_id] = {
                "id": fund.id,
                "name": fund.name,
                "initials": fund.initials,
                "focus": fund.focus,
                "neighborhood": fund.neighborhood,
                "aum": fund.aum,
                "founded": fund.founded,
                "map_x": fund.map_x,
                "map_y": fund.map_y,
                "hiring": True,
                "roles": [],
            }
        output["funds"][role.fund_id]["roles"].append({
            "title": role.title,
            "freshness": role.freshness,
            "freshness_label": role.freshness_label,
            "posted_ago": role.posted_ago,
            "source": role.source,
            "source_url": role.source_url,
            "description": role.description,
            "seniority": role.seniority,
        })

    # Add non-hiring funds
    for fund in FUNDS:
        if fund.id not in output["funds"]:
            output["funds"][fund.id] = {
                "id": fund.id,
                "name": fund.name,
                "initials": fund.initials,
                "focus": fund.focus,
                "neighborhood": fund.neighborhood,
                "aum": fund.aum,
                "founded": fund.founded,
                "map_x": fund.map_x,
                "map_y": fund.map_y,
                "hiring": False,
                "roles": [],
            }

    # Write output
    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        log.info(f"[Pipeline] Output written to {OUTPUT_FILE}")

    # Print summary
    log.info("=" * 60)
    log.info(f"  PROSPERITY PIPELINE — RUN COMPLETE")
    log.info(f"  Total roles:    {output['stats']['total_roles']}")
    log.info(f"  HOT (< 1 week): {output['stats']['hot_roles']}")
    log.info(f"  WARM (< 1 mo):  {output['stats']['warm_roles']}")
    log.info(f"  Funds hiring:   {output['stats']['funds_hiring']}")
    log.info(f"  Errors:         {len(errors)}")
    log.info("=" * 60)

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prosperity VC Hiring Pipeline")
    parser.add_argument("--source", nargs="+",
                        choices=["lever", "greenhouse", "google", "twitter", "proxycurl"],
                        help="Run specific scrapers only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrape but don't write output file")
    parser.add_argument("--fund", help="Scrape a single fund by ID")
    args = parser.parse_args()

    if args.fund:
        # Override FUNDS to only scrape one
        if args.fund in FUND_MAP:
            FUNDS_BACKUP = FUNDS.copy()
            FUNDS.clear()
            FUNDS.append(FUND_MAP[args.fund])

    run_pipeline(sources=args.source, dry_run=args.dry_run)
