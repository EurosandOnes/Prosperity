/**
 * WorldView.jsx — Globe screen with stats readout and CTA.
 * Dark theme only.
 */

import Globe from "./Globe";
import { FONTS } from "../config/theme";

export default function WorldView({ stats, onEnter, exiting }) {
  return (
    <div style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", position: "relative",
      animation: exiting ? "fadeOut .5s ease-in forwards" : "fadeIn .6s ease-out",
      overflow: "hidden",
    }}>
      {/* Corner readouts */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0,
        padding: "max(env(safe-area-inset-top,20px),20px) 24px 0",
        display: "flex", justifyContent: "space-between", zIndex: 5,
      }}>
        <div style={{
          fontSize: 11, letterSpacing: "0.14em", fontFamily: FONTS.mono,
          fontWeight: 700, color: "#444",
        }}>VENTURE CAPITAL · LIVE HIRING</div>
        <div style={{
          fontSize: 10, letterSpacing: "0.08em", textAlign: "right",
          lineHeight: 2, fontFamily: FONTS.mono, color: "#333",
        }}>
          <div>SYS:ONLINE</div><div>NODES:{stats.totalFunds}</div>
        </div>
      </div>

      {/* Globe */}
      <div style={{ width: "min(85vw, 80vh)", maxWidth: 650, aspectRatio: "1/1", marginTop: -30 }}>
        <Globe onEnterCity={onEnter} />
      </div>

      {/* Stats */}
      <div style={{
        display: "flex", gap: 32, marginTop: 24, fontSize: 15,
        letterSpacing: "0.04em", fontWeight: 700, fontFamily: FONTS.mono, color: "#bbb",
      }}>
        <span><span style={{ marginRight: 6, color: "#fff" }}>●</span>{stats.fundsHiring} funds hiring</span>
        <span><span style={{ marginRight: 6, color: "#666" }}>●</span>{stats.hotRoles} roles &lt; 1wk</span>
      </div>

      {/* CTA */}
      <button onClick={() => onEnter("london")} style={{
        marginTop: 28, padding: "16px 44px", background: "transparent",
        border: "1px solid rgba(255,255,255,0.15)",
        borderRadius: 0, cursor: "pointer",
        fontFamily: FONTS.mono, fontSize: 14, fontWeight: 700,
        color: "#bbb", letterSpacing: "0.16em",
        transition: "all 0.2s",
      }}
      onMouseEnter={e => {
        e.target.style.background = "rgba(255,255,255,0.06)";
        e.target.style.borderColor = "rgba(255,255,255,0.35)";
        e.target.style.color = "#fff";
      }}
      onMouseLeave={e => {
        e.target.style.background = "transparent";
        e.target.style.borderColor = "rgba(255,255,255,0.15)";
        e.target.style.color = "#bbb";
      }}>
        [ ENTER LONDON ]
      </button>

      <p style={{
        marginTop: 14, fontSize: 11, letterSpacing: "0.1em",
        fontFamily: FONTS.mono, color: "#444",
      }}>DRAG TO ROTATE · TAP LONDON</p>

      <p style={{
        position: "absolute", bottom: "max(env(safe-area-inset-bottom,24px),24px)",
        fontSize: 10, letterSpacing: "0.14em", fontFamily: FONTS.mono, color: "#222",
      }}>ADDITIONAL NODES PENDING</p>
    </div>
  );
}
