#!/usr/bin/env python3
"""
PROSPERITY — People Registry Builder
=====================================

Builds a watchlist of VC professionals by:
  1. Scraping each fund's team/about/people page
  2. Extracting names, roles, and LinkedIn URLs via LLM
  3. Finding missing LinkedIn URLs via Google Custom Search
  4. Outputting people_registry.json for the social signal scanner

This runs MONTHLY (team pages change slowly) via GitHub Actions.

SOURCES:
  - Fund team pages (e.g., /team, /about, /people) — free
  - Google Custom Search for LinkedIn profile discovery — free (100 queries/day)
  - Claude Haiku for page parsing — ~£0.10 per full run

OUTPUT:
  - people_registry.json — consumed by pipeline.py for social monitoring

USAGE:
  python people_registry.py                     # Full build
  python people_registry.py --fund atomico      # Single fund
  python people_registry.py --linkedin-only     # Just find missing LinkedIn URLs
"""

import os
import sys
import json
import re
import logging
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote_plus

try:
    import requests
except ImportError:
    print("Run: pip install requests"); sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Run: pip install beautifulsoup4"); sys.exit(1)

# Ensure pipeline modules can import each other regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

import llm_classifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prosperity.people")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
TIMEOUT = 15

GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

OUTPUT_DIR = Path(os.getenv("PEOPLE_OUTPUT_DIR", "./public/data"))
REGISTRY_FILE = Path(os.getenv("REGISTRY_FILE", "./public/data/funds_registry.json"))
PEOPLE_FILE = OUTPUT_DIR / "people_registry.json"


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM PAGE DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

TEAM_PAGE_PATHS = [
    "/team", "/about", "/people", "/our-team", "/about-us",
    "/who-we-are", "/about/team", "/about/people",
    "/the-team", "/meet-the-team", "/our-people",
]


def find_team_page_url(website: str) -> str:
    """
    Try common team page paths to find the actual team page URL.
    Returns the first one that responds with 200 and contains people-like content.
    """
    if not website:
        return ""

    base = website.rstrip("/")

    for path in TEAM_PAGE_PATHS:
        url = base + path
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                text_lower = resp.text.lower()
                # Quick check: does this page look like a team page?
                people_signals = ["team", "partner", "associate", "analyst",
                                  "managing director", "principal", "investment",
                                  "linkedin.com/in/"]
                hits = sum(1 for s in people_signals if s in text_lower)
                if hits >= 2:
                    log.info(f"  Found team page: {url} ({hits} signals)")
                    return url
        except requests.RequestException:
            continue

    # Fallback: try the /about page even with fewer signals
    for path in ["/about", "/about-us"]:
        url = base + path
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            continue

    return ""


