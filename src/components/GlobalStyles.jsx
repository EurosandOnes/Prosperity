/**
 * GlobalStyles.jsx — Keyframes, font imports, and global CSS.
 */

import { FONTS } from "../config/theme";

export default function GlobalStyles() {
  return (
    <style>{`
      @import url('${FONTS.import}');

      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      html, body, #root {
        width: 100%; height: 100%; overflow: hidden;
        background: #000; color: #999;
        font-family: ${FONTS.body};
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        cursor: url('/hitmarker.svg') 16 16, crosshair;
      }

      a, button, [role="button"] {
        cursor: url('/hitmarker.svg') 16 16, crosshair;
      }

      * {
        cursor: url('/hitmarker.svg') 16 16, crosshair !important;
      }

      ::-webkit-scrollbar { width: 4px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }

      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
      @keyframes slideUp {
        from { transform: translateY(100%); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
      @keyframes scan {
        from { transform: translateY(-100%); }
        to { transform: translateY(100vh); }
      }

      /* Click feedback — sonar ping */
      @keyframes sonarPing {
        0% { width: 0px; height: 0px; opacity: 0.3; border-width: 1px; }
        100% { width: 40px; height: 40px; opacity: 0; border-width: 0.5px; }
      }
      .click-ping {
        position: fixed;
        border: 1px solid rgba(255,255,255,0.4);
        border-radius: 50%;
        pointer-events: none;
        z-index: 99999;
        transform: translate(-50%, -50%);
        animation: sonarPing 0.35s ease-out forwards;
      }

      @keyframes ebbHot {
        0%, 100% {
          box-shadow: 0 0 10px rgba(255,255,255,0.15), 0 0 24px rgba(255,255,255,0.08);
          border-color: rgba(255,255,255,0.45);
        }
        50% {
          box-shadow: 0 0 18px rgba(255,255,255,0.35), 0 0 40px rgba(255,255,255,0.18), 0 0 60px rgba(255,255,255,0.08);
          border-color: rgba(255,255,255,0.7);
        }
      }

      @keyframes ebbWarm {
        0%, 100% {
          box-shadow: 0 0 6px rgba(255,255,255,0.06), 0 0 14px rgba(255,255,255,0.03);
          border-color: rgba(255,255,255,0.25);
        }
        50% {
          box-shadow: 0 0 10px rgba(255,255,255,0.14), 0 0 22px rgba(255,255,255,0.07);
          border-color: rgba(255,255,255,0.4);
        }
      }

      @keyframes roleEbb {
        0%, 100% { border-color: rgba(255,255,255,0.1); }
        50% { border-color: rgba(255,255,255,0.25); }
      }
    `}</style>
  );
}
