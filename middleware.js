/**
 * middleware.js — Vercel Edge Middleware (framework-agnostic)
 * ==========================================================
 * 
 * Runs on Vercel's edge BEFORE your Vite app is sent to the browser.
 * No Next.js required — uses standard Web APIs only.
 * 
 * SETUP:
 * 1. This file lives at the project root (next to package.json)
 * 2. Set SITE_PASSWORD in Vercel → Settings → Environment Variables
 * 3. Deploy. That's it.
 * 
 * The password never appears in client-side code.
 * Unauthenticated visitors see a server-rendered login page.
 * Your React app bundle is never served without a valid cookie.
 */

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|assets|favicon.ico|.*\\.(?:js|css|png|jpg|svg|ico|woff2?|ttf)$).*)"],
};

const COOKIE_NAME = "prosperity_auth";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export default async function middleware(request) {
  const password = process.env.SITE_PASSWORD;

  // No password set → allow all access (local dev)
  if (!password) return;

  // Check auth cookie
  const cookies = parseCookies(request.headers.get("cookie") || "");
  if (cookies[COOKIE_NAME]) {
    const expected = await sha256(`prosperity:${password}`);
    if (cookies[COOKIE_NAME] === expected) return; // Authenticated
  }

  // Handle POST (password submission)
  if (request.method === "POST") {
    const body = await request.text();
    const params = new URLSearchParams(body);
    const submitted = params.get("password") || "";

    if (submitted === password) {
      const hash = await sha256(`prosperity:${password}`);
      return new Response(null, {
        status: 302,
        headers: {
          "Location": new URL(request.url).pathname,
          "Set-Cookie": `${COOKIE_NAME}=${hash}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${COOKIE_MAX_AGE}`,
        },
      });
    }

    // Wrong password
    return new Response(loginHTML(true), {
      status: 401,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  }

  // No cookie, GET → show login
  return new Response(loginHTML(false), {
    status: 401,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function parseCookies(str) {
  const obj = {};
  str.split(";").forEach(pair => {
    const [k, ...v] = pair.trim().split("=");
    if (k) obj[k.trim()] = v.join("=").trim();
  });
  return obj;
}

async function sha256(str) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function loginHTML(error) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Access Required</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #000; color: #999;
      font-family: 'Space Mono', monospace;
      height: 100dvh; width: 100vw; overflow: hidden;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      -webkit-font-smoothing: antialiased;
    }
    @keyframes scan { from{transform:translateY(-100%)} to{transform:translateY(100vh)} }
    @keyframes fadeIn { from{opacity:0} to{opacity:1} }
    @keyframes shake { 0%,100%{transform:translateX(0)} 20%,60%{transform:translateX(-6px)} 40%,80%{transform:translateX(6px)} }
    @keyframes pulseGlow { 0%,100%{opacity:0.03} 50%{opacity:0.06} }
    .scanline { position:fixed; inset:0; pointer-events:none; z-index:100; overflow:hidden; opacity:0.025; }
    .scanline div { width:100%; height:1px; background:rgba(255,255,255,0.6); animation:scan 10s linear infinite; }
    .glow { position:absolute; width:300px; height:300px; border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,0.03) 0%,transparent 70%); animation:pulseGlow 4s ease-in-out infinite; pointer-events:none; }
    .top-bar { position:absolute; top:0; left:0; right:0; padding:max(env(safe-area-inset-top,16px),16px) 16px 0; display:flex; justify-content:space-between; font-size:7px; color:#1a1a1a; letter-spacing:0.16em; }
    .lock { width:48px; height:48px; border:1.5px solid #222; border-radius:50%; display:flex; align-items:center; justify-content:center; margin-bottom:32px; }
    .form-wrap { width:min(280px,80vw); animation:${error ? "shake 0.4s ease-out" : "fadeIn 0.6s ease-out"}; }
    input[type="password"] { width:100%; padding:14px 16px; background:#060606; border:1px solid ${error ? "#FF4D4D33" : "#1a1a1a"}; border-radius:0; font-family:'Space Mono',monospace; font-size:11px; font-weight:700; color:#ccc; letter-spacing:0.12em; text-align:center; transition:border-color 0.2s; }
    input:focus { outline:none; border-color:#333; }
    input::placeholder { color:#2a2a2a; }
    .error-msg { text-align:center; margin-top:10px; font-size:8px; color:#FF4D4D; letter-spacing:0.1em; animation:fadeIn 0.2s ease-out; }
    button { width:100%; margin-top:12px; padding:13px 0; background:#111; border:none; border-radius:0; font-family:'Space Mono',monospace; font-size:10px; font-weight:700; color:#333; letter-spacing:0.14em; cursor:pointer; transition:all 0.2s; }
    button:hover { background:#fff; color:#000; }
    .footer { position:absolute; bottom:max(env(safe-area-inset-bottom,20px),20px); font-size:7px; color:#0a0a0a; letter-spacing:0.14em; }
  </style>
</head>
<body>
  <div class="scanline"><div></div></div>
  <div class="glow"></div>
  <div class="top-bar"><span>RESTRICTED ACCESS</span><span>AUTH:REQUIRED</span></div>
  <div class="lock">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#444" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  </div>
  <form method="POST" class="form-wrap">
    <input type="password" name="password" placeholder="ENTER PASSWORD" autofocus required />
    ${error ? '<div class="error-msg">ACCESS DENIED</div>' : ""}
    <button type="submit">AUTHENTICATE</button>
  </form>
  <p class="footer">AUTHORISED PERSONNEL ONLY</p>
  <script>
    const i=document.querySelector('input'),b=document.querySelector('button');
    i.addEventListener('input',()=>{b.style.background=i.value?'#fff':'#111';b.style.color=i.value?'#000':'#333';});
  </script>
</body>
</html>`;
}