def scrape_team_page(url: str) -> str:
    """
    Fetch a team page and extract the meaningful text content.
    Strips nav, footer, scripts — returns clean text for LLM parsing.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"  Failed to fetch {url}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()

    # Try to find the main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", {"class": re.compile(r"team|people|about|content", re.I)})
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Also extract LinkedIn URLs from href attributes
    linkedin_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" in href:
            # Get the text near this link (usually the person's name)
            name_text = a.get_text(strip=True) or a.parent.get_text(strip=True) if a.parent else ""
            linkedin_urls.append(f"{name_text}: {href}")

    if linkedin_urls:
        text += "\n\nLINKEDIN URLS FOUND ON PAGE:\n" + "\n".join(linkedin_urls)

    return text


# ═══════════════════════════════════════════════════════════════════════════════
# LINKEDIN PROFILE DISCOVERY VIA GOOGLE
# ═══════════════════════════════════════════════════════════════════════════════

def find_linkedin_profile(person_name: str, fund_name: str) -> str:
    """
    Use Google Custom Search to find a person's LinkedIn profile.
    Returns the LinkedIn URL or empty string.
    """
    if not GOOGLE_CSE_KEY or not GOOGLE_CSE_CX:
        return ""

    query = f'site:linkedin.com/in/ "{person_name}" "{fund_name}"'
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_CSE_KEY,
        "cx": GOOGLE_CSE_CX,
        "q": query,
        "num": 3,
    }

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        for item in items:
            link = item.get("link", "")
            if "linkedin.com/in/" in link:
                # Verify the name appears in the result
                title = item.get("title", "").lower()
                name_parts = person_name.lower().split()
                if any(part in title for part in name_parts if len(part) > 2):
                    return link

    except Exception as e:
        log.debug(f"  Google search failed for {person_name}: {e}")

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_people_for_fund(fund: dict) -> list[dict]:
    """
    Build the people list for a single fund.
    1. Find team page → 2. Scrape it → 3. LLM extract → 4. Find LinkedIn URLs
    """
    fund_name = fund.get("name", "Unknown")
    website = fund.get("website", "")
    fund_id = fund.get("id", "")

    log.info(f"[People] Processing {fund_name}...")

    # Step 1: Find team page
    team_url = find_team_page_url(website)
    if not team_url:
        log.info(f"  No team page found for {fund_name}")
        return []

    # Step 2: Scrape it
    page_text = scrape_team_page(team_url)
    if not page_text or len(page_text) < 50:
        log.info(f"  Team page too sparse for {fund_name}")
        return []

    # Step 3: LLM extraction
    llm_result = llm_classifier.extract_team_from_page(page_text, fund_name)

    if not llm_result or not llm_result.get("people"):
        log.info(f"  No people extracted for {fund_name}")
        # Fallback: try regex extraction for LinkedIn URLs
        return _regex_extract_people(page_text, fund_id, fund_name)

    people = []
    for p in llm_result["people"]:
        person = {
            "name": p.get("name", ""),
            "role": p.get("role", ""),
            "seniority": p.get("seniority", "Other"),
            "fund_id": fund_id,
            "fund_name": fund_name,
            "linkedin_url": p.get("linkedin_url") or "",
            "twitter_handle": p.get("twitter_handle") or "",
            "is_investment_team": p.get("is_investment_team", False),
            "source": "team_page",
            "team_page_url": team_url,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        people.append(person)

    log.info(f"  Extracted {len(people)} people from {fund_name}")

    # Step 4: Find missing LinkedIn URLs via Google
    if GOOGLE_CSE_KEY:
        missing_linkedin = [p for p in people if not p["linkedin_url"] and p["is_investment_team"]]
        log.info(f"  Searching LinkedIn for {len(missing_linkedin)} people...")

        for person in missing_linkedin[:10]:  # Cap at 10 per fund to conserve queries
            linkedin = find_linkedin_profile(person["name"], fund_name)
            if linkedin:
                person["linkedin_url"] = linkedin
                log.info(f"    Found: {person['name']} → {linkedin}")
            time.sleep(0.5)  # Rate limit

    return people


def _regex_extract_people(text: str, fund_id: str, fund_name: str) -> list[dict]:
    """
    Fallback: extract people using regex when LLM is unavailable.
    Looks for LinkedIn URLs and nearby names.
    """
    people = []
    
    # Find LinkedIn profile URLs and associated text
    pattern = r"([\w\s]{3,40})[\s:]*(?:https?://)?(?:www\.)?linkedin\.com/in/([\w-]+)"
    matches = re.findall(pattern, text)
    
    for name_text, linkedin_slug in matches:
        name = name_text.strip()
        # Filter out garbage
        if len(name) < 3 or any(skip in name.lower() for skip in ["click", "view", "http", "www", "follow"]):
            continue

        people.append({
            "name": name,
            "role": "",
            "seniority": "Other",
            "fund_id": fund_id,
            "fund_name": fund_name,
            "linkedin_url": f"https://linkedin.com/in/{linkedin_slug}",
            "twitter_handle": "",
            "is_investment_team": True,  # Assume yes if on team page
            "source": "team_page_regex",
            "team_page_url": "",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })

    return people


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_people_registry(fund_filter: str = None, linkedin_only: bool = False):
    """
    Build the complete people registry.
    """
    # Load fund registry
    if not REGISTRY_FILE.exists():
        log.error(f"Fund registry not found at {REGISTRY_FILE} — run discovery.py first")
        return

    data = json.loads(REGISTRY_FILE.read_text())
    funds = data.get("funds", [])
    log.info(f"[People] Loaded {len(funds)} funds from registry")

    # Filter if requested
    if fund_filter:
        funds = [f for f in funds if f.get("id", "") == fund_filter or fund_filter.lower() in f.get("name", "").lower()]
        log.info(f"[People] Filtered to {len(funds)} funds matching '{fund_filter}'")

    # Load existing registry to merge with
    existing_people = {}
    if PEOPLE_FILE.exists():
        try:
            existing_data = json.loads(PEOPLE_FILE.read_text())
            for p in existing_data.get("people", []):
                key = f"{p.get('fund_id', '')}|{p.get('name', '').lower()}"
                existing_people[key] = p
            log.info(f"[People] Loaded {len(existing_people)} existing people")
        except json.JSONDecodeError:
            pass

    if linkedin_only:
        # Just find missing LinkedIn URLs for existing people
        _fill_missing_linkedin(existing_people)
        _save_registry(list(existing_people.values()))
        return

    # Build people for each fund
    all_people = []
    errors = []

    for fund in funds:
        try:
            people = build_people_for_fund(fund)
            all_people.extend(people)
        except Exception as e:
            err = f"{fund.get('name', '?')}: {str(e)}"
            log.error(f"[People] Error — {err}")
            errors.append(err)

        time.sleep(1)  # Be polite between funds

    # Merge with existing: keep existing data, update with new
    for person in all_people:
        key = f"{person['fund_id']}|{person['name'].lower()}"
        if key in existing_people:
            # Update fields but keep LinkedIn URL if we had it
            old = existing_people[key]
            if old.get("linkedin_url") and not person.get("linkedin_url"):
                person["linkedin_url"] = old["linkedin_url"]
        existing_people[key] = person

    _save_registry(list(existing_people.values()), errors)


def _fill_missing_linkedin(people: dict):
    """Find LinkedIn URLs for people who don't have one yet."""
    if not GOOGLE_CSE_KEY:
        log.warning("[People] No Google CSE key — can't search for LinkedIn profiles")
        return

    missing = [p for p in people.values()
               if not p.get("linkedin_url") and p.get("is_investment_team")]
    log.info(f"[People] Searching LinkedIn for {len(missing)} people without profiles")

    found = 0
    for person in missing[:80]:  # Cap to stay within daily quota
        url = find_linkedin_profile(person["name"], person["fund_name"])
        if url:
            person["linkedin_url"] = url
            found += 1
        time.sleep(0.5)

    log.info(f"[People] Found {found}/{len(missing)} LinkedIn profiles")


