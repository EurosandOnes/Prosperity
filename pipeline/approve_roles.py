#!/usr/bin/env python3
"""
PROSPERITY — Role Approval Processor
=====================================

Processes approved role hashes and merges them into approved_roles.json.
Called by the admin page or email digest approval flow.

USAGE:
  python approve_roles.py --approve hash1 hash2 hash3
  python approve_roles.py --reject hash1 hash2
  python approve_roles.py --approve-all        # Approve everything pending
  python approve_roles.py --list               # Show pending roles
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

OUTPUT_DIR = Path("./public/data")
PENDING_FILE = OUTPUT_DIR / "pending_roles.json"
APPROVED_FILE = OUTPUT_DIR / "approved_roles.json"


def load_approved():
    if APPROVED_FILE.exists():
        try:
            return json.loads(APPROVED_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"hashes": [], "approved_at": {}}


def save_approved(data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED_FILE.write_text(json.dumps(data, indent=2))


def load_pending():
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text())
        return data.get("roles", [])
    except json.JSONDecodeError:
        return []


def approve(hashes, role_metadata=None):
    data = load_approved()
    now = datetime.now(timezone.utc).isoformat()
    if "decision_history" not in data:
        data["decision_history"] = []
    added = 0
    for h in hashes:
        if h not in data["hashes"]:
            data["hashes"].append(h)
            data["approved_at"][h] = now
            # Store metadata for learning engine
            if role_metadata and h in role_metadata:
                data["decision_history"].append({
                    **role_metadata[h],
                    "decision": "approved",
                    "decided_at": now,
                })
            added += 1
    save_approved(data)
    print(f"Approved {added} new roles ({len(data['hashes'])} total approved)")


def reject(hashes, role_metadata=None):
    """Rejecting = don't approve. Track rejections to avoid re-showing and for learning."""
    data = load_approved()
    if "rejected" not in data:
        data["rejected"] = []
    if "decision_history" not in data:
        data["decision_history"] = []
    now = datetime.now(timezone.utc).isoformat()
    for h in hashes:
        if h not in data["rejected"]:
            data["rejected"].append(h)
            if role_metadata and h in role_metadata:
                data["decision_history"].append({
                    **role_metadata[h],
                    "decision": "rejected",
                    "decided_at": now,
                })
    save_approved(data)
    print(f"Rejected {len(hashes)} roles")


def approve_all():
    pending = load_pending()
    hashes = [r.get("dedup_hash", "") for r in pending if r.get("dedup_hash")]
    if not hashes:
        print("No pending roles to approve")
        return
    approve(hashes)


def list_pending():
    pending = load_pending()
    if not pending:
        print("No pending roles")
        return
    
    approved_data = load_approved()
    approved_set = set(approved_data.get("hashes", []))
    rejected_set = set(approved_data.get("rejected", []))

    for r in pending:
        h = r.get("dedup_hash", "")
        status = "✓" if h in approved_set else ("✗" if h in rejected_set else "?")
        print(f"  [{status}] {h[:8]} | {r.get('fund_name', '?'):25s} | {r.get('title', '?'):40s} | {r.get('source', '?')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prosperity Role Approval")
    parser.add_argument("--approve", nargs="+", help="Approve role hashes")
    parser.add_argument("--reject", nargs="+", help="Reject role hashes")
    parser.add_argument("--approve-all", action="store_true", help="Approve all pending")
    parser.add_argument("--list", action="store_true", help="List pending roles")
    args = parser.parse_args()

    if args.approve:
        approve(args.approve)
    elif args.reject:
        reject(args.reject)
    elif args.approve_all:
        approve_all()
    elif args.list:
        list_pending()
    else:
        parser.print_help()
