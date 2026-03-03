#!/usr/bin/env python3
"""
PROSPERITY — VC Fund Auto-Discovery Engine
===========================================

Automatically discovers and registers London VC funds by:
  1. Scraping public VC directory websites (free, no API keys)
  2. Cross-referencing across multiple sources for confidence
  3. Auto-probing fund websites to detect ATS systems (Lever, Greenhouse, Ashby)
  4. Finding LinkedIn company pages via Google
  5. Generating fund configs ready for the scraping pipeline

SOURCES (all free, public HTML):
  - Gilion VC Mapping (gilion.com)
  - Seedtable Investor Rankings (seedtable.com)
  - Google Search for emerging funds

AUTO-DETECTION:
  - Lever:      GET api.lever.co/v0/postings/{slug} → 200 = uses Lever
  - Greenhouse: GET boards-api.greenhouse.io/v1/boards/{slug}/jobs → 200 = uses Greenhouse
  - Ashby:      GET api.ashbyhq.com/posting-api/job-board/{slug} → 200 = uses Ashby

OUTPUT:
  - funds_registry.json — machine-readable fund registry
  - discovery_report.json — human-readable discovery log

USAGE:
  python discovery.py                    # Full discovery run
  python discovery.py --probe-only       # Just re-probe ATS for existing funds
  python discovery.py --source seedtable # Only scrape one directory

DEPLOYMENT:
  Run weekly via GitHub Actions (separate from the 6-hourly scrape job)
  to catch newly launched funds.
"""

import os
import sys
import json
import re
import hashlib
import logging
import argparse
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, quote_plus

try:
    import requests
except ImportError:
    print("Run: pip install requests"); sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Run: pip install beautifulsoup4"); sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("discovery")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
TIMEOUT = 12

# Google Custom Search (optional — enables LinkedIn URL discovery)
GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

OUTPUT_DIR = Path(os.getenv("DISCOVERY_OUTPUT_DIR", "./public/data"))
REGISTRY_FILE = OUTPUT_DIR / "funds_registry.json"
REPORT_FILE = OUTPUT_DIR / "discovery_report.json"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DiscoveredFund:
    """A fund found via directory scraping."""
    name: str
    website: str = ""
    description: str = ""
    focus_stage: str = ""           # "Pre-seed", "Seed", "Series A", etc.
    focus_sector: str = ""          # "Fintech", "Deep Tech", etc.
    location: str = "London"
    aum: str = ""
    founded: int = 0
    # Auto-populated fields
    id: str = ""                    # Slug derived from name
    initials: str = ""              # First letters of name words
    # ATS detection results
    lever_slug: str = ""
    greenhouse_slug: str = ""
    ashby_slug: str = ""
    careers_url: str = ""
    # LinkedIn
    linkedin_url: str = ""
    twitter_handle: str = ""
    # Discovery metadata
    sources: list = field(default_factory=list)  # Which directories found this fund
    confidence: float = 0.0         # 0-1, higher = found in more sources
    first_seen: str = ""
    last_verified: str = ""
    # Map coordinates (auto-assigned based on neighborhood clustering)
    map_x: float = 0
    map_y: float = 0

    def __post_init__(self):
        if not self.id:
            self.id = self._make_slug(self.name)
        if not self.initials:
            self.initials = self._make_initials(self.name)
        if not self.first_seen:
            self.first_seen = datetime.now(timezone.utc).isoformat()
        self.last_verified = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _make_slug(name):
        s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        # Remove common suffixes
        for suffix in ["-capital", "-ventures", "-vc", "-partners", "-fund"]:
            if s.endswith(suffix) and len(s) > len(suffix) + 2:
                s = s[:-len(suffix)]
        return s

    @staticmethod
    def _make_initials(name):
        # Skip common words
        skip = {"the", "of", "and", "in", "for", "capital", "ventures", "partners", "fund", "group"}
        words = [w for w in name.split() if w.lower() not in skip]
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        elif words:
            return words[0][:2].upper()
        return name[:2].upper()


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def safe_get(url, **kwargs):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.debug(f"GET failed: {url} — {e}")
        return None


