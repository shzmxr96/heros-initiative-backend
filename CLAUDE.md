# Hero's Initiative — CLAUDE.md

> Persistent context brief for Claude Code operating in this Replit environment.
> Read this at the start of every session before touching any code.

---

## Project Overview

**Hero's Initiative** is Pakistan's first AI-powered Government Traffic Intelligence Platform for Karachi.
It is **not a consumer app** — it is government-facing critical data infrastructure targeting Karachi Traffic Police and Government of Sindh as clients.

**Three core government capabilities:**
1. Predictive Congestion Forecasting (15-minute to 48-hour horizons)
2. Root Cause Intelligence (why is a road congested)
3. Infrastructure Investment Prioritisation (economic impact in PKR, bottleneck ranking)

**Founder:** Muhammad Mir | GitHub: shzmxr96

---

## Critical Decision: Google API Migration

### What was agreed

The data pipeline must migrate from the **legacy Distance Matrix API** to the **Google Routes API (`computeRouteMatrix`)**.

This is not optional — as of March 1, 2025, Google Routes API fully replaces both the Directions API and the Distance Matrix API. The Distance Matrix API is legacy. All new pipeline work must use the Routes API.

### Why we are migrating

1. **Distance Matrix is legacy** — Google's official replacement is the Routes API. Building further on Distance Matrix is technical debt from day one.
2. **Route accuracy problem** — On short segments (under ~1.5km), the legacy Distance Matrix API sometimes routes through side streets rather than the target road. This makes the congestion reading meaningless for that segment. The Routes API solves this with `via:` pass-through waypoints.
3. **Better data** — The Routes API returns `speedReadingIntervals` (per-polyline-segment speed data), `staticDuration` (historical baseline), and heading support — none of which are available in Distance Matrix.

### The route accuracy problem in detail

For short segments where origin and destination coordinates are at intersections (chowrangis), Google has multiple valid route options. On a short segment, Google may route through a side street if it's faster — producing a reading that reflects the side street, not the main road.

**The fix: `via:` pass-through waypoints.** For any segment under ~1.5km, add one mid-road coordinate as a `via:` waypoint. Google is forced to pass through that point and stay on the correct road. Critically, `duration_in_traffic` is still returned when using `via:` waypoints.

---

## Routes API — Implementation Spec

### Endpoint

```
POST https://routes.googleapis.com/directions/v2:computeRouteMatrix
```

### Required headers

```
X-Goog-Api-Key: {GOOGLE_MAPS_API_KEY}
X-Goog-FieldMask: originIndex,destinationIndex,duration,distanceMeters,status,condition
```

For traffic data, add `travelAdvisory` to the field mask:
```
X-Goog-FieldMask: originIndex,destinationIndex,duration,distanceMeters,status,condition,travelAdvisory
```

### Request body structure

```json
{
  "origins": [
    {
      "waypoint": {
        "location": { "latLng": { "latitude": 24.9312, "longitude": 67.1100 } }
      }
    }
  ],
  "destinations": [
    {
      "waypoint": {
        "location": { "latLng": { "latitude": 24.9268, "longitude": 67.0791 } }
      }
    }
  ],
  "travelMode": "DRIVE",
  "routingPreference": "TRAFFIC_AWARE",
  "departureTime": "now"
}
```

### Key response fields to extract

| Field | Maps to | Description |
|---|---|---|
| `duration` | used to derive `delay_seconds` | Live traffic travel time (seconds) |
| `staticDuration` | used to derive `congestion_ratio` | Historical baseline travel time |
| `distanceMeters` | used to derive `estimated_speed_kmh` | Segment length |
| `condition` | `google_status` | ROUTE_EXISTS / NO_ROUTE_FOUND etc. |

**Do not store `duration` or `staticDuration` raw values.** Per Google Maps Terms of Service, raw API response values cannot be stored or used to build datasets. Extract and store only derived calculations:
- `congestion_ratio` = `duration` / `staticDuration`
- `congestion_level` = threshold classification (see schema)
- `delay_seconds` = `duration` - `staticDuration`
- `estimated_speed_kmh` = `distanceMeters` / `duration` × 3.6

