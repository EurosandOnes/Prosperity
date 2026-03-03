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
        const fundList = Object.values(data.funds || {}).map(f => ({
          id: f.id,
          name: f.name,
          initials: f.initials,
          focus: f.focus,
          neighborhood: f.neighborhood,
          x: f.map_x,
          y: f.map_y,
          aum: f.aum,
          founded: f.founded,
          hiring: f.hiring,
          roles: (f.roles || []).map(r => ({
            title: r.title,
            freshness: r.freshness,
            source: r.source,
            url: r.source_url,
            description: r.description,
            posted: r.posted_ago || "recently",
          })),
        }));

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