def normalize_fund_name(name):
    """Normalize for dedup comparison."""
    n = name.strip()
    # Remove legal suffixes
    for suffix in [" Ltd", " LLP", " Limited", " Inc", " LLC", " Plc"]:
        n = n.replace(suffix, "")
    return n.strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECTORY SCRAPERS
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_gilion():
    """
    Gilion (formerly Ark Kapital) publishes a curated VC mapping page.
    URL: https://vc-mapping.gilion.com/venture-capital-firms/london
    Structured list of 50+ London VC funds with names, descriptions, and links.
    """
    url = "https://vc-mapping.gilion.com/venture-capital-firms/london"
    log.info(f"[Gilion] Scraping {url}")

    resp = safe_get(url)
    if not resp:
        log.warning("[Gilion] Failed to fetch page")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    funds = []

    # Gilion uses structured cards/sections for each fund
    # Look for fund name patterns in headings and links
    for el in soup.find_all(["h2", "h3", "h4", "a"]):
        text = el.get_text(strip=True)
        href = el.get("href", "")

        # Filter for likely fund names (skip generic headings)
        if len(text) < 3 or len(text) > 60:
            continue
        if any(skip in text.lower() for skip in ["london", "venture capital", "startup", "read more", "learn more", "subscribe", "cookie"]):
            continue

        # Check if it links to a fund website
        if href and href.startswith("http") and "gilion" not in href:
            fund = DiscoveredFund(
                name=normalize_fund_name(text),
                website=href,
                sources=["gilion"],
            )
            funds.append(fund)

    log.info(f"[Gilion] Found {len(funds)} potential funds")
    return funds


def scrape_seedtable():
    """
    Seedtable publishes a data-driven ranking of London's most active investors.
    URL: https://www.seedtable.com/investors-london
    Typically 30+ funds with names, descriptions, and Seedtable scores.
    """
    url = "https://www.seedtable.com/investors-london"
    log.info(f"[Seedtable] Scraping {url}")

    resp = safe_get(url)
    if not resp:
        log.warning("[Seedtable] Failed to fetch page")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    funds = []

    # Seedtable typically uses card-style layouts with fund names in headings
    for card in soup.find_all(["article", "div"], class_=True):
        classes = " ".join(card.get("class", []))
        # Look for investor/fund card patterns
        heading = card.find(["h2", "h3", "h4"])
        if not heading:
            continue

        name = heading.get_text(strip=True)
        if len(name) < 3 or len(name) > 60:
            continue

        # Try to find website link
        link = card.find("a", href=True)
        website = ""
        if link:
            href = link.get("href", "")
            if href.startswith("http") and "seedtable" not in href:
                website = href

        # Try to find description
        desc_el = card.find("p")
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

        fund = DiscoveredFund(
            name=normalize_fund_name(name),
            website=website,
            description=desc,
            sources=["seedtable"],
        )
        funds.append(fund)

    log.info(f"[Seedtable] Found {len(funds)} potential funds")
    return funds


