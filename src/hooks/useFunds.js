/**
 * useFunds.js — Data layer abstraction.
 * 
 * This is THE ONLY FILE that changes when switching from mock to live data.
 * Every component consumes funds through this hook. None of them know or care
 * whether the data comes from a hardcoded array or a pipeline API.
 * 
 * SWITCHING TO LIVE DATA:
 * 1. Set LIVE_DATA_URL to your roles.json endpoint
 * 2. Set USE_LIVE_DATA to true
 * 3. That's it. Everything else is wired.
 */

import { useState, useEffect, useMemo } from "react";
import MOCK_FUNDS from "../data/mockFunds";
import { lookupFundCoords } from "../data/fundCoordinates";

// ── Toggle this to switch data sources ──
const USE_LIVE_DATA = false;
const LIVE_DATA_URL = "/data/roles.json"; // Served from public/data/ in the repo

export default function useFunds() {
  const [rawFunds, setRawFunds] = useState(USE_LIVE_DATA ? [] : MOCK_FUNDS);
  const [loading, setLoading] = useState(USE_LIVE_DATA);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Fetch live data if enabled
  useEffect(() => {
    if (!USE_LIVE_DATA) return;

    async function fetchFunds() {
      try {
        const resp = await fetch(LIVE_DATA_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        // Pipeline outputs { funds: { id: {...} }, roles: [...], stats: {...} }
        // Transform to array format the components expect
        const fundList = Object.values(data.funds || {}).map((f, i) => {
          // Look up real coordinates from our verified database
          const coords = lookupFundCoords(f.id);

          let lat, lng, neighborhood;
          if (coords) {
            lat = coords.lat;
            lng = coords.lng;
            neighborhood = coords.neighborhood;
          } else {
            // Fund not in our database — place in central London
            // using golden angle distribution to avoid overlap
            const angle = i * 2.399;
            const radius = 0.003 + (i * 0.0004);
            lat = 51.518 + Math.sin(angle) * Math.min(radius, 0.012);
            lng = -0.130 + Math.cos(angle) * Math.min(radius, 0.016);
            neighborhood = f.neighborhood || "London";
          }

          return {
            id: f.id,
            name: f.name,
            initials: f.initials,
            focus: f.focus,
            neighborhood: neighborhood,
            lat,
            lng,
            website: f.website || "",
            aum: f.aum || "",
            founded: f.founded || 0,
            hiring: f.hiring,
            roles: (f.roles || []).map(r => ({
              title: r.title,
              freshness: r.freshness,
              source: r.source,
              url: r.source_url,
              description: r.description,
              posted: r.posted_ago || "recently",
            })),
          };
        });

        setRawFunds(fundList);
        setLastUpdated(data.generated_at || new Date().toISOString());
        setError(null);
      } catch (err) {
        console.error("[useFunds] Fetch failed, falling back to mock:", err);
        setRawFunds(MOCK_FUNDS);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchFunds();

    // Re-fetch every 30 minutes if tab stays open
    const interval = setInterval(fetchFunds, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Derived stats (memoized — only recompute when data changes)
  const stats = useMemo(() => ({
    totalFunds: rawFunds.length,
    fundsHiring: rawFunds.filter(f => f.hiring).length,
    hotRoles: rawFunds.reduce((a, f) => a + f.roles.filter(r => r.freshness === "HOT").length, 0),
    warmRoles: rawFunds.reduce((a, f) => a + f.roles.filter(r => r.freshness === "WARM").length, 0),
    totalRoles: rawFunds.reduce((a, f) => a + f.roles.length, 0),
  }), [rawFunds]);

  return {
    funds: rawFunds,
    stats,
    loading,
    error,
    lastUpdated,
    isLive: USE_LIVE_DATA,
  };
}
