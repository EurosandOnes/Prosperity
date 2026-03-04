#!/usr/bin/env python3
"""
PROSPERITY — LLM Hiring Signal Classifier
==========================================

Uses Claude Haiku (cheapest, fastest) to:
  1. Determine if unstructured text contains a VC hiring signal
  2. Extract structured role data (title, seniority, fund, location)
  3. Parse messy career page HTML into clean role listings

Cost: ~$0.25/1M input tokens, ~$1.25/1M output tokens
At 200 classifications/day ≈ £1-2/month total.

Requires: ANTHROPIC_API_KEY env var

Falls back to regex-only extraction (pipeline.py's existing logic) 
if API key is not set or if the API call fails.
"""

import os
import json
import logging
import time
from typing import Optional

log = logging.getLogger("prosperity.llm")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 2
RETRY_DELAY = 2

# Try to import the SDK; fall back to requests-based calls
try:
    import anthropic
    HAS_SDK = True
except ImportError:
    HAS_SDK = False
    log.info("[LLM] anthropic SDK not installed — using requests fallback")

try:
    import requests
except ImportError:
    requests = None


def _call_api(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> Optional[str]:
    """
    Call Claude API. Uses SDK if available, otherwise raw requests.
    Returns the text response or None on failure.
    """
    if not ANTHROPIC_API_KEY:
        return None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if HAS_SDK:
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return resp.content[0].text

            elif requests:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": MODEL,
                        "max_tokens": max_tokens,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]

        except Exception as e:
            log.warning(f"[LLM] API call failed (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * (attempt + 1))

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER 1: Is this text a hiring signal?
# ═══════════════════════════════════════════════════════════════════════════════

CLASSIFY_SYSTEM = """You are a hiring signal classifier for venture capital firms. 
Your job is to determine if a piece of text (LinkedIn post, tweet, blog excerpt) 
contains a signal that a VC fund is hiring for an investment or platform role.

RESPOND WITH ONLY valid JSON, no markdown, no explanation. Format:
{
  "is_hiring_signal": true/false,
  "confidence": 0.0-1.0,
  "roles": [
    {
      "title": "Investment Analyst",
      "seniority": "Analyst|Associate|VP|Principal|Partner|Platform|Other",
      "fund_name": "Fund Name or null if unclear",
      "location": "London or wherever mentioned",
      "description": "Brief 1-2 sentence summary of the role"
    }
  ],
  "reasoning": "One sentence explaining your classification"
}

RULES:
- A hiring signal means someone is actively recruiting or announcing an open position
- Include roles at ALL levels: analyst, associate, principal, partner, platform, ops
- "We're growing the team" with no specific role = is_hiring_signal: true, roles: empty list
- Someone discussing hiring trends in general = is_hiring_signal: false
- A post congratulating someone on a new role ≠ hiring signal (role is filled)
- Headhunter/recruiter posts count as signals
- Be generous with classification — false negatives are worse than false positives"""


def classify_hiring_signal(text: str, source_context: str = "") -> Optional[dict]:
    """
    Classify whether text contains a hiring signal.
    Returns parsed JSON dict or None if LLM unavailable.
    
    Args:
        text: The raw text to classify (post, tweet, page excerpt)
        source_context: Optional context like "LinkedIn post by John Smith, Partner at Accel"
    """
    if not ANTHROPIC_API_KEY:
        log.debug("[LLM] No API key — skipping classification")
        return None

    prompt = f"""Classify this text as a hiring signal or not.

SOURCE CONTEXT: {source_context or "Unknown"}

TEXT:
{text[:3000]}"""

    response = _call_api(CLASSIFY_SYSTEM, prompt, max_tokens=512)
    if not response:
        return None

    try:
        # Strip markdown fences if present
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
        if clean.endswith("```"):
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        log.warning(f"[LLM] Failed to parse response as JSON: {response[:200]}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER 2: Extract roles from career page HTML
# ═══════════════════════════════════════════════════════════════════════════════

CAREER_PAGE_SYSTEM = """You are a job listing extractor for venture capital firm career pages.
Given raw text from a VC fund's career/jobs page, extract all open positions.

RESPOND WITH ONLY valid JSON, no markdown. Format:
{
  "roles": [
    {
      "title": "Investment Analyst",
      "seniority": "Analyst|Associate|VP|Principal|Partner|Platform|Other",
      "location": "London",
      "description": "Brief description if available",
      "apply_url": "URL if found in the text, otherwise null"
    }
  ],
  "has_roles": true/false,
  "notes": "Any relevant context (e.g., 'page says check back later', 'speculative applications welcome')"
}

RULES:
- Extract ALL roles, not just investment roles (the pipeline will filter later)
- If the page says "no current openings" or similar, return has_roles: false
- If the page has a general "careers@fund.com" email, note it
- Be precise with titles — don't invent roles that aren't listed
- location defaults to "London" for London-based funds unless stated otherwise"""


def extract_roles_from_career_page(page_text: str, fund_name: str) -> Optional[dict]:
    """
    Extract structured role listings from career page text.
    Returns parsed JSON dict or None if LLM unavailable.
    """
    if not ANTHROPIC_API_KEY:
        return None

    # Truncate very long pages — focus on the content-rich parts
    if len(page_text) > 8000:
        page_text = page_text[:8000]

    prompt = f"""Extract all job listings from this VC fund's career page.

FUND: {fund_name}

PAGE CONTENT:
{page_text}"""

    response = _call_api(CAREER_PAGE_SYSTEM, prompt, max_tokens=1024)
    if not response:
        return None

    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
        if clean.endswith("```"):
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        log.warning(f"[LLM] Failed to parse career page response: {response[:200]}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER 3: Extract people/team from fund team page
# ═══════════════════════════════════════════════════════════════════════════════

TEAM_PAGE_SYSTEM = """You are a team page parser for venture capital fund websites.
Given raw text from a VC fund's team/about/people page, extract team members.

RESPOND WITH ONLY valid JSON, no markdown. Format:
{
  "people": [
    {
      "name": "Sarah Chen",
      "role": "Partner",
      "seniority": "Partner|Principal|VP|Associate|Analyst|Platform|Operations|Other",
      "linkedin_url": "https://linkedin.com/in/... or null",
      "twitter_handle": "@handle or null",
      "is_investment_team": true/false
    }
  ],
  "total_found": 5
}

RULES:
- Extract ALL team members, not just partners
- is_investment_team = true for: Partners, Principals, Associates, Analysts, Investment Managers, VPs
- is_investment_team = false for: Operations, Legal, Finance, HR, Marketing, Admin
- Also include Talent/People team (they post about hiring)
- LinkedIn URLs might appear as links in the page content
- If no LinkedIn URLs are visible, set to null (we'll find them separately)
- Be precise with names — don't guess or abbreviate"""


def extract_team_from_page(page_text: str, fund_name: str) -> Optional[dict]:
    """
    Extract team members from a fund's team/about page.
    Returns parsed JSON dict or None if LLM unavailable.
    """
    if not ANTHROPIC_API_KEY:
        return None

    if len(page_text) > 10000:
        page_text = page_text[:10000]

    prompt = f"""Extract all team members from this VC fund's team page.

FUND: {fund_name}

PAGE CONTENT:
{page_text}"""

    response = _call_api(TEAM_PAGE_SYSTEM, prompt, max_tokens=2048)
    if not response:
        return None

    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
        if clean.endswith("```"):
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        log.warning(f"[LLM] Failed to parse team page response: {response[:200]}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def is_available() -> bool:
    """Check if the LLM classifier is configured and reachable."""
    if not ANTHROPIC_API_KEY:
        log.info("[LLM] No ANTHROPIC_API_KEY set — LLM features disabled")
        return False

    result = _call_api(
        "Respond with exactly: OK",
        "Health check",
        max_tokens=10,
    )
    if result and "OK" in result:
        log.info("[LLM] Claude Haiku reachable and responding")
        return True

    log.warning("[LLM] Claude Haiku not reachable")
    return False
