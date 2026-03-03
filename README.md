# Prosperity

VC hiring intelligence — a real-time map of who's hiring across London's venture capital ecosystem.

## Architecture

```
prosperity/
├── src/                          # React frontend (Vite)
│   ├── App.jsx                   # View orchestrator (world ↔ city)
│   ├── main.jsx                  # Entry point
│   ├── config/
│   │   ├── theme.js              # Colors, fonts, freshness thresholds
│   │   └── cities.js             # City coordinates for globe
│   ├── data/
│   │   └── mockFunds.js          # Dev-only hardcoded data (16 funds)
│   ├── hooks/
│   │   └── useFunds.js           # Data layer — swap mock ↔ live here
│   └── components/
│       ├── Globe.jsx             # 3D orthographic globe (d3 + canvas)
│       ├── WorldView.jsx         # Globe screen + stats + CTA
│       ├── CityMap.jsx           # City view with filters
│       ├── FundNode.jsx          # Single fund marker
│       ├── FundSheet.jsx         # Bottom sheet detail panel
│       └── GlobalStyles.jsx      # Keyframes, fonts, CSS reset
│
├── pipeline/                     # Python data pipeline
│   ├── discovery.py              # Auto-discovers funds from VC directories
│   ├── pipeline.py               # Scrapes job postings from ATS APIs
│   └── requirements.txt          # Python dependencies
│
├── public/data/                  # Pipeline output (committed by GitHub Actions)
│   ├── funds_registry.json       # All known funds + ATS detection results
│   └── roles.json                # Current job postings
│
├── .github/workflows/
│   ├── discover.yml              # Weekly: scrape directories, probe ATS
│   └── scrape.yml                # 6-hourly: pull job postings
│
├── middleware.js                  # Vercel Edge auth (server-side password)
├── vercel.json                   # Vercel deployment config
├── vite.config.js                # Vite build config
└── package.json
```

## Quickstart

### 1. Run locally (mock data)

```bash
npm install
npm run dev
```

Opens at `http://localhost:3000`. Uses hardcoded mock data from `src/data/mockFunds.js`.

### 2. Run discovery + pipeline (live data)

```bash
pip install -r pipeline/requirements.txt

# Discover funds and probe their ATS systems
python pipeline/discovery.py

# Scrape live job postings
python pipeline/pipeline.py
```

This writes `funds_registry.json` and `roles.json` into `public/data/`.

### 3. Switch frontend to live data

In `src/hooks/useFunds.js`, change:

```js
const USE_LIVE_DATA = true;
```

The frontend will now fetch from `/data/roles.json` instead of mock data.

### 4. Deploy to Vercel

```bash
# Connect repo to Vercel (one-time)
npx vercel link

# Set password
# Vercel Dashboard → Settings → Environment Variables → SITE_PASSWORD = your_password

# Deploy
npx vercel --prod
```

## Data Pipeline

### Fund Discovery (`pipeline/discovery.py`)

Runs weekly. Automatically finds and registers London VC funds by:

1. Starting with a compiled seed list of 50+ confirmed funds
2. Scraping public VC directories (Gilion, Seedtable) for additional funds
3. Optionally searching Google for newly launched funds
4. Probing each fund's website for ATS systems (Lever, Greenhouse, Ashby)
5. Outputting `funds_registry.json`

### Job Scraping (`pipeline/pipeline.py`)

Runs every 6 hours. For each fund in the registry:

1. Checks Lever API (free, no auth) — ~40% of funds
2. Checks Greenhouse API (free, no auth) — ~20% of funds
3. Optionally searches Google for LinkedIn hiring posts
4. Optionally checks Twitter/X for hiring announcements
5. Normalises, deduplicates, and freshness-scores all roles
6. Outputs `roles.json`

### Freshness Scoring

- **HOT** (< 7 days): White indicator — actively being filled
- **WARM** (7-30 days): Grey indicator — still open
- **EXPIRED** (> 30 days): Removed from output

## GitHub Actions

Both workflows run automatically and commit data back to the repo.

### Required Secrets

Set these in GitHub → Settings → Secrets:

| Secret | Required | Purpose |
|--------|----------|---------|
| `GOOGLE_CSE_API_KEY` | Optional | Google Custom Search (100 free queries/day) |
| `GOOGLE_CSE_CX` | Optional | Custom Search Engine ID |
| `TWITTER_BEARER_TOKEN` | Optional | X/Twitter API v2 |
| `PROXYCURL_API_KEY` | Optional | LinkedIn data ($0.01-0.03/call) |

The pipeline works with zero secrets — Lever and Greenhouse APIs require no authentication. Adding Google CSE significantly improves LinkedIn post discovery.

### Manual Triggers

Both workflows can be triggered manually from GitHub → Actions → select workflow → "Run workflow".

## Authentication

`middleware.js` runs on Vercel's edge before any page content is served. Without a valid auth cookie, visitors see a server-rendered login page. Your React app bundle, fund data, and pipeline logic are never exposed.

Set `SITE_PASSWORD` in Vercel's environment variables. No password set = open access (useful for local dev).

## Adding Cities

1. Add coordinates to `src/config/cities.js`
2. Add a new view component for that city's map
3. Update `App.jsx` routing
4. Add funds for that city to the discovery seed list

## Cost

$0/month on free tiers (Vercel free, GitHub Actions free, Lever/Greenhouse APIs free). Optional: ~$15-45/month for Proxycurl LinkedIn coverage.
