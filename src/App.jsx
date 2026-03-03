/**
 * App.jsx — Orchestrator.
 * Manages view state and light/dark theme transition on London hover.
 */

import { useState } from "react";
import { COLORS as C, FONTS } from "./config/theme";
import useFunds from "./hooks/useFunds";
import GlobalStyles from "./components/GlobalStyles";
import WorldView from "./components/WorldView";
import CityMap from "./components/CityMap";

export default function App() {
  const { funds, stats, loading, error, isLive } = useFunds();
  const [view, setView] = useState("world");
  const [transitioning, setTransitioning] = useState(false);
  const [hoveringLondon, setHoveringLondon] = useState(false);

  const enterCity = () => {
    setTransitioning(true);
    setHoveringLondon(false);
    setTimeout(() => { setView("city"); setTransitioning(false); }, 600);
  };

  const exitCity = () => {
    setTransitioning(true);
    setTimeout(() => { setView("world"); setTransitioning(false); }, 400);
  };

  const light = hoveringLondon && view === "world";

  return (
    <div style={{
      width: "100vw", height: "100dvh", overflow: "hidden",
      position: "relative", fontFamily: FONTS.mono,
      background: light ? "#f0f0f0" : C.void,
      color: light ? "#222" : C.text,
      touchAction: "manipulation",
      WebkitTapHighlightColor: "transparent",
      transition: "background 0.6s ease, color 0.6s ease",
    }}>
      <GlobalStyles light={light} />

      {/* Scanline overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 100, overflow: "hidden",
        opacity: light ? 0.01 : 0.025,
        transition: "opacity 0.6s ease",
      }}>
        <div style={{
          width: "100%", height: 1,
          background: light ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.6)",
          animation: "scan 10s linear infinite",
          transition: "background 0.6s ease",
        }}/>
      </div>

      {view === "world" && (
        <WorldView
          stats={stats}
          onEnter={enterCity}
          exiting={transitioning}
          light={light}
          onHoverLondon={setHoveringLondon}
        />
      )}
      {view === "city" && (
        <CityMap funds={funds} onBack={exitCity} />
      )}
    </div>
  );
}
