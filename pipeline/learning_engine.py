#!/usr/bin/env python3
"""
PROSPERITY — Learning Engine
=============================

Analyzes historical approve/reject decisions to auto-classify future roles.
Builds rejection patterns from rejected titles and approval patterns from
approved ones. Over time, fewer roles need manual review.

The learning is simple pattern matching, not ML:
  1. Extract common words/phrases from rejected titles
  2. Track which funds + sources produce noise vs signal
  3. Score new roles against these patterns
  4. High-confidence auto-reject/approve, uncertain → pending review

This file is imported by pipeline.py during each scrape run.
"""

import json
import re
import logging
from collections import Counter
from pathlib import Path

log = logging.getLogger("prosperity.learning")

DECISIONS_DIR = Path("./public/data")
APPROVED_FILE = DECISIONS_DIR / "approved_roles.json"
DECISIONS_FILE = DECISIONS_DIR / "latest_decisions.json"
LEARNING_FILE = DECISIONS_DIR / "learning_model.json"


def load_decision_history() -> dict:
    """Load all historical approve/reject decisions with metadata."""
    approved_data = {}
    if APPROVED_FILE.exists():
        try:
            approved_data = json.loads(APPROVED_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        "approved_hashes": set(approved_data.get("hashes", [])),
        "rejected_hashes": set(approved_data.get("rejected", [])),
        "decision_history": approved_data.get("decision_history", []),
    }


def build_patterns(decision_history: list) -> dict:
    """
    Analyze decision history to build rejection/approval patterns.
    Returns a model dict with word frequencies, source scores, and fund scores.
    """
    rejected_titles = []
    approved_titles = []
    rejected_sources = Counter()
    approved_sources = Counter()
    rejected_funds = Counter()
    approved_funds = Counter()

    for d in decision_history:
        title = d.get("title", "").lower()
        source = d.get("source", "")
        fund = d.get("fund_name", "")

        if d.get("decision") == "rejected":
            rejected_titles.append(title)
            rejected_sources[source] += 1
            rejected_funds[fund] += 1
        elif d.get("decision") == "approved":
            approved_titles.append(title)
            approved_sources[source] += 1
            approved_funds[fund] += 1

    # Extract word frequencies from titles
    stop_words = {"the", "a", "an", "and", "or", "in", "at", "of", "for", "to", "is", "on", "-", "–", "|"}

    def extract_words(titles):
        words = Counter()
        for t in titles:
            for w in re.findall(r'\b[a-z]+\b', t):
                if w not in stop_words and len(w) > 2:
                    words[w] += 1
        return words

    reject_words = extract_words(rejected_titles)
    approve_words = extract_words(approved_titles)

    # Compute word signals: words that appear much more in rejects than approves
    reject_signals = {}
    for word, count in reject_words.items():
        approve_count = approve_words.get(word, 0)
        if count >= 3 and count > approve_count * 2:
            reject_signals[word] = count / max(approve_count, 1)

    approve_signals = {}
    for word, count in approve_words.items():
        reject_count = reject_words.get(word, 0)
        if count >= 2 and count > reject_count * 2:
            approve_signals[word] = count / max(reject_count, 1)

    model = {
        "reject_word_signals": dict(sorted(reject_signals.items(), key=lambda x: -x[1])[:50]),
        "approve_word_signals": dict(sorted(approve_signals.items(), key=lambda x: -x[1])[:50]),
        "rejected_source_rates": {},
        "total_decisions": len(decision_history),
        "total_rejected": len(rejected_titles),
        "total_approved": len(approved_titles),
    }

    # Source rejection rates
    for source in set(list(rejected_sources.keys()) + list(approved_sources.keys())):
        total = rejected_sources.get(source, 0) + approved_sources.get(source, 0)
        if total >= 3:
            model["rejected_source_rates"][source] = rejected_sources.get(source, 0) / total

    return model


def score_role(role_title: str, role_source: str, role_fund: str, model: dict) -> tuple:
    """
    Score a role against the learned model.
    Returns (score, recommendation) where:
      score: -1.0 (definitely reject) to 1.0 (definitely approve)
      recommendation: "auto_reject" | "auto_approve" | "pending"
    """
    if not model or model.get("total_decisions", 0) < 10:
        # Not enough data to learn from yet
        return 0.0, "pending"

    title_lower = role_title.lower()
    words = set(re.findall(r'\b[a-z]+\b', title_lower))

    reject_signals = model.get("reject_word_signals", {})
    approve_signals = model.get("approve_word_signals", {})

    # Word-based score
    reject_score = sum(reject_signals.get(w, 0) for w in words)
    approve_score = sum(approve_signals.get(w, 0) for w in words)

    # Source-based adjustment
    source_reject_rate = model.get("rejected_source_rates", {}).get(role_source, 0.5)
    source_adjustment = (source_reject_rate - 0.5) * 0.5  # -0.25 to 0.25

    # Combine scores
    if reject_score + approve_score == 0:
        score = -source_adjustment  # Only source info available
    else:
        word_score = (approve_score - reject_score) / (approve_score + reject_score)
        score = word_score * 0.7 + (-source_adjustment) * 0.3

    # Clamp
    score = max(-1.0, min(1.0, score))

    # Thresholds for auto-classification
    if score > 0.6:
        return score, "auto_approve"
    elif score < -0.6:
        return score, "auto_reject"
    else:
        return score, "pending"


def load_or_build_model() -> dict:
    """Load cached model or build from scratch."""
    # Try cached model first
    if LEARNING_FILE.exists():
        try:
            model = json.loads(LEARNING_FILE.read_text())
            if model.get("total_decisions", 0) > 0:
                return model
        except (json.JSONDecodeError, KeyError):
            pass

    # Build from decision history
    history = load_decision_history()
    all_decisions = history.get("decision_history", [])

    # Also load from latest_decisions.json if available
    if DECISIONS_FILE.exists():
        try:
            latest = json.loads(DECISIONS_FILE.read_text())
            all_decisions.extend(latest.get("decisions", []))
        except (json.JSONDecodeError, KeyError):
            pass

    if not all_decisions:
        return {"total_decisions": 0}

    model = build_patterns(all_decisions)

    # Cache the model
    try:
        LEARNING_FILE.write_text(json.dumps(model, indent=2))
    except Exception:
        pass

    return model


def classify_role(title: str, source: str, fund_name: str) -> str:
    """
    Classify a role using the learned model.
    Returns "auto_approve", "auto_reject", or "pending".
    """
    model = load_or_build_model()
    _, recommendation = score_role(title, source, fund_name, model)
    return recommendation