def scrape_google_emerging():
    """
    Use Google Custom Search to find recently launched London VC funds
    that might not be in established directories yet.
    
    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX env vars.
    """
    if not GOOGLE_CSE_KEY or not GOOGLE_CSE_CX:
        log.info("[Google] No API key set — skipping emerging fund discovery")
        return []

    queries = [
        '"london" "venture capital" "new fund" site:techcrunch.com OR site:sifted.eu',
        '"london" "vc fund" "launched" OR "raised" 2025',
        '"london" "first close" "venture" 2025',
    ]

    funds = []
    for query in queries:
        params = {
            "key": GOOGLE_CSE_KEY,
            "cx": GOOGLE_CSE_CX,
            "q": query,
            "dateRestrict": "m6",  # Last 6 months
            "num": 10,
        }

        log.info(f"[Google] Searching: {query[:60]}...")
        resp = safe_get("https://www.googleapis.com/customsearch/v1", params=params)
        if not resp:
            continue

        for item in resp.json().get("items", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")

            # Try to extract fund name from title/snippet
            fund_name = extract_fund_name_from_text(f"{title} {snippet}")
            if fund_name:
                fund = DiscoveredFund(
                    name=fund_name,
                    description=snippet[:300],
                    sources=["google_search"],
                )
                funds.append(fund)

        time.sleep(0.5)  # Rate limit courtesy

    log.info(f"[Google] Found {len(funds)} potential emerging funds")
    return funds


def extract_fund_name_from_text(text):
    """Extract a VC fund name from article titles/snippets."""
    # Patterns like "X Capital launches...", "X Ventures raises..."
    patterns = [
        r"([\w\s]+(?:Capital|Ventures|Partners|VC|Fund))\s+(?:launches|raises|closes|announces|secures)",
        r"(?:new fund|new vc|new venture)\s+(?:from\s+)?([\w\s]+(?:Capital|Ventures|Partners))",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if 3 < len(name) < 50:
                return normalize_fund_name(name)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWN FUND SEED LIST
# ═══════════════════════════════════════════════════════════════════════════════
# These are confirmed London VC funds compiled from research.
# The directory scrapers ADD to this list; they don't replace it.
# This ensures we always have a baseline even if scrapers break.

SEED_FUNDS = [
    # ── Tier 1: Large, well-known London VCs ──
    {"name": "Index Ventures", "website": "https://www.indexventures.com", "focus_stage": "Multi-stage", "aum": "€3.2B", "founded": 1996},
    {"name": "Atomico", "website": "https://www.atomico.com", "focus_stage": "Growth", "aum": "€4.5B", "founded": 2006},
    {"name": "Balderton Capital", "website": "https://www.balderton.com", "focus_stage": "Early Stage", "aum": "€3.7B", "founded": 2000},
    {"name": "Northzone", "website": "https://northzone.com", "focus_stage": "Early Stage", "aum": "€2.5B", "founded": 1996},
    {"name": "LocalGlobe", "website": "https://localglobe.vc", "focus_stage": "Pre-seed / Seed", "aum": "€900M", "founded": 2015},
    {"name": "Seedcamp", "website": "https://seedcamp.com", "focus_stage": "Pre-seed / Seed", "aum": "€400M", "founded": 2007},
    {"name": "Accel", "website": "https://www.accel.com", "focus_stage": "Multi-stage", "aum": "$3B", "founded": 1983},
    {"name": "Octopus Ventures", "website": "https://octopusventures.com", "focus_stage": "Early Stage", "aum": "£1.9B", "founded": 2000},
    {"name": "EQT Ventures", "website": "https://eqtventures.com", "focus_stage": "Growth", "aum": "€3B", "founded": 2016},
    {"name": "Felix Capital", "website": "https://www.felixcapital.com", "focus_stage": "Consumer", "aum": "€1B", "founded": 2015},
    {"name": "Dawn Capital", "website": "https://dawncapital.com", "focus_stage": "B2B / Enterprise", "aum": "€1B", "founded": 2007},

    # ── Tier 2: Established mid-size funds ──
    {"name": "Notion Capital", "website": "https://notion.vc", "focus_stage": "B2B / Enterprise", "aum": "€600M", "founded": 2009},
    {"name": "Blossom Capital", "website": "https://www.blossomcap.com", "focus_stage": "Early Stage", "aum": "€500M", "founded": 2017},
    {"name": "Creandum", "website": "https://www.creandum.com", "focus_stage": "Early Stage", "aum": "€1B", "founded": 2003},
    {"name": "Molten Ventures", "website": "https://moltenventures.com", "focus_stage": "Growth", "aum": "£1.4B", "founded": 2000},
    {"name": "83North", "website": "https://www.83north.com", "focus_stage": "Growth", "aum": "$1.8B", "founded": 2006},
    {"name": "Mosaic Ventures", "website": "https://www.mosaic.vc", "focus_stage": "Deep Tech", "aum": "€400M", "founded": 2014},
    {"name": "MMC Ventures", "website": "https://mmc.vc", "focus_stage": "Early Stage", "aum": "£400M", "founded": 2000},
    {"name": "Hoxton Ventures", "website": "https://www.hoxtonventures.com", "focus_stage": "Pre-seed / Seed", "aum": "€200M", "founded": 2013},
    {"name": "Playfair Capital", "website": "https://www.playfaircapital.com", "focus_stage": "Pre-seed / Seed", "aum": "£150M", "founded": 2013},
    {"name": "Passion Capital", "website": "https://www.passioncapital.com", "focus_stage": "Pre-seed / Seed", "aum": "£100M", "founded": 2011},
    {"name": "Flashpoint VC", "website": "https://flashpoint.vc", "focus_stage": "Secondaries", "aum": "€500M", "founded": 2019},
    {"name": "Anthemis", "website": "https://www.anthemis.com", "focus_stage": "Early Stage", "focus_sector": "Fintech", "aum": "$1B", "founded": 2010},
    {"name": "Air Street Capital", "website": "https://www.airstreet.com", "focus_stage": "Pre-seed / Seed", "focus_sector": "AI", "aum": "£100M", "founded": 2019},
    {"name": "Stride VC", "website": "https://stride.vc", "focus_stage": "Pre-seed / Seed", "aum": "£100M", "founded": 2018},
    {"name": "Connect Ventures", "website": "https://www.connectventures.co", "focus_stage": "Pre-seed / Seed", "focus_sector": "Product/UX", "aum": "£80M", "founded": 2012},
    {"name": "firstminute capital", "website": "https://firstminute.capital", "focus_stage": "Pre-seed / Seed", "aum": "$100M", "founded": 2017},

    # ── Tier 3: Smaller / specialist funds ──
    {"name": "Augmentum Fintech", "website": "https://augmentum.vc", "focus_stage": "Early Stage", "focus_sector": "Fintech", "aum": "£200M", "founded": 2018},
    {"name": "Talis Capital", "website": "https://taliscapital.com", "focus_stage": "Early Stage", "aum": "£200M", "founded": 2015},
    {"name": "Kindred Capital", "website": "https://kindredcapital.vc", "focus_stage": "Pre-seed / Seed", "aum": "£100M", "founded": 2015},
    {"name": "Concept Ventures", "website": "https://www.conceptventures.vc", "focus_stage": "Pre-seed / Seed", "aum": "£50M", "founded": 2020},
    {"name": "Moonfire Ventures", "website": "https://moonfire.com", "focus_stage": "Pre-seed / Seed", "aum": "€60M", "founded": 2020},
    {"name": "Episode 1", "website": "https://episode1.com", "focus_stage": "Pre-seed / Seed", "aum": "£50M", "founded": 2013},
    {"name": "Bethnal Green Ventures", "website": "https://bethnalgreenventures.com", "focus_stage": "Pre-seed / Seed", "focus_sector": "Impact", "aum": "£30M", "founded": 2012},
    {"name": "Seraphim Space", "website": "https://seraphim.vc", "focus_stage": "Early Stage", "focus_sector": "SpaceTech", "aum": "£300M", "founded": 2016},
    {"name": "Amadeus Capital", "website": "https://amadeuscapital.com", "focus_stage": "Early Stage", "aum": "$1B", "founded": 1997},
    {"name": "AlbionVC", "website": "https://albionvc.com", "focus_stage": "Early Stage", "aum": "£500M", "founded": 2009},
    {"name": "Fuel Ventures", "website": "https://fuelventures.com", "focus_stage": "Pre-seed / Seed", "aum": "£80M", "founded": 2014},
    {"name": "Ascension Ventures", "website": "https://ascensionventures.com", "focus_stage": "Pre-seed / Seed", "focus_sector": "Impact", "aum": "£50M", "founded": 2015},
    {"name": "IQ Capital", "website": "https://iqcapital.vc", "focus_stage": "Pre-seed / Seed", "focus_sector": "Deep Tech", "aum": "£300M", "founded": 2005},
    {"name": "Entrepreneur First", "website": "https://www.joinef.com", "focus_stage": "Pre-seed / Seed", "aum": "£150M", "founded": 2011},
    {"name": "Forward Partners", "website": "https://forwardpartners.com", "focus_stage": "Pre-seed / Seed", "aum": "£100M", "founded": 2013},
    {"name": "Ada Ventures", "website": "https://www.adaventures.com", "focus_stage": "Pre-seed / Seed", "focus_sector": "Impact", "aum": "£60M", "founded": 2019},
    {"name": "Pitchdrive", "website": "https://www.pitchdrive.com", "focus_stage": "Pre-seed / Seed", "aum": "€50M", "founded": 2020},
    {"name": "Giant Ventures", "website": "https://giantventures.com", "focus_stage": "Pre-seed / Seed", "focus_sector": "Impact", "aum": "€100M", "founded": 2018},
    {"name": "Lakestar", "website": "https://www.lakestar.com", "focus_stage": "Multi-stage", "aum": "€1B", "founded": 2012},
    {"name": "General Catalyst", "website": "https://www.generalcatalyst.com", "focus_stage": "Multi-stage", "aum": "$25B", "founded": 2000},
    {"name": "GV", "website": "https://www.gv.com", "focus_stage": "Multi-stage", "aum": "$8B", "founded": 2009},
    {"name": "Lightspeed Venture Partners", "website": "https://lsvp.com", "focus_stage": "Multi-stage", "aum": "$10B", "founded": 2000},
    {"name": "Sapphire Ventures", "website": "https://sapphireventures.com", "focus_stage": "Growth", "aum": "$9B", "founded": 2011},
    {"name": "Singular", "website": "https://singular.vc", "focus_stage": "Pre-seed / Seed", "focus_sector": "Deep Tech", "aum": "€100M", "founded": 2014},
    {"name": "Backed VC", "website": "https://backed.vc", "focus_stage": "Pre-seed / Seed", "aum": "€50M", "founded": 2015},
    {"name": "Emerge Education", "website": "https://emerge.education", "focus_stage": "Pre-seed / Seed", "focus_sector": "EdTech", "aum": "£30M", "founded": 2014},
]


# ═══════════════════════════════════════════════════════════════════════════════
# ATS AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_slugs(name, website=""):
    """Generate candidate slugs from a fund name and website for ATS probing."""
    slugs = set()

    # From name: "Balderton Capital" → "balderton", "baldertoncapital", "balderton-capital"
    words = re.sub(r"[^a-z0-9\s]", "", name.lower()).split()
    skip = {"the", "of", "and", "in", "for"}
    meaningful = [w for w in words if w not in skip]

    if meaningful:
        slugs.add(meaningful[0])                          # "balderton"
        slugs.add("".join(meaningful))                    # "baldertoncapital"
        slugs.add("-".join(meaningful))                   # "balderton-capital"
        if len(meaningful) >= 2:
            slugs.add(meaningful[0] + meaningful[1])      # "baldertoncapital"
            slugs.add(f"{meaningful[0]}-{meaningful[1]}") # "balderton-capital"

    # From website domain: "www.balderton.com" → "balderton"
    if website:
        domain = urlparse(website).netloc.replace("www.", "")
        base = domain.split(".")[0]
        slugs.add(base)

    return list(slugs)


def probe_lever(slugs):
    """Test if any slug resolves to a valid Lever job board."""
    for slug in slugs:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):  # Lever returns a list of postings
                    log.info(f"  [Lever] ✓ Found: {slug} ({len(data)} postings)")
                    return slug
        except Exception:
            pass
    return ""


def probe_greenhouse(slugs):
    """Test if any slug resolves to a valid Greenhouse job board."""
    for slug in slugs:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if "jobs" in data:
                    n = len(data["jobs"])
                    log.info(f"  [Greenhouse] ✓ Found: {slug} ({n} jobs)")
                    return slug
        except Exception:
            pass
    return ""


def probe_ashby(slugs):
    """Test if any slug resolves to a valid Ashby job board."""
    for slug in slugs:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if "jobs" in data:
                    n = len(data["jobs"])
                    log.info(f"  [Ashby] ✓ Found: {slug} ({n} jobs)")
                    return slug
        except Exception:
            pass
    return ""


def detect_careers_url(website):
    """Try to find the careers page on a fund's website."""
    if not website:
        return ""

    candidates = [
        f"{website.rstrip('/')}/careers",
        f"{website.rstrip('/')}/jobs",
        f"{website.rstrip('/')}/join",
        f"{website.rstrip('/')}/team#careers",
        f"{website.rstrip('/')}/about/careers",
    ]

    for url in candidates:
        try:
            resp = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                return url
        except Exception:
            pass

    return ""


def find_linkedin_via_google(fund_name):
    """Use Google to find a fund's LinkedIn company page."""
    if not GOOGLE_CSE_KEY or not GOOGLE_CSE_CX:
        return ""

    query = f'site:linkedin.com/company "{fund_name}"'
    params = {
        "key": GOOGLE_CSE_KEY,
        "cx": GOOGLE_CSE_CX,
        "q": query,
        "num": 3,
    }

    resp = safe_get("https://www.googleapis.com/customsearch/v1", params=params)
    if not resp:
        return ""

    for item in resp.json().get("items", []):
        link = item.get("link", "")
        if "linkedin.com/company/" in link:
            # Clean URL
            return link.split("?")[0].rstrip("/")

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# MAP COORDINATE ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

def assign_map_coordinates(funds):
    """
    Auto-assign x,y map positions for the city view.
    Distributes funds in a grid pattern to avoid overlap.
    Uses a spiral layout from center outward.
    """
    import math

    n = len(funds)
    cx, cy = 50, 50  # Center of map (percentage)

    for i, fund in enumerate(funds):
        if fund.map_x != 0 and fund.map_y != 0:
            continue  # Already has coordinates

        # Spiral layout
        angle = i * 2.399  # Golden angle in radians
        radius = 8 + (i * 1.8)  # Grow outward
        radius = min(radius, 35)  # Cap at edges

        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)

        # Clamp to valid map area (10-90%)
        fund.map_x = max(10, min(90, round(x, 1)))
        fund.map_y = max(10, min(90, round(y, 1)))


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def merge_funds(all_discovered):
    """
    Deduplicate and merge funds from multiple sources.
    Higher confidence = found in more sources.
    """
    merged = {}

    for fund in all_discovered:
        key = slugify(fund.name)

        # Fuzzy match: also try without "capital", "ventures", etc.
        alt_keys = [
            slugify(fund.name.replace("Capital", "").replace("Ventures", "").replace("Partners", "").strip()),
        ]

        matched_key = None
        if key in merged:
            matched_key = key
        else:
            for ak in alt_keys:
                if ak and ak in merged:
                    matched_key = ak
                    break

        if matched_key:
            existing = merged[matched_key]
            # Merge data: keep non-empty values, accumulate sources
            if fund.website and not existing.website:
                existing.website = fund.website
            if fund.description and len(fund.description) > len(existing.description):
                existing.description = fund.description
            if fund.aum and not existing.aum:
                existing.aum = fund.aum
            if fund.founded and not existing.founded:
                existing.founded = fund.founded
            if fund.focus_stage and not existing.focus_stage:
                existing.focus_stage = fund.focus_stage
            existing.sources = list(set(existing.sources + fund.sources))
        else:
            merged[key] = fund

    # Calculate confidence based on source count
    max_sources = max(len(f.sources) for f in merged.values()) if merged else 1
    for fund in merged.values():
        fund.confidence = len(fund.sources) / max_sources

    return list(merged.values())


