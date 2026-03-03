/**
 * CityMap.jsx — London city view with fund markers over a dark map.
 * Positions are computed from lat/lng via Mercator projection matching the tile grid.
 * Includes collision avoidance for overlapping clusters (e.g., Soho).
 */

import { useState, useEffect, useCallback } from "react";
import { FOCUS_COLORS, FONTS } from "../config/theme";
import FundNode from "./FundNode";
import FundSheet from "./FundSheet";

/* ── Tile grid constants ── */
const TILE_Z = 12;
const TILE_SIZE = 256;
const GRID_COLS = 7;
const GRID_ROWS = 5;
const TILE_START_X = 2043;
const TILE_START_Y = 1360;
const TOTAL_W = GRID_COLS * TILE_SIZE; // 1792
const TOTAL_H = GRID_ROWS * TILE_SIZE; // 1280
const N = Math.pow(2, TILE_Z); // 4096

// Geographic bounds of the tile grid
const WEST_LNG = (TILE_START_X / N) * 360 - 180;
const EAST_LNG = ((TILE_START_X + GRID_COLS) / N) * 360 - 180;
const mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const tileToLat = (ty) => Math.atan(Math.sinh(Math.PI * (1 - (2 * ty) / N))) * (180 / Math.PI);
const NORTH_LAT = tileToLat(TILE_START_Y);
const SOUTH_LAT = tileToLat(TILE_START_Y + GRID_ROWS);
const MERC_NORTH = mercY(NORTH_LAT);
const MERC_SOUTH = mercY(SOUTH_LAT);

