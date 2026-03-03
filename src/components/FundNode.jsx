/**
 * FundNode.jsx — Single fund marker on the London map.
 * Receives pre-computed x,y (viewport %) from CityMap's geo projection.
 */

import { useState } from "react";
import { FOCUS_COLORS, FONTS, getFundLogoUrl } from "../config/theme";

export default function FundNode({ fund, selected, onClick }) {
  const [imgError, setImgError] = useState(false);
  const [hover, setHover] = useState(false);

  const color = FOCUS_COLORS[fund.focus] || "#666";
  const logoUrl = getFundLogoUrl(fund.website);
  const hasLogo = logoUrl && !imgError;

  const isHiring = fund.hiring && fund.roles?.length > 0;
  const hasHot = fund.roles?.some(r => r.freshness === "HOT");
  const hasWarm = fund.roles?.some(r => r.freshness === "WARM");

  // Size & styling
  const size = selected ? 60 : hover ? 56 : 50;
  const active = selected || hover;

  // Hiring signal ring
  let ringStyle = {};
  if (hasHot) {
    ringStyle = {
      boxShadow: `0 0 14px rgba(255,255,255,0.3), 0 0 28px rgba(255,255,255,0.1)`,
      border: `2.5px solid rgba(255,255,255,0.55)`,
      animation: "ebbHot 2.2s ease-in-out infinite",
    };
  } else if (hasWarm) {
    ringStyle = {
      boxShadow: `0 0 8px rgba(255,255,255,0.12)`,
      border: `2px solid rgba(255,255,255,0.3)`,
      animation: "ebbWarm 3s ease-in-out infinite",
    };
  } else {
    ringStyle = {
      border: `2px solid rgba(255,255,255,${isHiring ? 0.15 : 0.08})`,
    };
  }

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: "absolute",
        left: `${fund.x}%`,
        top: `${fund.y}%`,
        transform: "translate(-50%, -50%)",
        zIndex: active ? 20 : 10,
        cursor: "pointer",
        transition: "transform 0.2s ease, z-index 0s",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
        filter: !isHiring ? "brightness(0.6)" : "none",
      }}
    >
      {/* Logo circle */}
      <div style={{
        width: size, height: size, borderRadius: "50%",
        background: "rgba(0,0,0,0.7)",
        display: "flex", alignItems: "center", justifyContent: "center",
        overflow: "hidden",
        transition: "all 0.2s ease",
        ...ringStyle,
        ...(active ? {
          boxShadow: `0 0 20px rgba(255,255,255,0.3), 0 0 40px rgba(255,255,255,0.1)`,
          border: `2.5px solid rgba(255,255,255,0.6)`,
        } : {}),
      }}>
        {hasLogo ? (
          <img src={logoUrl} alt={fund.name} onError={() => setImgError(true)}
            style={{
              width: size - 12, height: size - 12,
              objectFit: "contain", borderRadius: "50%",
            }}
          />
        ) : (
          <span style={{
            fontSize: size * 0.3, fontWeight: 700, color,
            fontFamily: FONTS.mono, letterSpacing: "0.02em",
          }}>{fund.initials}</span>
        )}
      </div>

      {/* Label */}
      <div style={{
        textAlign: "center", whiteSpace: "nowrap",
        textShadow: "0 1px 6px rgba(0,0,0,0.9), 0 0 12px rgba(0,0,0,0.7)",
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: active ? "#fff" : "#ddd",
          fontFamily: FONTS.mono, letterSpacing: "0.03em",
          transition: "color 0.2s",
        }}>{fund.name}</div>
        <div style={{
          fontSize: 10, color: active ? "#aaa" : "#666",
          fontFamily: FONTS.mono, fontStyle: "italic",
          letterSpacing: "0.02em", marginTop: 1,
          transition: "color 0.2s",
        }}>{fund.neighborhood}</div>
      </div>
    </div>
  );
}