Raw values must be used transiently in-pipeline and immediately discarded.

### Routing preference

Always use `"routingPreference": "TRAFFIC_AWARE"` — this is what gives us live traffic data. Do **not** use `TRAFFIC_UNAWARE` or `TRAFFIC_AWARE_OPTIMAL` (the latter is slower and overkill for polling).

---

## Pricing — Critical Context

The Google Maps pricing model changed on **March 1, 2025**. The old $200/month credit is gone.

### New pricing structure

| SKU tier | Free cap/month | Triggered by |
|---|---|---|
| Essentials | 10,000 events | Basic routing, no traffic |
| **Pro** | **5,000 events** | **`TRAFFIC_AWARE` or `TRAFFIC_AWARE_OPTIMAL`** |
| Enterprise | 1,000 events | Two-wheel routing, enterprise features |

### Our usage

```
32 segments × 96 runs/day × 30 days = 92,160 requests/month
```

We need `TRAFFIC_AWARE` → **Pro SKU** → 5,000 free events/month.
Billable requests: 92,160 − 5,000 = **87,160/month**.

The $275/month Essentials subscription does **not** cover Routes Pro. Only the $1,200/month Pro subscription includes it. Pay-as-you-go is the right approach for PoC. Monitor costs and apply for Google for Startups credits when appropriate.

---

## Three-Step Migration Plan

### Step 1 — Migrate `data_pipeline.py` from Distance Matrix to Routes API `computeRouteMatrix`

Replace all Distance Matrix API calls with `computeRouteMatrix`. Same functional output — live traffic travel time per segment — but future-proof. Use `TRAFFIC_AWARE` + `departureTime: now`.

### Step 2 — Add `via:` waypoints for short/problematic segments

For any segment under ~1.5km, or any segment where coordinates are at chowrangis with side-street alternatives, add one mid-road coordinate as a `via:` pass-through waypoint.

After migration, flag any segment where `congestion_ratio` returns implausibly low during peak hours — this is the signal that Google is routing via a side street and a waypoint is needed.

### Step 3 — `speedReadingIntervals` for dashboard (runtime only, not pipeline)

At dashboard load time (not in the pipeline), fetch encoded polylines with `speedReadingIntervals` for sub-segment traffic colouring. **Do not store this data** — display-only at runtime.

---

## Data Storage Rules (Google Maps ToS — Non-Negotiable)

- **NEVER store** `duration`, `staticDuration`, `distanceMeters` or any raw API response value in Supabase
- **ALWAYS store** only derived calculations: `congestion_ratio`, `congestion_level`, `delay_seconds`, `estimated_speed_kmh`
- Raw values exist only as local variables within the pipeline function scope — discard immediately after calculation

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI (Replit) |
| Data source | Google Routes API (`computeRouteMatrix`) — **not Distance Matrix** |
| Database | Supabase (PostgreSQL) |
| ML models | XGBoost (15min–6hr), Prophet (24–48hr) |
| LLM layer | Claude API (Anthropic) — plain-English government briefings |
| Frontend | React + Vite + Leaflet + Recharts + Tailwind |
| Task tracking | Beads (`bd`) — `.beads/` committed to git |

---

## Replit Secrets Required

| Secret | Purpose |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Routes API (same key, different endpoint) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (bypasses RLS) |
| `ANTHROPIC_API_KEY` | Claude API for LLM briefing layer |
| `NOTION_TOKEN` | Notion MCP integration |

---

## Session Workflow

1. Run `bd ready` — get the highest-priority unblocked task
2. Check this CLAUDE.md for any constraints relevant to that task
3. Execute the task
4. Run `bd close <task-id>` before ending the session
5. Commit `.beads/` changes to git

---

*Hero's Initiative | Confidential | v1.4 | April 2026*
*Founder: Muhammad Mir | Built with Claude (Anthropic)*