/* ── Geo → viewport % conversion ── */
function useGeoProjection() {
  const [dims, setDims] = useState({ w: window.innerWidth, h: window.innerHeight });

  useEffect(() => {
    const onResize = () => setDims({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const project = useCallback((lat, lng) => {
    // Position within tile grid (0..1)
    const gx = (lng - WEST_LNG) / (EAST_LNG - WEST_LNG);
    const gy = (MERC_NORTH - mercY(lat)) / (MERC_NORTH - MERC_SOUTH);

    // Pixel in unscaled tile grid
    const px = gx * TOTAL_W;
    const py = gy * TOTAL_H;

    // Scale factor (same as MapBackground)
    const scale = Math.max(dims.w / TOTAL_W, dims.h / TOTAL_H) * 1.2;

    // Viewport position (tile grid is centered via translate(-50%,-50%) at 50%,50%)
    const vpx = dims.w / 2 + (px - TOTAL_W / 2) * scale;
    const vpy = dims.h / 2 + (py - TOTAL_H / 2) * scale;

    return { x: (vpx / dims.w) * 100, y: (vpy / dims.h) * 100 };
  }, [dims]);

  return project;
}

/* ── Collision avoidance ── */
function deconflict(funds, project, minDist = 5) {
  const positioned = funds.map(f => {
    const { x, y } = project(f.lat, f.lng);
    return { ...f, x, y };
  });

  // Simple repulsion pass — push overlapping nodes apart
  for (let pass = 0; pass < 4; pass++) {
    for (let i = 0; i < positioned.length; i++) {
      for (let j = i + 1; j < positioned.length; j++) {
        const dx = positioned[j].x - positioned[i].x;
        const dy = positioned[j].y - positioned[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < minDist && dist > 0) {
          const push = (minDist - dist) / 2;
          const angle = Math.atan2(dy, dx);
          positioned[j].x += Math.cos(angle) * push;
          positioned[j].y += Math.sin(angle) * push;
          positioned[i].x -= Math.cos(angle) * push;
          positioned[i].y -= Math.sin(angle) * push;
        } else if (dist === 0) {
          // Identical positions — nudge randomly
          positioned[j].x += (Math.random() - 0.5) * minDist;
          positioned[j].y += (Math.random() - 0.5) * minDist;
        }
      }
    }
  }

  return positioned;
}

/* ── Map Background ── */
function MapBackground() {
  const [scale, setScale] = useState(1);

  const tiles = [];
  for (let row = 0; row < GRID_ROWS; row++) {
    for (let col = 0; col < GRID_COLS; col++) {
      tiles.push({
        tx: TILE_START_X + col, ty: TILE_START_Y + row,
        col, row, key: `${TILE_START_X + col}-${TILE_START_Y + row}`,
      });
    }
  }

  useEffect(() => {
    const update = () => setScale(Math.max(window.innerWidth / TOTAL_W, window.innerHeight / TOTAL_H) * 1.2);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 0, overflow: "hidden" }}>
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        width: TOTAL_W, height: TOTAL_H,
        transform: `translate(-50%, -50%) scale(${scale})`,
        transformOrigin: "center center",
        opacity: 0.85,
        filter: "brightness(1.3) contrast(1.1) saturate(0.15)",
      }}>
        {tiles.map(t => (
          <img key={t.key} alt="" loading="eager" draggable={false}
            src={`https://basemaps.cartocdn.com/dark_nolabels/${TILE_Z}/${t.tx}/${t.ty}.png`}
            style={{
              position: "absolute",
              left: t.col * TILE_SIZE, top: t.row * TILE_SIZE,
              width: TILE_SIZE, height: TILE_SIZE, display: "block",
            }}
          />
        ))}
      </div>
      <div style={{
        position: "absolute", inset: 0,
        background: "radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.45) 100%)",
        pointerEvents: "none",
      }} />
    </div>
  );
}

/* ── Focus Dropdown ── */
function FocusDropdown({ value, onChange, options }) {
  const [open, setOpen] = useState(false);
  const label = value || "All focuses";
  const color = value ? FOCUS_COLORS[value] || "#fff" : "#888";

  return (
    <div style={{ position: "relative", zIndex: 25 }}>
      <button onClick={() => setOpen(!open)} style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "9px 16px", minWidth: 180,
        background: "rgba(0,0,0,0.6)", backdropFilter: "blur(12px)",
        border: `1px solid ${value ? color + "40" : "rgba(255,255,255,0.1)"}`,
        borderRadius: 0, cursor: "pointer",
        fontFamily: FONTS.mono, fontSize: 12, fontWeight: 600,
        color: value ? color : "#999", letterSpacing: "0.04em",
        transition: "all 0.2s",
      }}>
        {value && <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, flexShrink: 0 }} />}
        <span style={{ flex: 1, textAlign: "left" }}>{label}</span>
        <span style={{
          fontSize: 8, color: "#555", marginLeft: 4,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform 0.2s",
        }}>▼</span>
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0,
          background: "rgba(6,6,8,0.95)", backdropFilter: "blur(16px)",
          border: "1px solid rgba(255,255,255,0.08)",
          maxHeight: 280, overflowY: "auto",
          animation: "fadeIn 0.15s ease-out",
        }}>
          <div onClick={() => { onChange(null); setOpen(false); }} style={{
            padding: "10px 16px", cursor: "pointer",
            fontFamily: FONTS.mono, fontSize: 12,
            color: !value ? "#fff" : "#666",
            background: !value ? "rgba(255,255,255,0.04)" : "transparent",
            letterSpacing: "0.04em", transition: "background 0.15s",
          }}
          onMouseEnter={e => e.target.style.background = "rgba(255,255,255,0.06)"}
          onMouseLeave={e => e.target.style.background = !value ? "rgba(255,255,255,0.04)" : "transparent"}>
            All focuses
          </div>
          {options.map(f => {
            const fc = FOCUS_COLORS[f] || "#666";
            const active = value === f;
            return (
              <div key={f}
                onClick={() => { onChange(active ? null : f); setOpen(false); }}
                style={{
                  padding: "10px 16px", cursor: "pointer",
                  display: "flex", alignItems: "center", gap: 10,
                  fontFamily: FONTS.mono, fontSize: 12,
                  color: active ? fc : "#888",
                  background: active ? `${fc}10` : "transparent",
                  letterSpacing: "0.04em",
                  transition: "background 0.15s, color 0.15s",
                }}
                onMouseEnter={e => { e.currentTarget.style.background = `${fc}15`; e.currentTarget.style.color = fc; }}
                onMouseLeave={e => { e.currentTarget.style.background = active ? `${fc}10` : "transparent"; e.currentTarget.style.color = active ? fc : "#888"; }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: fc, flexShrink: 0 }} />
                {f}
              </div>
            );
          })}
        </div>
      )}
      {open && <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: -1 }} />}
    </div>
  );
}

