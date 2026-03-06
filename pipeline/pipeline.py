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
import time

# Ensure pipeline modules can import each other regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")         # Claude Haiku for NLP

# LLM classifier (imported from same directory)
try:
    import llm_classifier
    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    log.info("[Pipeline] llm_classifier not available — using regex-only extraction")

# People registry for social monitoring
PEOPLE_FILE = Path(os.getenv("PEOPLE_FILE", "./public/data/people_registry.json"))

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
# SCRAPER 6: CAREER PAGE SCRAPING (free, LLM-assisted)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_career_page(fund: FundConfig) -> list[Role]:
    """
    Scrape a fund's career/jobs page directly.
    Uses LLM to extract structured roles from raw HTML.
    Falls back to regex extraction if LLM unavailable.
    
    CRITICAL: Detects and skips team/about pages that list team members
    (not job openings). Only processes actual careers/jobs pages.
    """
    # Skip if we already scrape this fund via ATS
    if fund.lever_slug or fund.greenhouse_slug or fund.ashby_slug:
        return []

    if not fund.careers_url:
        return []

    # Skip URLs that are clearly team pages, not careers pages
    url_lower = fund.careers_url.lower()
    if any(p in url_lower for p in ["/team", "/people", "/about/team", "/meet-the-team"]):
        if "/careers" not in url_lower and "/jobs" not in url_lower:
            log.info(f"[Career] Skipping {fund.name} — URL looks like team page: {fund.careers_url}")
            return []

    log.info(f"[Career] Scraping {fund.name} → {fund.careers_url}")

    resp = safe_get(fund.careers_url)
    if not resp:
        return []

    # Parse HTML → clean text
    if BeautifulSoup:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        page_text = soup.get_text(separator="\n", strip=True)

        # ── Detect if this is a team page, not a careers page ──
        text_lower = page_text.lower()
        team_signals = ["meet the team", "our team", "our people", "leadership team",
                        "managing partner", "general partner", "venture partner",
                        "advisory board", "board of directors"]
        career_signals = ["apply now", "job opening", "open position", "current openings",
                          "we're hiring", "join us", "career opportunities", "open roles",
                          "submit your application", "apply here"]
        
        team_score = sum(1 for s in team_signals if s in text_lower)
        career_score = sum(1 for s in career_signals if s in text_lower)
        
        if team_score > career_score and career_score < 2:
            log.info(f"[Career] Skipping {fund.name} — page content looks like team page (team:{team_score} career:{career_score})")
            return []

        # Grab job-specific links for proper apply URLs
        job_links = {}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if any(kw in text.lower() or kw in href.lower() 
                   for kw in ["apply", "job", "role", "position", "career", "lever.co", "greenhouse.io"]):
                if text and len(text) > 3:
                    job_links[text] = href

        if job_links:
            page_text += "\n\nJOB LINKS FOUND:\n" + "\n".join(f"{k}: {v}" for k, v in list(job_links.items())[:20])
    else:
        page_text = resp.text[:5000]

    if len(page_text) < 30:
        return []

    roles = []
    if not BeautifulSoup:
        job_links = {}

    # Try LLM extraction first
    if HAS_LLM:
        result = llm_classifier.extract_roles_from_career_page(page_text, fund.name)
        if result and result.get("has_roles") and result.get("roles"):
            for r in result["roles"]:
                title = r.get("title", "")
                if not title or not is_relevant_vc_role(title, ""):
                    continue

                # Try to find a specific apply URL for this role
                apply_url = r.get("apply_url") or ""
                if not apply_url or apply_url == fund.careers_url:
                    # Look for a matching link from the page
                    for link_text, link_url in (job_links.items() if BeautifulSoup else []):
                        if any(word in link_text.lower() for word in title.lower().split() if len(word) > 3):
                            apply_url = link_url
                            break
                
                if not apply_url:
                    apply_url = fund.careers_url

                role = Role(
                    fund_id=fund.id,
                    fund_name=fund.name,
                    title=title,
                    description=r.get("description", "")[:500],
                    source="website",
                    source_url=apply_url,
                    posted_date="",
                    location=r.get("location", "London"),
                )
                roles.append(role)

            log.info(f"[Career] {fund.name}: LLM extracted {len(roles)} roles")
            return roles

    # Regex fallback: ONLY look for lines that look like actual job postings
    # Must have action words nearby, not just role keywords
    job_listing_patterns = [
        r"(?:apply|open|hiring|vacancy|position).*?([\w\s/\-]+(?:analyst|associate|principal|partner|fellow|intern|manager|director|VP))",
        r"([\w\s/\-]+(?:analyst|associate|principal|partner|fellow|manager|director))[\s—\-:]+(?:apply|london|remote|full.time|open)",
    ]
    
    for line in page_text.split("\n"):
        line = line.strip()
        if len(line) < 10 or len(line) > 120:
            continue
        for pattern in job_listing_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if is_relevant_vc_role(title, ""):
                    role = Role(
                        fund_id=fund.id,
                        fund_name=fund.name,
                        title=title,
                        description="",
                        source="website",
                        source_url=fund.careers_url,
                    )
                    roles.append(role)
                break

    log.info(f"[Career] {fund.name}: regex extracted {len(roles)} roles")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 7: PEOPLE-BASED LINKEDIN MONITORING (free via Google CSE)