def run_discovery(sources=None, probe_ats=True):
    """
    Full discovery pipeline.
    
    1. Load seed funds (always included)
    2. Scrape directories for additional funds
    3. Merge and deduplicate
    4. Probe ATS endpoints for each fund
    5. Find LinkedIn URLs
    6. Assign map coordinates
    7. Output registry
    """
    all_funds = []
    errors = []

    # Step 1: Seed funds (always)
    log.info(f"[Discovery] Loading {len(SEED_FUNDS)} seed funds")
    for sf in SEED_FUNDS:
        fund = DiscoveredFund(
            name=sf["name"],
            website=sf.get("website", ""),
            focus_stage=sf.get("focus_stage", ""),
            focus_sector=sf.get("focus_sector", ""),
            aum=sf.get("aum", ""),
            founded=sf.get("founded", 0),
            sources=["seed_list"],
        )
        all_funds.append(fund)

    # Step 2: Scrape directories
    source_map = {
        "gilion": scrape_gilion,
        "seedtable": scrape_seedtable,
        "google": scrape_google_emerging,
    }

    active_sources = sources or list(source_map.keys())
    for src_name in active_sources:
        scraper = source_map.get(src_name)
        if not scraper:
            continue
        try:
            found = scraper()
            all_funds.extend(found)
        except Exception as e:
            err = f"{src_name}: {str(e)}"
            log.error(f"[Discovery] Scraper error — {err}")
            errors.append(err)

    # Step 3: Merge and deduplicate
    log.info(f"[Discovery] Merging {len(all_funds)} raw entries...")
    merged = merge_funds(all_funds)
    log.info(f"[Discovery] After dedup: {len(merged)} unique funds")

    # Step 4: Probe ATS (optional, takes time)
    if probe_ats:
        log.info("[Discovery] Probing ATS endpoints...")
        for fund in merged:
            slugs = generate_slugs(fund.name, fund.website)
            log.info(f"  Probing {fund.name} ({len(slugs)} slug candidates)...")

            if not fund.lever_slug:
                fund.lever_slug = probe_lever(slugs)
            if not fund.greenhouse_slug:
                fund.greenhouse_slug = probe_greenhouse(slugs)
            if not fund.ashby_slug:
                fund.ashby_slug = probe_ashby(slugs)
            if not fund.careers_url:
                fund.careers_url = detect_careers_url(fund.website)

            time.sleep(0.3)  # Don't hammer APIs

    # Step 5: LinkedIn URLs (if Google CSE available)
    if GOOGLE_CSE_KEY:
        log.info("[Discovery] Finding LinkedIn URLs...")
        for fund in merged:
            if not fund.linkedin_url:
                fund.linkedin_url = find_linkedin_via_google(fund.name)
                time.sleep(0.5)

    # Step 6: Assign map coordinates
    assign_map_coordinates(merged)

    # Step 7: Output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Registry — consumed by the pipeline and frontend
    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_funds": len(merged),
        "funds": [asdict(f) for f in merged],
    }
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    log.info(f"[Discovery] Registry written to {REGISTRY_FILE}")

    # Report — human-readable summary
    ats_detected = sum(1 for f in merged if f.lever_slug or f.greenhouse_slug or f.ashby_slug)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_funds_discovered": len(merged),
        "with_ats_detected": ats_detected,
        "with_linkedin": sum(1 for f in merged if f.linkedin_url),
        "with_careers_url": sum(1 for f in merged if f.careers_url),
        "sources_scraped": active_sources,
        "errors": errors,
        "top_confidence": [
            {"name": f.name, "sources": f.sources, "confidence": f.confidence,
             "ats": f.lever_slug or f.greenhouse_slug or f.ashby_slug or "none"}
            for f in sorted(merged, key=lambda x: -x.confidence)[:20]
        ],
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Summary
    log.info("=" * 60)
    log.info("  DISCOVERY COMPLETE")
    log.info(f"  Total funds:       {len(merged)}")
    log.info(f"  ATS detected:      {ats_detected}")
    log.info(f"  LinkedIn found:    {sum(1 for f in merged if f.linkedin_url)}")
    log.info(f"  Careers URL found: {sum(1 for f in merged if f.careers_url)}")
    log.info(f"  Errors:            {len(errors)}")
    log.info("=" * 60)

    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prosperity VC Fund Discovery")
    parser.add_argument("--source", nargs="+", choices=["gilion", "seedtable", "google"],
                        help="Only scrape specific directories")
    parser.add_argument("--probe-only", action="store_true",
                        help="Skip directory scraping, just re-probe ATS for seed funds")
    parser.add_argument("--no-probe", action="store_true",
                        help="Skip ATS probing (faster, directory scraping only)")
    args = parser.parse_args()

    if args.probe_only:
        run_discovery(sources=[], probe_ats=True)
    else:
        run_discovery(sources=args.source, probe_ats=not args.no_probe)