/* ── Main ── */
export default function CityMap({ funds, onBack }) {
  const [filter, setFilter] = useState(null);
  const [showHiring, setShowHiring] = useState(false);
  const [selected, setSelected] = useState(null);
  const [sheetFund, setSheetFund] = useState(null);

  const project = useGeoProjection();

  const visible = funds.filter(f => {
    if (showHiring && (!f.hiring || !f.roles?.length)) return false;
    if (filter && f.focus !== filter) return false;
    return true;
  });

  // Compute positions with collision avoidance
  const positioned = deconflict(visible, project, 5.5);

  const focusAreas = [...new Set(funds.map(f => f.focus))].sort();
  const hiringCount = funds.filter(f => f.hiring && f.roles?.length).length;

  return (
    <div style={{
      width: "100%", height: "100%", position: "relative", overflow: "hidden",
      animation: "fadeIn .5s ease-out", background: "#000",
    }}>
      <MapBackground />

      {/* Header */}
      <div style={{
        position: "relative", zIndex: 10, padding: "20px 24px 0",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button onClick={onBack} style={{
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 0, padding: "8px 14px", cursor: "pointer",
            fontFamily: FONTS.mono, fontSize: 16, color: "#888", fontWeight: 700,
            transition: "all 0.2s",
          }}
          onMouseEnter={e => { e.target.style.color = "#fff"; e.target.style.borderColor = "rgba(255,255,255,0.3)"; }}
          onMouseLeave={e => { e.target.style.color = "#888"; e.target.style.borderColor = "rgba(255,255,255,0.12)"; }}>
            ←
          </button>
          <h1 style={{
            margin: 0, fontSize: 28, fontWeight: 800, color: "#fff",
            fontFamily: FONTS.heading, letterSpacing: "0.04em", lineHeight: 1,
          }}>
            LONDON
            <span style={{ fontSize: 13, color: "#666", fontWeight: 400, fontFamily: FONTS.mono, marginLeft: 12 }}>
              {hiringCount} HIRING
            </span>
          </h1>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <FocusDropdown value={filter} onChange={setFilter} options={focusAreas} />
          <button onClick={() => setShowHiring(!showHiring)} style={{
            padding: "9px 18px",
            background: showHiring ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.6)",
            backdropFilter: "blur(12px)",
            border: `1px solid ${showHiring ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.1)"}`,
            borderRadius: 0, cursor: "pointer",
            fontFamily: FONTS.mono, fontSize: 12, fontWeight: 700,
            color: showHiring ? "#fff" : "#999",
            letterSpacing: "0.06em", transition: "all 0.2s",
          }}>
            {showHiring ? "● LIVE ONLY" : "LIVE ONLY"}
          </button>
        </div>
      </div>

      {/* Signal legend */}
      <div style={{
        position: "relative", zIndex: 10, padding: "12px 24px 0",
        display: "flex", gap: 24, alignItems: "center",
      }}>
        <span style={{ fontSize: 10, color: "#555", fontFamily: FONTS.mono, letterSpacing: "0.08em", fontWeight: 700 }}>SIGNAL</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            display: "inline-block", width: 12, height: 12, borderRadius: "50%",
            background: "rgba(0,0,0,0.6)", border: "2px solid rgba(255,255,255,0.55)",
            boxShadow: "0 0 10px rgba(255,255,255,0.25), 0 0 20px rgba(255,255,255,0.1)",
            animation: "ebbHot 2.2s ease-in-out infinite",
          }} />
          <span style={{ fontSize: 11, color: "#bbb", fontFamily: FONTS.mono }}>Hot</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            display: "inline-block", width: 12, height: 12, borderRadius: "50%",
            background: "rgba(0,0,0,0.6)", border: "2px solid rgba(255,255,255,0.3)",
            boxShadow: "0 0 6px rgba(255,255,255,0.08)",
            animation: "ebbWarm 3s ease-in-out infinite",
          }} />
          <span style={{ fontSize: 11, color: "#999", fontFamily: FONTS.mono }}>Warm</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            display: "inline-block", width: 12, height: 12, borderRadius: "50%",
            background: "rgba(0,0,0,0.6)", border: "2px solid rgba(255,255,255,0.12)",
          }} />
          <span style={{ fontSize: 11, color: "#666", fontFamily: FONTS.mono }}>Quiet</span>
        </span>
      </div>

      {/* Fund nodes */}
      <div style={{ position: "absolute", inset: 0, zIndex: 5, pointerEvents: "none" }}>
        <div style={{ position: "relative", width: "100%", height: "100%", pointerEvents: "auto" }}>
          {positioned.map(f => (
            <FundNode key={f.id} fund={f} selected={selected === f.id}
              onClick={() => {
                setSelected(selected === f.id ? null : f.id);
                setSheetFund(selected === f.id ? null : f);
              }}
            />
          ))}
        </div>
      </div>

      {sheetFund && (
        <FundSheet fund={sheetFund} onClose={() => { setSheetFund(null); setSelected(null); }} />
      )}

      <div style={{
        position: "absolute", bottom: 20, left: 24, zIndex: 10,
        fontSize: 10, color: "#444", fontFamily: FONTS.mono,
        letterSpacing: "0.1em", lineHeight: 1.8,
      }}>
        <div>51.5074°N, 0.1278°W</div>
        <div>{positioned.length} FUNDS VISIBLE</div>
      </div>
    </div>
  );
}
