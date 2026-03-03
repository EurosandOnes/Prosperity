/**
 * theme.js — Visual constants shared across all components.
 */

export const COLORS = {
  void: "#000000",
  land: "rgba(255,255,255,0.09)",
  landStroke: "rgba(255,255,255,0.22)",
  landBack: "rgba(255,255,255,0.018)",
  landStrokeBack: "rgba(255,255,255,0.04)",
  grid: "rgba(255,255,255,0.02)",
  gridFront: "rgba(255,255,255,0.04)",
  accent: "#ffffff",
  accentFaint: "rgba(255,255,255,0.08)",
  text: "#999",
  textBright: "#ccc",
  textDim: "#333",
};

export const FOCUS_COLORS = {
  "Pre-seed / Seed": "#00E0C8",
  "Early Stage": "#4A9EFF",
  "Growth": "#B76FFF",
  "Multi-stage": "#FFB830",
  "B2B / Enterprise": "#2EE08A",
  "Consumer": "#FF5C99",
  "Secondaries": "#FF8C38",
  "Deep Tech": "#FF4D4D",
};

export const FRESHNESS = {
  HOT:  { label: "< 1 week",  color: "#FF3D3D", bg: "rgba(255,61,61,0.12)", sort: 0 },
  WARM: { label: "< 1 month", color: "#FFB830", bg: "rgba(255,184,48,0.08)", sort: 1 },
};

export const FONTS = {
  heading: "'Syne', sans-serif",
  mono: "'Space Mono', monospace",
  body: "'Outfit', sans-serif",
  import: "https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Outfit:wght@300;400;500;600&display=swap",
};

/**
 * Get a fund's logo URL via Google's favicon service (always free, no API key).
 * Returns a 128px icon for any domain. Falls back to null if no website.
 */
export function getFundLogoUrl(website) {
  if (!website) return null;
  try {
    const domain = new URL(website).hostname.replace("www.", "");
    return `https://t1.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${domain}&size=128`;
  } catch {
    return null;
  }
}