def _save_registry(people: list, errors: list = None):
    """Write the people registry to disk."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Stats
    investment_team = [p for p in people if p.get("is_investment_team")]
    with_linkedin = [p for p in people if p.get("linkedin_url")]

    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_people": len(people),
            "investment_team": len(investment_team),
            "with_linkedin": len(with_linkedin),
            "funds_covered": len(set(p["fund_id"] for p in people)),
            "errors": errors or [],
        },
        "people": people,
    }

    PEOPLE_FILE.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    log.info(f"[People] Registry written to {PEOPLE_FILE}")
    log.info("=" * 60)
    log.info(f"  PEOPLE REGISTRY — BUILD COMPLETE")
    log.info(f"  Total people:     {len(people)}")
    log.info(f"  Investment team:  {len(investment_team)}")
    log.info(f"  With LinkedIn:    {len(with_linkedin)}")
    log.info(f"  Funds covered:    {registry['stats']['funds_covered']}")
    log.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prosperity People Registry Builder")
    parser.add_argument("--fund", help="Process a single fund by ID or name")
    parser.add_argument("--linkedin-only", action="store_true",
                        help="Only search for missing LinkedIn URLs")
    args = parser.parse_args()

    run_people_registry(fund_filter=args.fund, linkedin_only=args.linkedin_only)
