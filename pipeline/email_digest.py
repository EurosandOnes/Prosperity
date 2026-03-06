#!/usr/bin/env python3
"""
PROSPERITY — Email Digest for Pending Roles
============================================

Reads pending_roles.json and sends a formatted email summary.
Designed to run daily via GitHub Actions.

Requires:
  SMTP_EMAIL — your Gmail address
  SMTP_PASSWORD — Gmail app password (NOT your regular password)
  NOTIFY_EMAIL — where to send the digest (can be same as SMTP_EMAIL)

To get a Gmail app password:
  1. Go to https://myaccount.google.com/apppasswords
  2. Create a new app password for "Prosperity"
  3. Copy the 16-character password
"""

import os
import json
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timezone

PENDING_FILE = Path(os.getenv("PENDING_FILE", "./public/data/pending_roles.json"))
APPROVED_FILE = Path(os.getenv("APPROVED_FILE", "./public/data/approved_roles.json"))

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "") or SMTP_EMAIL
REPO_URL = os.getenv("REPO_URL", "https://github.com/EurosandOnes/Prosperity")


def load_pending():
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text())
        return data.get("roles", [])
    except (json.JSONDecodeError, KeyError):
        return []


def load_approved_hashes():
    if not APPROVED_FILE.exists():
        return set(), set()
    try:
        data = json.loads(APPROVED_FILE.read_text())
        return set(data.get("hashes", [])), set(data.get("rejected", []))
    except (json.JSONDecodeError, KeyError):
        return set(), set()


def build_email_html(pending, approved_hashes, rejected_hashes):
    """Build a clean HTML email with the pending roles."""
    
    # Filter out already-approved and rejected
    new_pending = [r for r in pending 
                   if r.get("dedup_hash", "") not in approved_hashes
                   and r.get("dedup_hash", "") not in rejected_hashes]
    
    if not new_pending:
        return None, 0  # No email needed

    # Group by fund
    by_fund = {}
    for r in new_pending:
        fund = r.get("fund_name", "Unknown")
        if fund not in by_fund:
            by_fund[fund] = []
        by_fund[fund].append(r)

    approve_url = f"{REPO_URL}/actions/workflows/approve.yml"

    rows = ""
    all_hashes = []
    for fund_name, roles in sorted(by_fund.items()):
        for r in roles:
            h = r.get("dedup_hash", "?")
            all_hashes.append(h)
            source_url = r.get("source_url", "")
            link = f'<a href="{source_url}" style="color:#4A9EFF;">View Source</a>' if source_url else "—"
            rows += f"""
            <tr style="border-bottom:1px solid #222;">
                <td style="padding:8px;color:#fff;font-weight:600;">{fund_name}</td>
                <td style="padding:8px;color:#ccc;">{r.get('title', '?')}</td>
                <td style="padding:8px;color:#888;">{r.get('seniority', '—')}</td>
                <td style="padding:8px;color:#888;">{r.get('source', '?')}</td>
                <td style="padding:8px;">{link}</td>
                <td style="padding:8px;color:#666;font-family:monospace;font-size:11px;">{h}</td>
            </tr>"""

    hashes_str = ",".join(all_hashes)

    html = f"""
    <div style="background:#0a0a0a;color:#999;font-family:'Helvetica Neue',Arial,sans-serif;padding:30px;max-width:900px;margin:0 auto;">
        <div style="border-bottom:1px solid #222;padding-bottom:16px;margin-bottom:24px;">
            <h1 style="color:#fff;font-size:22px;margin:0;">PROSPERITY — Pending Roles</h1>
            <p style="color:#666;font-size:13px;margin:4px 0 0;">{len(new_pending)} roles awaiting your review · {datetime.now(timezone.utc).strftime('%d %b %Y')}</p>
        </div>

        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
                <tr style="border-bottom:2px solid #333;">
                    <th style="padding:8px;text-align:left;color:#666;">Fund</th>
                    <th style="padding:8px;text-align:left;color:#666;">Role</th>
                    <th style="padding:8px;text-align:left;color:#666;">Level</th>
                    <th style="padding:8px;text-align:left;color:#666;">Source</th>
                    <th style="padding:8px;text-align:left;color:#666;">Link</th>
                    <th style="padding:8px;text-align:left;color:#666;">Hash</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>

        <div style="margin-top:30px;padding:20px;background:#111;border:1px solid #222;border-radius:6px;">
            <h3 style="color:#fff;margin:0 0 10px;font-size:15px;">How to approve</h3>
            <p style="color:#999;font-size:13px;line-height:1.6;margin:0;">
                Go to <a href="{approve_url}" style="color:#4A9EFF;">GitHub Actions → Approve Roles</a>, click <strong style="color:#fff;">Run workflow</strong>, and paste one of the following:
            </p>
            <ul style="color:#999;font-size:13px;line-height:1.8;margin:10px 0;">
                <li><code style="background:#1a1a1a;padding:2px 6px;border-radius:3px;color:#fff;">all</code> — approve everything listed above</li>
                <li>Individual hashes separated by commas (copy from the Hash column)</li>
            </ul>
        </div>

        <p style="color:#444;font-size:11px;margin-top:24px;">
            Roles from Lever &amp; Greenhouse are auto-approved. This digest only shows roles from career pages, LinkedIn, and social sources that need your review.
        </p>
    </div>
    """
    return html, len(new_pending)


def send_email(html, count):
    """Send the digest email via Gmail SMTP."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[Email] No SMTP credentials — skipping email send")
        print("[Email] Set SMTP_EMAIL and SMTP_PASSWORD in GitHub Secrets")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Prosperity: {count} roles pending review"
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[Email] Digest sent to {NOTIFY_EMAIL} ({count} roles)")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False


if __name__ == "__main__":
    pending = load_pending()
    if not pending:
        print("[Email] No pending roles — no email needed")
        sys.exit(0)

    approved_hashes, rejected_hashes = load_approved_hashes()
    html, count = build_email_html(pending, approved_hashes, rejected_hashes)
    
    if html is None:
        print("[Email] All pending roles already reviewed — no email needed")
        sys.exit(0)

    send_email(html, count)