# ═══════════════════════════════════════════════════════════════════════════════

def load_people_registry() -> list[dict]:
    """Load the people registry built by people_registry.py."""
    if not PEOPLE_FILE.exists():
        return []
    try:
        data = json.loads(PEOPLE_FILE.read_text())
        return data.get("people", [])
    except (json.JSONDecodeError, KeyError):
        return []


def scrape_linkedin_by_people(fund: FundConfig) -> list[Role]:
    """
    Search Google for LinkedIn posts by SPECIFIC PEOPLE at a fund.
    This catches posts where someone says 'we're hiring' without naming the fund.
    
    Uses the people_registry.json built by people_registry.py.
    Complementary to scrape_linkedin_via_google() which searches by fund name.
    """
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return []

    # Load people for this fund
    all_people = load_people_registry()
    fund_people = [p for p in all_people
                   if p.get("fund_id") == fund.id
                   and p.get("is_investment_team", False)]

    if not fund_people:
        return []

    # Pick the most likely posters: partners, talent leads, senior team
    priority_roles = ["partner", "principal", "talent", "people", "head"]
    high_priority = [p for p in fund_people 
                     if any(r in p.get("role", "").lower() for r in priority_roles)]
    others = [p for p in fund_people if p not in high_priority]
    
    # Search partners first, then others; cap at 5 people per fund
    to_search = (high_priority + others)[:5]

    roles = []
    for person in to_search:
        name = person.get("name", "")
        if not name:
            continue

        # Search by person name + hiring keywords
        query = f'site:linkedin.com/posts "{name}" ("hiring" OR "join" OR "role" OR "open position" OR "team")'
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_CSE_API_KEY,
            "cx": GOOGLE_CSE_CX,
            "q": query,
            "dateRestrict": "m1",  # Last month
            "num": 5,
        }

        log.info(f"[People→LinkedIn] Searching posts by {name} ({fund.name})")
        resp = safe_get(url, params=params)
        if not resp:
            continue

        try:
            items = resp.json().get("items", [])
        except json.JSONDecodeError:
            continue

        for item in items:
            title_text = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            combined_text = f"{title_text} {snippet}"

            # Use LLM to classify if available
            if HAS_LLM:
                classification = llm_classifier.classify_hiring_signal(
                    combined_text,
                    source_context=f"LinkedIn post by {name}, {person.get('role', '')} at {fund.name}"
                )
                if classification and classification.get("is_hiring_signal"):
                    for llm_role in classification.get("roles", []):
                        role_title = llm_role.get("title", "")
                        if not role_title:
                            role_title = f"Open Role at {fund.name}"
                        
                        role = Role(
                            fund_id=fund.id,
                            fund_name=fund.name,
                            title=role_title,
                            description=llm_role.get("description", snippet[:500]),
                            source="linkedin",
                            source_url=link,
                            posted_date="",  # Google snippets don't always have dates
                        )
                        roles.append(role)
                    
                    # Even if LLM found no specific roles, create a generic signal
                    if not classification.get("roles") and classification.get("confidence", 0) > 0.7:
                        role = Role(
                            fund_id=fund.id,
                            fund_name=fund.name,
                            title=f"Hiring Signal — {fund.name}",
                            description=f"Post by {name}: {snippet[:400]}",
                            source="linkedin",
                            source_url=link,
                        )
                        roles.append(role)
                continue

            # Regex fallback
            extracted_title = extract_role_title_from_text(combined_text, fund.name)
            if extracted_title:
                role = Role(
                    fund_id=fund.id,
                    fund_name=fund.name,
                    title=extracted_title,
                    description=snippet[:500],
                    source="linkedin",
                    source_url=link,
                )
                roles.append(role)

        time.sleep(0.5)  # Rate limit between people

    log.info(f"[People→LinkedIn] {fund.name}: found {len(roles)} roles from {len(to_search)} people")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 8: FUND-NAME SOCIAL SCANNER (catches outsider posts)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_social_mentions(fund: FundConfig) -> list[Role]:
    """
    Search Google for ANY LinkedIn post mentioning a fund + hiring signal.
    This catches: recruiters, portfolio founders, ecosystem chatter.
    Complementary to people-based search (catches outsider posts).
    
    Enhanced with LLM classification to reduce false positives.
    """
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return []

    # Broader keyword set than the original google scraper
    hiring_phrases = [
        "hiring", "open role", "looking for", "join",
        "growing the team", "searching for", "recruiting",
        "DMs open", "know someone", "opportunity",
    ]
    role_phrases = [
        "analyst", "associate", "principal", "partner",
        "fellow", "investment", "venture", "platform",
    ]

    # Build 2 complementary queries
    hire_or = " OR ".join(f'"{p}"' for p in hiring_phrases[:5])
    role_or = " OR ".join(f'"{p}"' for p in role_phrases[:5])
    queries = [
        f'site:linkedin.com "{fund.name}" ({hire_or})',
        f'site:linkedin.com "{fund.name}" ({role_or})',
    ]

    roles = []
    seen_links = set()

    for query in queries:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_CSE_API_KEY,
            "cx": GOOGLE_CSE_CX,
            "q": query,
            "dateRestrict": "m1",
            "num": 5,
        }

        log.info(f"[Social] Searching: {fund.name} mentions")
        resp = safe_get(url, params=params)
        if not resp:
            continue

        try:
            items = resp.json().get("items", [])
        except json.JSONDecodeError:
            continue

        for item in items:
            link = item.get("link", "")
            if link in seen_links:
                continue
            seen_links.add(link)

            title_text = item.get("title", "")
            snippet = item.get("snippet", "")
            combined = f"{title_text} {snippet}"

            # LLM classification
            if HAS_LLM:
                classification = llm_classifier.classify_hiring_signal(
                    combined,
                    source_context=f"LinkedIn post/article mentioning {fund.name}"
                )
                if not classification or not classification.get("is_hiring_signal"):
                    continue
                
                for llm_role in classification.get("roles", []):
                    role = Role(
                        fund_id=fund.id,
                        fund_name=fund.name,
                        title=llm_role.get("title") or f"Open Role at {fund.name}",
                        description=llm_role.get("description", snippet[:500]),
                        source="linkedin",
                        source_url=link,
                    )
                    roles.append(role)

                if not classification.get("roles") and classification.get("confidence", 0) > 0.7:
                    roles.append(Role(
                        fund_id=fund.id,
                        fund_name=fund.name,
                        title=f"Hiring Signal — {fund.name}",
                        description=snippet[:500],
                        source="linkedin",
                        source_url=link,
                    ))
                continue

            # Regex fallback
            extracted = extract_role_title_from_text(combined, fund.name)
            if extracted:
                roles.append(Role(
                    fund_id=fund.id,
                    fund_name=fund.name,
                    title=extracted,
                    description=snippet[:500],
                    source="linkedin",
                    source_url=link,
                ))

        time.sleep(0.5)

    log.info(f"[Social] {fund.name}: found {len(roles)} roles from mentions")
    return roles


