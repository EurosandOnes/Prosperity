/**
 * FundSheet.jsx — Bottom sheet showing fund details and roles.
 */

import { FOCUS_COLORS, FRESHNESS, FONTS, getFundLogoUrl } from "../config/theme";
import { useState } from "react";

export default function FundSheet({ fund, onClose }) {
  const [imgError, setImgError] = useState(false);
  const color = FOCUS_COLORS[fund.focus] || "#666";
  const logoUrl = getFundLogoUrl(fund.website);
  const hasLogo = logoUrl && !imgError;

  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0, zIndex: 30,
      maxHeight: "55vh", overflowY: "auto",
      background: "rgba(6,6,8,0.97)",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      backdropFilter: "blur(24px)",
      animation: "slideUp .35s cubic-bezier(.22,1,.36,1)",
      padding: "24px 28px 32px",
    }}>
      <button onClick={onClose} style={{
        position: "absolute", top: 16, right: 20,
        background: "none", border: "none", cursor: "pointer",
        fontSize: 18, color: "#555", fontFamily: FONTS.mono, padding: "4px 8px",
      }}
      onMouseEnter={e => e.target.style.color = "#fff"}
      onMouseLeave={e => e.target.style.color = "#555"}>✕</button>

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
        <div style={{
          width: 48, height: 48, borderRadius: "50%",
          border: `2px solid ${color}`, background: "rgba(0,0,0,0.6)",
          display: "flex", alignItems: "center", justifyContent: "center",
          overflow: "hidden", flexShrink: 0,
        }}>
          {hasLogo ? (
            <img src={logoUrl} alt={fund.name} onError={() => setImgError(true)}
              style={{ width: 38, height: 38, objectFit: "contain", borderRadius: "50%" }} />
          ) : (
            <span style={{ fontSize: 15, fontWeight: 700, color, fontFamily: FONTS.mono }}>{fund.initials}</span>
          )}
        </div>
        <div>
          <h2 style={{
            margin: 0, fontSize: 22, fontWeight: 700, color: "#fff",
            fontFamily: FONTS.heading, letterSpacing: "0.02em",
          }}>{fund.name}</h2>
          <div style={{
            display: "flex", gap: 12, marginTop: 4,
            fontSize: 12, color: "#666", fontFamily: FONTS.mono, letterSpacing: "0.04em",
          }}>
            <span style={{ color }}>{fund.focus}</span>
            <span>·</span>
            <span>{fund.neighborhood}</span>
          </div>
        </div>
      </div>

      <div style={{
        display: "flex", gap: 28, marginBottom: 20, padding: "14px 18px",
        background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
      }}>
        {fund.aum && (
          <div>
            <div style={{ fontSize: 9, color: "#555", fontFamily: FONTS.mono, letterSpacing: "0.1em", fontWeight: 700 }}>AUM</div>
            <div style={{ fontSize: 16, color: "#ccc", fontFamily: FONTS.mono, fontWeight: 700, marginTop: 3 }}>{fund.aum}</div>
          </div>
        )}
        {fund.founded && (
          <div>
            <div style={{ fontSize: 9, color: "#555", fontFamily: FONTS.mono, letterSpacing: "0.1em", fontWeight: 700 }}>FOUNDED</div>
            <div style={{ fontSize: 16, color: "#ccc", fontFamily: FONTS.mono, fontWeight: 700, marginTop: 3 }}>{fund.founded}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 9, color: "#555", fontFamily: FONTS.mono, letterSpacing: "0.1em", fontWeight: 700 }}>ROLES</div>
          <div style={{
            fontSize: 16, fontFamily: FONTS.mono, fontWeight: 700, marginTop: 3,
            color: fund.roles?.length ? "#fff" : "#444",
          }}>{fund.roles?.length || 0}</div>
        </div>
      </div>

      {fund.roles?.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {fund.roles.map((r, i) => {
            const isHot = r.freshness === "HOT";
            return (
              <div key={i} style={{
                padding: "16px 18px",
                background: isHot ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.015)",
                border: `1px solid ${isHot ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.06)"}`,
                boxShadow: isHot ? "0 0 12px rgba(255,255,255,0.05)" : "none",
                cursor: r.url && r.url !== "#" ? "pointer" : "default",
                transition: "all 0.2s",
                ...(isHot ? { animation: "roleEbb 2.5s ease-in-out infinite" } : {}),
              }}
              onClick={() => r.url && r.url !== "#" && window.open(r.url, "_blank")}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#eee", fontFamily: FONTS.body }}>{r.title}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: isHot ? "#fff" : "#aaa",
                    fontFamily: FONTS.mono, letterSpacing: "0.08em",
                    padding: "3px 10px",
                    background: isHot ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.03)",
                    border: `1px solid ${isHot ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)"}`,
                  }}>{r.freshness}</span>
                </div>
                {r.description && (
                  <p style={{ margin: "6px 0 0", fontSize: 12, color: "#888", lineHeight: 1.5, fontFamily: FONTS.body }}>{r.description}</p>
                )}
                <div style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 10, color: "#555", fontFamily: FONTS.mono, letterSpacing: "0.04em" }}>
                  {r.posted && <span>{r.posted}</span>}
                  {r.source && <span>via {r.source}</span>}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ padding: "24px", textAlign: "center", fontSize: 13, color: "#444", fontFamily: FONTS.mono, letterSpacing: "0.06em" }}>
          NO OPEN ROLES DETECTED
        </div>
      )}
    </div>
  );
}
