/**
 * App.jsx — Orchestrator. Dark theme only.
 */

import { useState, useEffect } from "react";
import { COLORS as C, FONTS } from "./config/theme";
import useFunds from "./hooks/useFunds";
import GlobalStyles from "./components/GlobalStyles";
import WorldView from "./components/WorldView";
import CityMap from "./components/CityMap";

export default function App() {
  const { funds, stats } = useFunds();
  const [view, setView] = useState("world");
  const [transitioning, setTransitioning] = useState(false);

  /* ── Click feedback — sonar ping ── */
  useEffect(() => {
    const handleClick = (e) => {
      const ping = document.createElement("div");
      ping.className = "click-ping";
      ping.style.left = e.clientX + "px";
      ping.style.top = e.clientY + "px";
      document.body.appendChild(ping);
      setTimeout(() => ping.remove(), 400);
    };

    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  const enterCity = () => {
    setTransitioning(true);
    setTimeout(() => { setView("city"); setTransitioning(false); }, 500);
  };

  const exitCity = () => {
    setTransitioning(true);
    setTimeout(() => { setView("world"); setTransitioning(false); }, 400);
  };

  return (
    <div style={{
      width: "100vw", height: "100dvh", overflow: "hidden",
      position: "relative", fontFamily: FONTS.mono,
      background: C.void, color: C.text,
      touchAction: "manipulation",
      WebkitTapHighlightColor: "transparent",
    }}>
      <GlobalStyles />

      {/* Scanline overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 100, overflow: "hidden",
        opacity: 0.025,
      }}>
        <div style={{
          width: "100%", height: 1,
          background: "rgba(255,255,255,0.6)",
          animation: "scan 10s linear infinite",
        }}/>
      </div>

      {view === "world" && (
        <WorldView stats={stats} onEnter={enterCity} exiting={transitioning} />
      )}
      {view === "city" && (
        <CityMap funds={funds} onBack={exitCity} />
      )}
    </div>
  );
}
