/**
 * ReviewPage.jsx — Swipeable card review interface for pending roles.
 * Password protected. Approve/reject with tap. Submits via GitHub API.
 */

import { useState, useEffect, useCallback } from "react";

const MONO = "'Space Mono', monospace";
const REVIEW_PASSWORD = "prosperity"; // Change via env var later

export default function ReviewPage({ onBack }) {
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState([]);
  const [decisions, setDecisions] = useState({}); // hash -> "approved"|"rejected"
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [slideDir, setSlideDir] = useState(null); // "left"|"right" for animation

  // Load pending roles
  useEffect(() => {
    if (!authed) return;
    fetch("/data/pending_roles.json")
      .then(r => r.json())
      .then(data => {
        // Load any previously saved decisions from sessionStorage
        const saved = sessionStorage.getItem("prosperity_decisions");
        const savedDecisions = saved ? JSON.parse(saved) : {};
        
        // Filter out already-decided roles
        const roles = (data.roles || []).filter(r => !savedDecisions[r.dedup_hash]);
        setPending(roles);
        setDecisions(savedDecisions);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [authed]);

  // Save decisions to sessionStorage on change
  useEffect(() => {
    if (Object.keys(decisions).length > 0) {
      sessionStorage.setItem("prosperity_decisions", JSON.stringify(decisions));
    }
  }, [decisions]);

  const currentRole = pending[currentIndex];
  const totalReviewed = Object.keys(decisions).length;
  const approvedCount = Object.values(decisions).filter(d => d === "approved").length;
  const rejectedCount = Object.values(decisions).filter(d => d === "rejected").length;

  const decide = useCallback((decision) => {
    if (!currentRole) return;
    
    setSlideDir(decision === "approved" ? "right" : "left");
    
    setTimeout(() => {
      setDecisions(prev => ({ ...prev, [currentRole.dedup_hash]: decision }));
      setCurrentIndex(i => i + 1);
      setSlideDir(null);
    }, 200);
  }, [currentRole]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (!authed || !currentRole) return;
      if (e.key === "ArrowRight" || e.key === "a") decide("approved");
      if (e.key === "ArrowLeft" || e.key === "r") decide("rejected");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [authed, currentRole, decide]);

  const handleSubmit = async () => {
    setSubmitting(true);
    
    const approved = Object.entries(decisions)
      .filter(([_, d]) => d === "approved")
      .map(([h]) => h);
    const rejected = Object.entries(decisions)
      .filter(([_, d]) => d === "rejected")
      .map(([h]) => h);

    // Store decisions with role metadata for the learning engine
    const decisionData = {
      approved_hashes: approved,
      rejected_hashes: rejected,
      decisions: Object.entries(decisions).map(([hash, decision]) => {
        const role = pending.find(r => r.dedup_hash === hash) || {};
        return {
          hash,
          decision,
          title: role.title || "",
          fund_name: role.fund_name || "",
          source: role.source || "",
          seniority: role.seniority || "",
          decided_at: new Date().toISOString(),
        };
      }),
      submitted_at: new Date().toISOString(),
    };

    // Try to submit via API route
    try {
      const resp = await fetch("/api/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(decisionData),
      });
      
      if (resp.ok) {
        setSubmitted(true);
        sessionStorage.removeItem("prosperity_decisions");
      } else {
        // Fallback: copy to clipboard for manual GitHub Actions trigger
        const hashStr = approved.join(",");
        await navigator.clipboard.writeText(hashStr || "none");
        alert(`Copied ${approved.length} approved hashes to clipboard.\n\nGo to GitHub Actions → Approve Roles → Run workflow → Paste.`);
        setSubmitted(true);
      }
    } catch {
      // Fallback
      const hashStr = approved.join(",");
      try {
        await navigator.clipboard.writeText(hashStr || "none");
        alert(`Copied ${approved.length} approved hashes to clipboard.\n\nGo to GitHub Actions → Approve Roles → Run workflow → Paste.`);
      } catch {
        alert(`Approved hashes:\n${hashStr}\n\nCopy these and paste into GitHub Actions → Approve Roles.`);
      }
      setSubmitted(true);
    }
    
    setSubmitting(false);
  };

  // ── Password screen ──
  if (!authed) {
    return (
      <div style={containerStyle}>
        <div style={{ maxWidth: 400, width: "100%", padding: "0 20px" }}>
          <h1 style={{ fontFamily: MONO, fontSize: 20, color: "#fff", letterSpacing: "0.1em", marginBottom: 8 }}>PROSPERITY</h1>
          <p style={{ fontFamily: MONO, fontSize: 12, color: "rgba(255,255,255,0.4)", marginBottom: 30 }}>ROLE REVIEW</p>
          <input
            type="password"
            placeholder="Enter password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && password === REVIEW_PASSWORD) setAuthed(true); }}
            style={inputStyle}
          />
          <button
            onClick={() => { if (password === REVIEW_PASSWORD) setAuthed(true); }}
            style={{ ...btnBase, width: "100%", marginTop: 12, padding: "12px", color: "#fff", background: "rgba(255,255,255,0.1)", borderColor: "rgba(255,255,255,0.2)" }}
          >ENTER</button>
          <button onClick={onBack} style={{ ...btnBase, width: "100%", marginTop: 8, padding: "10px", color: "rgba(255,255,255,0.3)", borderColor: "rgba(255,255,255,0.08)" }}>← BACK TO MAP</button>
        </div>
      </div>
    );
  }

  // ── Loading ──
  if (loading) {
    return (
      <div style={containerStyle}>
        <p style={{ fontFamily: MONO, fontSize: 14, color: "rgba(255,255,255,0.5)" }}>Loading pending roles...</p>
      </div>
    );
  }

  // ── Submitted ──
  if (submitted) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✓</div>
          <h2 style={{ fontFamily: MONO, fontSize: 18, color: "#fff", marginBottom: 8 }}>DECISIONS SUBMITTED</h2>
          <p style={{ fontFamily: MONO, fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>
            {approvedCount} approved · {rejectedCount} rejected
          </p>
          <p style={{ fontFamily: MONO, fontSize: 11, color: "rgba(255,255,255,0.3)", marginBottom: 30 }}>
            Approved roles will appear on the site after the next scrape run.
          </p>
          <button onClick={onBack} style={{ ...btnBase, padding: "12px 32px", color: "#fff", borderColor: "rgba(255,255,255,0.2)" }}>← BACK TO MAP</button>
        </div>
      </div>
    );
  }

  // ── All reviewed ──
  if (currentIndex >= pending.length) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: "center", maxWidth: 400, padding: "0 20px" }}>
          <h2 style={{ fontFamily: MONO, fontSize: 18, color: "#fff", marginBottom: 12 }}>REVIEW COMPLETE</h2>
          <p style={{ fontFamily: MONO, fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 20 }}>
            {approvedCount} approved · {rejectedCount} rejected
          </p>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{ ...btnBase, width: "100%", padding: "14px", color: "#000", background: "#fff", borderColor: "#fff", fontWeight: 700 }}
          >{submitting ? "SUBMITTING..." : "SUBMIT DECISIONS"}</button>
          <button onClick={onBack} style={{ ...btnBase, width: "100%", marginTop: 8, padding: "10px", color: "rgba(255,255,255,0.3)", borderColor: "rgba(255,255,255,0.08)" }}>← BACK TO MAP</button>
        </div>
      </div>
    );
  }

  // ── Review card ──
  const role = currentRole;
  const progress = ((currentIndex) / pending.length) * 100;

  return (
    <div style={containerStyle}>
      {/* Progress bar */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "rgba(255,255,255,0.05)" }}>
        <div style={{ height: "100%", width: `${progress}%`, background: "rgba(255,255,255,0.3)", transition: "width 0.2s" }} />
      </div>

      {/* Header */}
      <div style={{ position: "absolute", top: 16, left: 20, right: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button onClick={onBack} style={{ ...btnBase, padding: "6px 12px", fontSize: 12, color: "rgba(255,255,255,0.4)", borderColor: "rgba(255,255,255,0.1)" }}>← EXIT</button>
        <span style={{ fontFamily: MONO, fontSize: 11, color: "rgba(255,255,255,0.3)" }}>
          {currentIndex + 1} / {pending.length} · {approvedCount}✓ {rejectedCount}✗
        </span>
      </div>

      {/* Card */}
      <div style={{
        maxWidth: 500, width: "calc(100% - 40px)", padding: 24,
        background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: 12,
        transform: slideDir === "right" ? "translateX(120%) rotate(5deg)" :
                   slideDir === "left" ? "translateX(-120%) rotate(-5deg)" : "none",
        opacity: slideDir ? 0.5 : 1,
        transition: slideDir ? "all 0.2s ease-out" : "none",
      }}>
        {/* Fund name */}
        <div style={{ fontFamily: MONO, fontSize: 11, color: "rgba(255,255,255,0.4)", letterSpacing: "0.08em", marginBottom: 6 }}>
          {role.fund_name}
        </div>

        {/* Role title */}
        <div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 12, lineHeight: 1.3 }}>
          {role.title}
        </div>

        {/* Meta row */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          {role.seniority && <span style={tagStyle}>{role.seniority}</span>}
          <span style={tagStyle}>{role.source}</span>
          {role.freshness && <span style={tagStyle}>{role.freshness}</span>}
        </div>

        {/* Description */}
        {role.description && (
          <div style={{ fontFamily: MONO, fontSize: 12, color: "rgba(255,255,255,0.4)", lineHeight: 1.6, marginBottom: 16, maxHeight: 120, overflow: "hidden" }}>
            {role.description}
          </div>
        )}

        {/* Source link */}
        {role.source_url && (
          <a href={role.source_url} target="_blank" rel="noopener noreferrer"
            style={{ fontFamily: MONO, fontSize: 11, color: "rgba(255,255,255,0.5)", textDecoration: "underline" }}>
            View Source ↗
          </a>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 20, marginTop: 24 }}>
        <button onClick={() => decide("rejected")} style={{
          ...btnBase, width: 64, height: 64, borderRadius: "50%",
          fontSize: 24, color: "#ff4444", borderColor: "rgba(255,68,68,0.3)",
          background: "rgba(255,68,68,0.05)",
        }}>✗</button>

        <button onClick={() => decide("approved")} style={{
          ...btnBase, width: 64, height: 64, borderRadius: "50%",
          fontSize: 24, color: "#44ff44", borderColor: "rgba(68,255,68,0.3)",
          background: "rgba(68,255,68,0.05)",
        }}>✓</button>
      </div>

      {/* Hint */}
      <p style={{ fontFamily: MONO, fontSize: 10, color: "rgba(255,255,255,0.2)", marginTop: 16 }}>
        ← REJECT · APPROVE → (or use arrow keys)
      </p>
    </div>
  );
}

const containerStyle = {
  width: "100%", height: "100dvh", display: "flex", flexDirection: "column",
  alignItems: "center", justifyContent: "center", position: "relative",
  background: "#0a0a0a",
};

const inputStyle = {
  width: "100%", padding: "12px 16px", background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6,
  color: "#fff", fontFamily: MONO, fontSize: 14,
  outline: "none", letterSpacing: "0.04em",
};

const btnBase = {
  background: "transparent", border: "1px solid rgba(255,255,255,0.15)",
  borderRadius: 6, cursor: "pointer", fontFamily: MONO, fontSize: 13,
  letterSpacing: "0.06em", display: "flex", alignItems: "center", justifyContent: "center",
};

const tagStyle = {
  fontFamily: MONO, fontSize: 10, padding: "3px 8px", borderRadius: 4,
  background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.5)",
  border: "1px solid rgba(255,255,255,0.08)", letterSpacing: "0.04em",
};
