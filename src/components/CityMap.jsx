/**
 * CityMap.jsx — Interactive London map using Leaflet.
 * Full pinch/zoom/drag, crisp tiles at every level, marker clustering.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { FONTS } from "../config/theme";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";

/* ── Constants ── */
const LONDON_CENTER = [51.518, -0.130];
const DEFAULT_ZOOM = 13;
const MIN_ZOOM = 11;
const MAX_ZOOM = 18;

/* ── Helpers ── */
function getFaviconUrl(fund) {
  if (!fund.website) return null;
  try {
    const host = new URL(fund.website).hostname;
    return `https://www.google.com/s2/favicons?domain=${host}&sz=64`;
  } catch { return null; }
}

function getBestFreshness(fund) {
  if (!fund.hiring || !fund.roles?.length) return "QUIET";
  if (fund.roles.some(r => r.freshness === "HOT")) return "HOT";
  if (fund.roles.some(r => r.freshness === "WARM")) return "WARM";
  return "QUIET";
}

function getUniqueFocuses(funds) {
  const s = new Set(funds.map(f => f.focus));
  return ["All", ...Array.from(s).sort()];
}

/* ── Custom marker HTML ── */
function createFundIcon(fund) {
  const freshness = getBestFreshness(fund);
  const logo = getFaviconUrl(fund);
  const sz = 38;

  const borderColor =
    freshness === "HOT" ? "rgba(255,255,255,0.7)" :
    freshness === "WARM" ? "rgba(255,255,255,0.35)" :
    "rgba(255,255,255,0.12)";

  const animation =
    freshness === "HOT" ? "ebbHot 3s ease-in-out infinite" :
    freshness === "WARM" ? "ebbWarm 4s ease-in-out infinite" :
    "none";

  const nameOpacity = freshness === "QUIET" ? "0.4" : "0.9";

  const imgHtml = logo
    ? `<img src="${logo}" style="width:${sz-6}px;height:${sz-6}px;border-radius:50%;object-fit:cover;" onerror="this.style.display='none';this.nextSibling.style.display='block'"/><span style="display:none;font-size:11px;font-weight:700;color:#fff;letter-spacing:0.04em">${fund.initials}</span>`
    : `<span style="font-size:11px;font-weight:700;color:#fff;letter-spacing:0.04em">${fund.initials}</span>`;

  const html = `
    <div style="display:flex;flex-direction:column;align-items:center;cursor:pointer;">
      <div style="
        width:${sz}px;height:${sz}px;border-radius:50%;
        border:2px solid ${borderColor};
        background:rgba(15,15,18,0.92);
        display:flex;align-items:center;justify-content:center;
        overflow:hidden;animation:${animation};
      ">${imgHtml}</div>
      <div style="
        margin-top:3px;font-family:'Space Mono',monospace;font-size:10px;font-weight:600;
        color:rgba(255,255,255,${nameOpacity});letter-spacing:0.03em;white-space:nowrap;
        text-shadow:0 1px 4px rgba(0,0,0,0.9),0 0 8px rgba(0,0,0,0.7);
        max-width:110px;overflow:hidden;text-overflow:ellipsis;text-align:center;
      ">${fund.name}</div>
    </div>`;

  return L.divIcon({
    html,
    className: "fund-marker",
    iconSize: [110, 60],
    iconAnchor: [55, 25],
  });
}

