/**
 * Globe.jsx — 3D orthographic globe with real country borders.
 * Detects mouse proximity to London and fires onHoverLondon callback.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";
import { COLORS as C } from "../config/theme";
import { CITIES, INACTIVE_CITIES } from "../config/cities";

function decodeTopo(topo, key) {
  const tf = topo.transform;
  const arcs = topo.arcs.map(arc => {
    let x = 0, y = 0;
    return arc.map(([dx, dy]) => {
      x += dx; y += dy;
      return [x * tf.scale[0] + tf.translate[0], y * tf.scale[1] + tf.translate[1]];
    });
  });
  const decArc = i => (i < 0 ? arcs[~i].slice().reverse() : arcs[i].slice());
  const decRing = ids => { let c = []; ids.forEach(i => c.push(...decArc(i))); return c; };
  const decGeom = g => {
    if (g.type === "Polygon") return { type: "Polygon", coordinates: g.arcs.map(decRing) };
    if (g.type === "MultiPolygon") return { type: "MultiPolygon", coordinates: g.arcs.map(p => p.map(decRing)) };
    return g;
  };
  const obj = topo.objects[key];
  if (!obj) return { type: "FeatureCollection", features: [] };
  if (obj.type === "GeometryCollection") {
    return { type: "FeatureCollection", features: obj.geometries.map(g => ({ type: "Feature", properties: g.properties || {}, geometry: decGeom(g) })) };
  }
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: obj.properties || {}, geometry: decGeom(obj) }] };
}

export default function Globe({ onEnterCity, light, onHoverLondon }) {
  const cvRef = useRef(null);
  const rotRef = useRef([0.12, -28, 0]);
  const dragRef = useRef(false);
  const lastRef = useRef(null);
  const animRef = useRef(null);
  const tRef = useRef(0);
  const geoRef = useRef(null);
  const hoverRef = useRef(false);
  const lightRef = useRef(light);
  const [loaded, setLoaded] = useState(false);

  lightRef.current = light;

  useEffect(() => {
    fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
      .then(r => r.json())
      .then(topo => { geoRef.current = decodeTopo(topo, Object.keys(topo.objects)[0]); setLoaded(true); })
      .catch(() => { setLoaded(true); });
  }, []);

  const london = CITIES.london;

  const draw = useCallback(() => {
    const cv = cvRef.current; if (!cv) return;
    const ctx = cv.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr;
    ctx.scale(dpr, dpr);
    const R = Math.min(w, h) * 0.46;
    const cx = w / 2, cy = h / 2;
    const lx = cx - R * 0.65, ly = cy - R * 0.65;
    const rot = rotRef.current;
    const pF = d3.geoOrthographic().translate([cx, cy]).scale(R).rotate(rot).clipAngle(90);
    const pA = d3.geoOrthographic().translate([cx, cy]).scale(R).rotate(rot).clipAngle(180);
    const dF = d3.geoPath(pF, ctx);
    const dA = d3.geoPath(pA, ctx);
    const isLight = lightRef.current;
    ctx.clearRect(0, 0, w, h);

    // Colors adapt to theme
    const landFill = isLight ? "rgba(0,0,0,0.06)" : C.land;
    const landStroke = isLight ? "rgba(0,0,0,0.15)" : C.landStroke;
    const landBackFill = isLight ? "rgba(0,0,0,0.02)" : C.landBack;
    const landBackStroke = isLight ? "rgba(0,0,0,0.03)" : C.landStrokeBack;
    const gridColor = isLight ? "rgba(0,0,0,0.015)" : C.grid;
    const gridFrontColor = isLight ? "rgba(0,0,0,0.03)" : C.gridFront;
    const sphereFill = isLight ? "rgba(230,230,235,0.85)" : "rgba(8,8,10,0.85)";
    const rimStroke = isLight ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.05)";
    const beaconColor = isLight ? "0,0,0" : "255,255,255";
    const textColor = isLight ? "rgba(50,50,50," : "rgba(200,200,200,";
    const subTextColor = isLight ? "rgba(80,80,80," : "rgba(150,150,150,";

    // Atmosphere
    const a1 = ctx.createRadialGradient(cx, cy, R * 0.85, cx, cy, R * 1.35);
    a1.addColorStop(0, isLight ? "rgba(0,0,0,0.006)" : "rgba(255,255,255,0.008)");
    a1.addColorStop(0.6, "transparent"); a1.addColorStop(1, "transparent");
    ctx.fillStyle = a1; ctx.fillRect(0, 0, w, h);

    // Sphere
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fillStyle = sphereFill; ctx.fill();

    // Specular
    const sg = ctx.createRadialGradient(lx, ly, 0, lx, ly, R * 1.1);
    const specColor = isLight ? "rgba(255,255,255," : "rgba(255,255,255,";
    sg.addColorStop(0, specColor + "0.06)"); sg.addColorStop(0.3, specColor + "0.02)"); sg.addColorStop(0.7, specColor + "0.005)"); sg.addColorStop(1, "transparent");
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip(); ctx.fillStyle = sg; ctx.fillRect(0, 0, w, h); ctx.restore();

    // Shadow
    const shg = ctx.createRadialGradient(cx + R * 0.5, cy + R * 0.5, 0, cx + R * 0.5, cy + R * 0.5, R * 1.4);
    shg.addColorStop(0, isLight ? "rgba(0,0,0,0.12)" : "rgba(0,0,0,0.4)");
    shg.addColorStop(0.5, isLight ? "rgba(0,0,0,0.04)" : "rgba(0,0,0,0.15)");
    shg.addColorStop(1, "transparent");
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip(); ctx.fillStyle = shg; ctx.fillRect(0, 0, w, h); ctx.restore();

    // Back-face
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    if (geoRef.current) {
      const g = d3.geoGraticule().step([20, 20])();
      ctx.beginPath(); dA(g); ctx.strokeStyle = gridColor; ctx.lineWidth = 0.3; ctx.stroke();
      geoRef.current.features.forEach(f => { ctx.beginPath(); dA(f); ctx.fillStyle = landBackFill; ctx.fill(); ctx.strokeStyle = landBackStroke; ctx.lineWidth = 0.25; ctx.stroke(); });
    }
    ctx.restore();

    // Front-face
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    if (geoRef.current) {
      const g = d3.geoGraticule().step([20, 20])();
      ctx.beginPath(); dF(g); ctx.strokeStyle = gridFrontColor; ctx.lineWidth = 0.4; ctx.stroke();
      geoRef.current.features.forEach(f => { ctx.beginPath(); dF(f); ctx.fillStyle = landFill; ctx.fill(); ctx.strokeStyle = landStroke; ctx.lineWidth = 0.5; ctx.stroke(); });
      const ll = ctx.createRadialGradient(lx, ly, 0, lx, ly, R * 1.2);
      ll.addColorStop(0, isLight ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.04)");
      ll.addColorStop(0.5, "transparent"); ll.addColorStop(1, "transparent");
      geoRef.current.features.forEach(f => { ctx.beginPath(); dF(f); ctx.fillStyle = ll; ctx.fill(); });
    }
    ctx.restore();

    // Rim
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.strokeStyle = rimStroke; ctx.lineWidth = 1; ctx.stroke();

    // Inactive cities
    INACTIVE_CITIES.forEach(co => {
      const p = pF(co); if (!p) return;
      const gd = d3.geoDistance(co, pF.invert([cx, cy]));
      if (gd > Math.PI / 2) return;
      ctx.beginPath(); ctx.arc(p[0], p[1], 1.5, 0, Math.PI * 2);
      const a = 0.1 * Math.max(0, 1 - gd / (Math.PI / 2));
      ctx.fillStyle = isLight ? `rgba(0,0,0,${a * 1.5})` : `rgba(255,255,255,${a})`; ctx.fill();
    });

    // London beacon
    const lp = pF(london.coord);
    if (lp) {
      const gd = d3.geoDistance(london.coord, pF.invert([cx, cy]));
      if (gd < Math.PI / 2) {
        tRef.current += 0.018;
        const ps = 1 + 0.4 * Math.sin(tRef.current * 2);
        const pa = 0.1 + 0.1 * Math.sin(tRef.current * 2);
        const fd = Math.max(0.2, 1 - gd / (Math.PI / 2));
        const og = ctx.createRadialGradient(lp[0], lp[1], 0, lp[0], lp[1], 30 * ps);
        og.addColorStop(0, `rgba(${beaconColor},${pa * fd})`); og.addColorStop(1, "transparent");
        ctx.beginPath(); ctx.arc(lp[0], lp[1], 30 * ps, 0, Math.PI * 2); ctx.fillStyle = og; ctx.fill();
        ctx.beginPath(); ctx.arc(lp[0], lp[1], 14 * ps, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${beaconColor},${0.1 * fd})`; ctx.lineWidth = 0.5; ctx.stroke();
        ctx.beginPath(); ctx.arc(lp[0], lp[1], 3.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${beaconColor},${0.95 * fd})`; ctx.shadowColor = isLight ? "#000" : "#fff"; ctx.shadowBlur = 16 * fd; ctx.fill(); ctx.shadowBlur = 0;
        if (fd > 0.45) {
          ctx.font = `700 ${Math.round(11 * fd)}px 'Space Mono', monospace`;
          ctx.fillStyle = textColor + `${fd * 0.85})`; ctx.textAlign = "center";
          ctx.fillText(london.name, lp[0], lp[1] + 20);
          ctx.font = `400 ${Math.round(8 * fd)}px 'Space Mono', monospace`;
          ctx.fillStyle = subTextColor + `${fd * 0.35})`;
          ctx.fillText(london.label, lp[0], lp[1] + 31);
        }
      }
    }
  }, [loaded, london, light]);

  const animate = useCallback(() => {
    if (!dragRef.current) rotRef.current = [rotRef.current[0] + 0.05, rotRef.current[1], 0];
    draw(); animRef.current = requestAnimationFrame(animate);
  }, [draw]);
  useEffect(() => { animRef.current = requestAnimationFrame(animate); return () => cancelAnimationFrame(animRef.current); }, [animate]);

  // Hover detection
  const checkHover = useCallback((clientX, clientY) => {
    const cv = cvRef.current; if (!cv || !onHoverLondon) return;
    const r = cv.getBoundingClientRect();
    const x = clientX - r.left, y = clientY - r.top;
    const R = Math.min(cv.clientWidth, cv.clientHeight) * 0.46;
    const proj = d3.geoOrthographic().translate([cv.clientWidth / 2, cv.clientHeight / 2]).scale(R).rotate(rotRef.current).clipAngle(90);
    const lp = proj(london.coord);
    const near = lp && Math.sqrt((x - lp[0]) ** 2 + (y - lp[1]) ** 2) < 55;
    if (near !== hoverRef.current) {
      hoverRef.current = near;
      onHoverLondon(near);
    }
  }, [london, onHoverLondon]);

  const gp = e => { const t = e.touches ? e.touches[0] : e; return [t.clientX, t.clientY]; };
  const onD = e => { dragRef.current = true; lastRef.current = gp(e); };
  const onM = e => {
    checkHover(e.clientX, e.clientY);
    if (!dragRef.current || !lastRef.current) return;
    const p = gp(e);
    rotRef.current = [rotRef.current[0] + (p[0] - lastRef.current[0]) * 0.25, Math.max(-65, Math.min(65, rotRef.current[1] - (p[1] - lastRef.current[1]) * 0.25)), 0];
    lastRef.current = p;
  };
  const onU = () => { dragRef.current = false; lastRef.current = null; };
  const onLeave = () => {
    onU();
    if (hoverRef.current && onHoverLondon) { hoverRef.current = false; onHoverLondon(false); }
  };
  const onT = e => {
    const cv = cvRef.current; if (!cv) return;
    const r = cv.getBoundingClientRect();
    const t = e.changedTouches ? e.changedTouches[0] : e;
    const x = t.clientX - r.left, y = t.clientY - r.top;
    const R = Math.min(cv.clientWidth, cv.clientHeight) * 0.46;
    const proj = d3.geoOrthographic().translate([cv.clientWidth / 2, cv.clientHeight / 2]).scale(R).rotate(rotRef.current).clipAngle(90);
    const lp = proj(london.coord);
    if (lp && Math.sqrt((x - lp[0]) ** 2 + (y - lp[1]) ** 2) < 40) onEnterCity("london");
  };

  return (
    <canvas ref={cvRef}
      onClick={onT} onMouseDown={onD} onMouseMove={onM} onMouseUp={onU} onMouseLeave={onLeave}
      onTouchStart={onD} onTouchMove={onM} onTouchEnd={e => { onU(); onT(e); }}
      style={{ width: "100%", height: "100%", cursor: "grab", touchAction: "none" }} />
  );
}