# ═══════════════════════════════════════════════════════════════════════════════
# NLP UTILITIES — Role title extraction from unstructured text
# ═══════════════════════════════════════════════════════════════════════════════

HIRING_KEYWORDS = [
    # Direct hiring signals
    "hiring", "looking for", "join our team", "open role", "we're recruiting",
    "job opening", "position available", "come work with", "apply now",
    "seeking a", "searching for", "opportunity at",
    # Softer signals (how partners actually talk)
    "building out", "expanding", "strengthening the team", "adding to",
    "scaling our team", "first hire", "founding team member", "come join",
    "excited to share", "who wants to", "growing the team", "we're adding",
    # Referral language (how VC roles circulate)
    "know anyone", "send them my way", "tag someone", "spread the word",
    "help me find", "would love intros", "share this",
    # Recruiter / headhunter language
    "mandate", "retained search", "exclusive role", "confidential search",
    "working with a leading", "on behalf of",
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
    # Core investment track
    "analyst", "associate", "principal", "partner", "fellow", "intern",
    "investment manager", "venture fellow",
    # Platform / ops
    "platform", "portfolio", "head of", "director", "vice president", "vp",
    # European VC specific
    "eir", "entrepreneur in residence", "venture partner", "operating partner",
    "scout", "deal team", "investment team", "talent partner",
    "portfolio services", "operating advisor",
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
    Filter for ACTUAL JOB LISTINGS at the VC fund itself.
    Must look like a real job title, not a team page bio or portfolio description.
    """
    combined = f"{title} {department}".lower()
    title_lower = title.lower().strip()
    title_stripped = title.strip()
    words = title_stripped.split()

    # ── Reject if too short or too long for a job title ──
    if len(title_lower) < 5 or len(title_lower) > 100:
        return False

    # ── Reject person names ──
    # Names like "Marianne Burgum Oliveira" or "John Smith"
    vc_keywords_set = {"analyst", "associate", "principal", "partner", "fellow",
        "intern", "investment", "venture", "platform", "portfolio", "head",
        "director", "vice", "president", "vp", "manager", "managing", "general",
        "operating", "senior", "junior", "research", "scout", "eir", "deal",
        "talent", "growth", "data", "of"}
    if len(words) >= 2:
        non_keyword_caps = [w for w in words
            if w[0].isupper() and w.lower() not in vc_keywords_set
            and len(w) > 2 and w.isalpha()]
        if len(non_keyword_caps) >= 2 and len(non_keyword_caps) >= len(words) * 0.5:
            return False

    # ── Reject bare role designations (team member labels, NOT job posts) ──
    bare_titles = {
        "managing partner", "general partner", "investment partner",
        "operating partner", "venture partner", "founding partner",
        "senior partner", "junior partner", "partner", "partners",
        "managing director", "co-founder", "founder",
        "chairman", "chairwoman", "board member",
        "advisory board", "board of directors",
        "team", "people", "about", "leadership",
        "our team", "meet the team", "who we are", "portfolio",
        "portfolio growth", "portfolio jobs",
    }
    if title_lower in bare_titles:
        return False

    # ── Reject descriptions/sentences ──
    if len(words) > 12:
        return False

    sentence_signals = ["investing in", "focused on", "partnering with",
                        "limited partner", "we invest", "our focus",
                        "backed by", "portfolio of", "companies at",
                        "shaping the future", "discover exciting",
                        "can you spot", "exceptional early-stage",
                        "nexus of", "at the intersection",
                        "gold and silver", "trading platform",
                        "banking platform", "investment platform",
                        "fintech platform", "coreless banking",
                        "direct-to-consumer", "financial crimes",
                        "internet services", "district of columbia"]
    if any(s in combined for s in sentence_signals):
        return False

    # ── Reject portfolio company roles ──
    portfolio_signals = ["portfolio company", "our portfolio",
                         "startup", "series a", "series b", "seed round",
                         "product manager", "software engineer", "frontend",
                         "backend", "full stack", "devops", "data scientist",
                         "machine learning engineer", "marketing manager",
                         "sales manager", "customer success", "account executive",
                         "cto", "cfo", "coo", "chief technology", "chief financial"]
    if any(s in combined for s in portfolio_signals):
        return False

    # ── Reject generic non-investment roles ──
    exclude = ["legal", "counsel", "accountant", "accounting", "receptionist",
               "office manager", "it support", "graphic design", "payroll",
               "cookie", "privacy", "terms", "subscribe", "newsletter"]
    if any(ex in combined for ex in exclude):
        return False

    # ── Must contain at least one VC role keyword to be included ──
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
    # SOURCES: ATS scrapers are auto-approved (structured, reliable).
    # All other scrapers produce "pending" roles that require manual review.
    AUTO_APPROVED_SOURCES = {"lever", "greenhouse"}
    all_sources = sources or ["lever", "greenhouse", "career", "google", "people", "social", "twitter", "proxycurl"]
    all_roles = []
    errors = []

    scrapers = {
        "lever": scrape_lever,
        "greenhouse": scrape_greenhouse,
        "career": scrape_career_page,
        "google": scrape_linkedin_via_google,
        "people": scrape_linkedin_by_people,
        "social": scrape_social_mentions,
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

    # ── Split into auto-approved and pending ──
    # Load previously approved roles (persists across runs)
    APPROVED_FILE = OUTPUT_DIR / "approved_roles.json"
    approved_hashes = set()
    if APPROVED_FILE.exists():
        try:
            approved_data = json.loads(APPROVED_FILE.read_text())
            approved_hashes = set(approved_data.get("hashes", []))
        except (json.JSONDecodeError, KeyError):
            pass

    auto_approved = []
    pending = []
    for role in fresh:
        if role.source in AUTO_APPROVED_SOURCES:
            auto_approved.append(role)
        elif role.dedup_hash in approved_hashes:
            auto_approved.append(role)  # Previously approved by user
        else:
            pending.append(role)

    log.info(f"[Pipeline] Auto-approved: {len(auto_approved)}, Pending review: {len(pending)}, Previously approved: {len(approved_hashes)}")

    # Sort: HOT first, then WARM; within each, newest first
    auto_approved.sort(key=lambda r: (0 if r.freshness == "HOT" else 1, r.posted_date or ""), reverse=False)
    auto_approved.sort(key=lambda r: (0 if r.freshness == "HOT" else 1))

    # Build output (only auto-approved roles go live)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_roles": len(auto_approved),
            "hot_roles": sum(1 for r in auto_approved if r.freshness == "HOT"),
            "warm_roles": sum(1 for r in auto_approved if r.freshness == "WARM"),
            "funds_hiring": len(set(r.fund_id for r in auto_approved)),
            "sources_used": list(set(r.source for r in auto_approved)),
            "pending_review": len(pending),
            "errors": errors,
        },
        # Group roles by fund for frontend consumption
        "funds": {},
        # Also provide flat list
        "roles": [asdict(r) for r in auto_approved],
    }

    # Group by fund
    for role in auto_approved:
        if role.fund_id not in output["funds"]:
            fund = FUND_MAP.get(role.fund_id)
            if not fund:
                continue
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
                "website": getattr(fund, 'careers_url', '') or '',
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
                "website": getattr(fund, 'careers_url', '') or '',
                "hiring": False,
                "roles": [],
            }

    # Write outputs
    if not dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Main roles file (auto-approved only)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        log.info(f"[Pipeline] Roles written to {OUTPUT_FILE}")

        # Pending roles file (for email digest / admin review)
        PENDING_FILE = OUTPUT_DIR / "pending_roles.json"
        pending_output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_pending": len(pending),
            "roles": [asdict(r) for r in pending],
        }
        PENDING_FILE.write_text(json.dumps(pending_output, indent=2, ensure_ascii=False))
        log.info(f"[Pipeline] Pending roles written to {PENDING_FILE}")

    # Print summary
    log.info("=" * 60)
    log.info(f"  PROSPERITY PIPELINE — RUN COMPLETE")
    log.info(f"  Live roles:     {output['stats']['total_roles']}")
    log.info(f"  Pending review: {len(pending)}")
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
                        choices=["lever", "greenhouse", "career", "google", "people", "social", "twitter", "proxycurl"],
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