export default function CityMap({ funds, onBack }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const clusterRef = useRef(null);
  const markersRef = useRef({});

  const [selected, setSelected] = useState(null);
  const [focusFilter, setFocusFilter] = useState("All");
  const [hiringOnly, setHiringOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const focuses = getUniqueFocuses(funds);

  /* ── Filter funds ── */
  const filtered = funds.filter(f => {
    if (focusFilter !== "All" && f.focus !== focusFilter) return false;
    if (hiringOnly && !f.hiring) return false;
    return true;
  });

  /* ── Initialize Leaflet map ── */
  useEffect(() => {
    if (leafletRef.current) return; // Already initialized

    const map = L.map(mapRef.current, {
      center: LONDON_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
      zoomControl: false,
      attributionControl: false,
    });

    // Dark tile layer — crisp at all zoom levels
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: MAX_ZOOM,
      subdomains: "abcd",
    }).addTo(map);

    // Create marker cluster group
    const cluster = L.markerClusterGroup({
      maxClusterRadius: 45,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      disableClusteringAtZoom: 16,
      iconCreateFunction: (clstr) => {
        const count = clstr.getChildCount();
        const childMarkers = clstr.getAllChildMarkers();
        const hasHot = childMarkers.some(m => m.options.freshness === "HOT");
        const hasWarm = childMarkers.some(m => m.options.freshness === "WARM");

        const borderColor = hasHot
          ? "rgba(255,255,255,0.6)"
          : hasWarm ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.15)";
        const glow = hasHot
          ? "box-shadow:0 0 14px rgba(255,255,255,0.25),0 0 30px rgba(255,255,255,0.1);"
          : hasWarm ? "box-shadow:0 0 8px rgba(255,255,255,0.1);" : "";
        const animation = hasHot ? "animation:ebbHot 3s ease-in-out infinite;" : "";

        return L.divIcon({
          html: `<div style="
            width:48px;height:48px;border-radius:50%;
            border:2px solid ${borderColor};
            background:rgba(15,15,18,0.92);
            display:flex;align-items:center;justify-content:center;
            font-family:'Space Mono',monospace;font-size:14px;font-weight:700;
            color:rgba(255,255,255,0.85);cursor:pointer;
            ${glow}${animation}
          ">${count}</div>`,
          className: "fund-cluster",
          iconSize: [48, 48],
          iconAnchor: [24, 24],
        });
      },
    });

    map.addLayer(cluster);
    leafletRef.current = map;
    clusterRef.current = cluster;

    return () => {
      map.remove();
      leafletRef.current = null;
      clusterRef.current = null;
    };
  }, []);

  /* ── Update markers when filters change ── */
  useEffect(() => {
    const cluster = clusterRef.current;
    if (!cluster) return;

    // Clear existing markers
    cluster.clearLayers();
    markersRef.current = {};

    // Add filtered fund markers
    filtered.forEach(fund => {
      if (!fund.lat || !fund.lng) return;

      const marker = L.marker([fund.lat, fund.lng], {
        icon: createFundIcon(fund),
        freshness: getBestFreshness(fund),
      });

      marker.on("click", () => {
        setSelected(prev => prev === fund.id ? null : fund.id);
      });

      cluster.addLayer(marker);
      markersRef.current[fund.id] = marker;
    });
  }, [filtered]);

  /* ── Zoom to fund when selected ── */
  useEffect(() => {
    if (!selected || !leafletRef.current) return;
    const marker = markersRef.current[selected];
    if (marker) {
      leafletRef.current.setView(marker.getLatLng(), 15, { animate: true });
    }
  }, [selected]);

  const selectedFund = selected ? funds.find(f => f.id === selected) : null;
  const resetView = () => {
    if (leafletRef.current) {
      leafletRef.current.setView(LONDON_CENTER, DEFAULT_ZOOM, { animate: true });
    }
    setSelected(null);
  };

  return (
    <div style={{
      width: "100%", height: "100%", position: "relative",
      background: "#0a0a0a", animation: "fadeIn 0.5s ease-out",
    }}>
      {/* Map container */}
      <div ref={mapRef} style={{ width: "100%", height: "100%", zIndex: 1 }} />

      {/* Top bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, zIndex: 1000,
        padding: "max(env(safe-area-inset-top,12px),12px) 16px 12px",
        background: "linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)",
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        pointerEvents: "none",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, pointerEvents: "auto" }}>
          <button onClick={onBack} style={backBtnStyle}>←</button>
          <div>
            <div style={{
              fontSize: 22, fontWeight: 700, letterSpacing: "0.08em",
              fontFamily: "'Space Mono', monospace", color: "#fff",
            }}>LONDON</div>
            <div style={{
              fontSize: 11, color: "rgba(255,255,255,0.5)", letterSpacing: "0.06em",
              fontFamily: "'Space Mono', monospace",
            }}>
              {filtered.filter(f => f.hiring).length} HIRING · {filtered.length} FUNDS
            </div>
          </div>
        </div>
      </div>

      {/* Signal legend */}
      <div style={{
        position: "absolute", top: 80, left: 16, zIndex: 1000,
        display: "flex", gap: 12, fontFamily: "'Space Mono', monospace", fontSize: 10,
        color: "rgba(255,255,255,0.6)", letterSpacing: "0.06em",
        pointerEvents: "none",
      }}>
        {[
          { label: "HOT", border: "1.5px solid rgba(255,255,255,0.7)", shadow: "0 0 6px rgba(255,255,255,0.3)" },
          { label: "WARM", border: "1.5px solid rgba(255,255,255,0.35)", shadow: "none" },
          { label: "QUIET", border: "1.5px solid rgba(255,255,255,0.12)", shadow: "none" },
        ].map(s => (
          <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{
              width: 8, height: 8, borderRadius: "50%", display: "inline-block",
              border: s.border, boxShadow: s.shadow,
            }} /> {s.label}
          </span>
        ))}
      </div>

      {/* Bottom controls */}
      {!selectedFund && (
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0, zIndex: 1000,
          padding: "0 12px max(env(safe-area-inset-bottom,12px),12px)",
          background: "linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)",
          pointerEvents: "none",
        }}>
          <div style={{
            display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap",
            justifyContent: "center", pointerEvents: "auto",
          }}>
            <button onClick={() => setHiringOnly(!hiringOnly)} style={{
              ...filterBtnStyle,
              background: hiringOnly ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.05)",
              borderColor: hiringOnly ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.12)",
              color: hiringOnly ? "#fff" : "rgba(255,255,255,0.6)",
            }}>
              {hiringOnly ? "● " : ""}HIRING ONLY
            </button>
            <button onClick={() => setShowFilters(!showFilters)} style={{
              ...filterBtnStyle,
              background: focusFilter !== "All" ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.05)",
              borderColor: focusFilter !== "All" ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.12)",
              color: focusFilter !== "All" ? "#fff" : "rgba(255,255,255,0.6)",
            }}>
              {focusFilter === "All" ? "FOCUS ▾" : focusFilter.toUpperCase() + " ✕"}
            </button>
            <button onClick={resetView} style={filterBtnStyle}>⊙ RESET</button>
          </div>

          {showFilters && (
            <div style={{
              display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "center",
              marginBottom: 8, padding: "8px 0", pointerEvents: "auto",
            }}>
              {focuses.map(f => (
                <button key={f} onClick={() => { setFocusFilter(f); setShowFilters(false); }} style={{
                  ...filterBtnStyle, fontSize: 10, padding: "5px 12px",
                  background: focusFilter === f ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.05)",
                  borderColor: focusFilter === f ? "rgba(255,255,255,0.4)" : "rgba(255,255,255,0.1)",
                  color: focusFilter === f ? "#fff" : "rgba(255,255,255,0.5)",
                }}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          )}

          <div style={{
            display: "flex", justifyContent: "space-between", paddingBottom: 4,
            fontFamily: "'Space Mono', monospace", fontSize: 10,
            color: "rgba(255,255,255,0.3)", letterSpacing: "0.06em",
          }}>
            <span>51.5074°N, 0.1278°W</span>
            <span>{filtered.length} FUNDS</span>
          </div>
        </div>
      )}

      {/* Bottom sheet — fund detail */}
      {selectedFund && (
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 0, zIndex: 1001,
          background: "rgba(10,10,12,0.95)", backdropFilter: "blur(12px)",
          borderTop: "1px solid rgba(255,255,255,0.1)",
          padding: "20px 20px max(env(safe-area-inset-bottom,20px),20px)",
          animation: "slideUp 0.3s ease-out",
          maxHeight: "55vh", overflowY: "auto",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
            <div>
              <div style={{
                fontFamily: "'Space Mono', monospace", fontSize: 16, fontWeight: 700,
                color: "#fff", letterSpacing: "0.04em",
              }}>{selectedFund.name}</div>
              <div style={{
                fontFamily: "'Space Mono', monospace", fontSize: 11,
                color: "rgba(255,255,255,0.45)", marginTop: 2,
              }}>
                {selectedFund.neighborhood} · {selectedFund.focus} · {selectedFund.aum}
              </div>
            </div>
            <button onClick={() => setSelected(null)} style={closeBtnStyle}>✕</button>
          </div>

          {selectedFund.hiring && selectedFund.roles.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {selectedFund.roles.map((r, i) => (
                <div key={i} style={{
                  padding: "12px 14px", border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 6, background: "rgba(255,255,255,0.03)",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{
                      fontFamily: "'Space Mono', monospace", fontSize: 13, fontWeight: 600, color: "#fff",
                    }}>{r.title}</span>
                    <span style={{
                      fontFamily: "'Space Mono', monospace", fontSize: 9, fontWeight: 700,
                      padding: "2px 8px", borderRadius: 3, letterSpacing: "0.08em",
                      background: r.freshness === "HOT" ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.06)",
                      color: r.freshness === "HOT" ? "#fff" : "rgba(255,255,255,0.5)",
                      border: `1px solid ${r.freshness === "HOT" ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.1)"}`,
                    }}>{r.freshness}</span>
                  </div>
                  <div style={{
                    fontFamily: "'Space Mono', monospace", fontSize: 11,
                    color: "rgba(255,255,255,0.4)", marginTop: 6, lineHeight: 1.5,
                  }}>{r.description}</div>
                  <div style={{
                    fontFamily: "'Space Mono', monospace", fontSize: 10,
                    color: "rgba(255,255,255,0.25)", marginTop: 6,
                  }}>{r.posted} · {r.source}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              fontFamily: "'Space Mono', monospace", fontSize: 12,
              color: "rgba(255,255,255,0.3)", padding: "12px 0",
            }}>No open roles detected.</div>
          )}
        </div>
      )}

      {/* Custom styles for Leaflet overrides */}
      <style>{`
        .fund-marker, .fund-cluster {
          background: none !important;
          border: none !important;
        }
        .leaflet-container {
          background: #0a0a0a !important;
          font-family: 'Space Mono', monospace !important;
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .leaflet-interactive {
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .leaflet-grab {
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .leaflet-dragging .leaflet-grab {
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .leaflet-container * {
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .fund-marker *, .fund-cluster * {
          cursor: url('/hitmarker.svg') 16 16, crosshair !important;
        }
        .leaflet-control-attribution { display: none !important; }
        .marker-cluster-small, .marker-cluster-medium, .marker-cluster-large {
          background: none !important;
        }
        .leaflet-tile {
          filter: brightness(1.3) contrast(1.05) saturate(0.15);
        }
      `}</style>
    </div>
  );
}

/* ── Shared button styles ── */
const backBtnStyle = {
  background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
  color: "#fff", width: 36, height: 36, borderRadius: 6,
  display: "flex", alignItems: "center", justifyContent: "center",
  cursor: "pointer", fontSize: 18, fontFamily: "'Space Mono', monospace",
};

const closeBtnStyle = {
  background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
  color: "#fff", width: 32, height: 32, borderRadius: 6,
  cursor: "pointer", fontSize: 16, fontFamily: "'Space Mono', monospace",
  display: "flex", alignItems: "center", justifyContent: "center",
};

const filterBtnStyle = {
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.12)",
  color: "rgba(255,255,255,0.6)",
  padding: "6px 14px", borderRadius: 4, cursor: "pointer",
  fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: "0.06em",
};
