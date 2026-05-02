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

As of March 1, 2025, the Routes API fully replaces both the Directions API and the Distance Matrix API. The Distance Matrix API is legacy. All new pipeline work must use the Routes API.

### Why we are migrating

1. **Distance Matrix is legacy** — building further on it is technical debt from day one.
2. **Route accuracy problem** — on short segments (under ~1.5km), Distance Matrix sometimes routes through side streets rather than the target road. For example, between Disco Bakery and Gulshan Chowrangi there are 8–10 side streets Google could pick. This makes the congestion reading meaningless. The Routes API solves this with `via:` pass-through waypoints.
3. **Better data** — Routes API returns `speedReadingIntervals`, `staticDuration`, and heading support — none available in Distance Matrix.

---

## Routes API — Implementation Spec

### Endpoint

```
POST https://routes.googleapis.com/directions/v2:computeRouteMatrix
```

### Required headers

```
X-Goog-Api-Key: {GOOGLE_MAPS_API_KEY}
X-Goog-FieldMask: originIndex,destinationIndex,duration,distanceMeters,status,condition,travelAdvisory
```

### Request body

```json
{
  "origins": [
    { "waypoint": { "location": { "latLng": { "latitude": 24.9291, "longitude": 67.0975 } } } }
  ],
  "destinations": [
    { "waypoint": { "location": { "latLng": { "latitude": 24.9246, "longitude": 67.0916 } } } }
  ],
  "travelMode": "DRIVE",
  "routingPreference": "TRAFFIC_AWARE",
  "departureTime": "now"
}
```

Always use `TRAFFIC_AWARE`. Never use `TRAFFIC_UNAWARE` or `TRAFFIC_AWARE_OPTIMAL`.

### Via: waypoints for short segments

For any segment under ~1.5km, add one mid-road coordinate as a `via:` pass-through waypoint to force Google onto the correct road. The following segments require waypoints:

- `road_05a` — Disco Bakery → Gulshan Chowrangi (800m)
- `road_05b` — Nipa Chowrangi → Gulshan Chowrangi (900m)
- `road_05c` — Maskan Chowrangi → Disco Bakery (1,000m)
- `road_06a` — Gulshan Chowrangi → Nipa Chowrangi (900m)
- `road_06c` — Johar Mor → Askari 4 (500m)

---

## Derived Metrics — Business Logic

**Google Maps ToS is non-negotiable: never store raw API response values in Supabase.**
Raw values (`duration`, `staticDuration`, `distanceMeters`) are transient local variables only — compute derived metrics from them immediately and discard.

| Metric | Formula | Unit | Stored |
|---|---|---|---|
| `congestion_ratio` | `duration / staticDuration` | ratio | ✅ Yes |
| `congestion_level` | threshold on `congestion_ratio` | enum | ✅ Yes |
| `delay_seconds` | `duration - staticDuration` | seconds | ✅ Yes |
| `estimated_speed_kmh` | `(distanceMeters / duration) × 3.6` | km/h | ✅ Yes |
| `duration` (raw) | — | seconds | ❌ Never |
| `staticDuration` (raw) | — | seconds | ❌ Never |
| `distanceMeters` (raw) | — | metres | ❌ Never |

### Congestion level thresholds

| Level | Ratio range | Meaning |
|---|---|---|
| `free_flow` | < 1.10 | At or near baseline speed |
| `light` | 1.10 – 1.30 | Up to 30% slower than normal |
| `moderate` | 1.30 – 1.60 | 30–60% slower than normal |
| `heavy` | > 1.60 | More than 60% slower than normal |

---

## Finalised PoC Segment List — 16 Forward Segments

**Decision:** Reverse segments dropped for PoC. Forward direction captures peak commuter flow and is sufficient to demonstrate actionable government intelligence. Reverse segments added back in Phase 2.

**Pipeline frequency:** Every 15 minutes (96 runs/day).
**Monthly API cost:** ~$206/month (~£163) — Routes API Pro SKU, pay-as-you-go.
**Monthly API calls:** 16 segments × 96 runs/day × 30 days = 46,080 requests/month.

### Shahrae Faisal — 6 segments

| road_id | Segment | Origin lat,lng | Destination lat,lng | Distance | Road type |
|---|---|---|---|---|---|
| road_01a | Airport → Drigh Road | 24.900800, 67.168100 | 24.887019, 67.125427 | 5,800m | arterial |
| road_01b | Drigh Road → Karsaz | 24.887019, 67.125427 | 24.874779, 67.095790 | 3,400m | arterial |
| road_01c | Karsaz → Shaheed-e-Millat Bridge | 24.874779, 67.095790 | 24.867330, 67.083804 | 1,500m | arterial |
| road_01d | Shaheed-e-Millat Bridge → City School PAF | 24.867330, 67.083804 | 24.861271, 67.088200 | 850m | arterial |
| road_01e | City School PAF → Manzoor Colony Parallel Rd | 24.861271, 67.088200 | 24.845614, 67.087526 | 1,800m | arterial |
| road_01f | Shahrah-e-Qaideen Flyover → Metropole | 24.859755, 67.059040 | 24.849675, 67.030451 | 3,300m | arterial |

Peak hours: 08:00–10:00, 17:00–20:00

### Shaheed-e-Millat Rd — 2 segments

| road_id | Segment | Origin lat,lng | Destination lat,lng | Distance | Road type |
|---|---|---|---|---|---|
| road_02a | Defence/Korangi → Manzoor Colony | 24.831287, 67.079822 | 24.852834, 67.089831 | 2,700m | expressway |
| road_02b | Manzoor Colony → Shaheed-e-Millat Bridge | 24.852834, 67.089831 | 24.866864, 67.083022 | 1,800m | expressway |

Peak hours: 08:00–10:00, 17:00–20:00

### Khayaban-e-Iqbal (Clifton) — 2 segments

| road_id | Segment | Origin lat,lng | Destination lat,lng | Distance | Road type |
|---|---|---|---|---|---|
| road_04a | Metropole → Teen Talwar | 24.849675, 67.030451 | 24.833776, 67.033724 | 1,800m | arterial |
| road_04b | Teen Talwar → Do Talwar | 24.833776, 67.033724 | 24.821175, 67.034203 | 1,500m | arterial |

Peak hours: 07:30–09:30, 17:00–21:00

### Allama Shabbir Ahmed Usmani Rd (University Road corridor) — 3 segments

| road_id | Segment | Origin lat,lng | Destination lat,lng | Distance | Road type | Waypoint needed |
|---|---|---|---|---|---|---|
| road_05a | Disco Bakery → Gulshan Chowrangi | 24.929126, 67.097527 | 24.924578, 67.091605 | 800m | arterial | ✅ Yes |
| road_05b | Nipa Chowrangi → Gulshan Chowrangi | 24.917845, 67.097369 | 24.924578, 67.091605 | 900m | arterial | ✅ Yes |
| road_05c | Maskan Chowrangi → Disco Bakery | 24.935079, 67.105263 | 24.929126, 67.097527 | 1,000m | arterial | ✅ Yes |

Peak hours: 07:30–09:30, 17:00–21:00

### Rashid Minhas Road — 4 segments (road_06a–road_06d)

| road_id | Segment | Origin lat,lng | Destination lat,lng | Distance | Road type | Waypoint needed |
|---|---|---|---|---|---|---|
| road_06a | Gulshan Chowrangi → Nipa Chowrangi | 24.924578, 67.091605 | 24.917845, 67.097369 | 900m | arterial | ✅ Yes |
| road_06b | Nipa Chowrangi → Johar Mor | 24.917845, 67.097369 | 24.903882, 67.114075 | 2,200m | arterial | No |
| road_06c | Johar Mor → Askari 4 | 24.903882, 67.114075 | 24.900911, 67.116371 | 500m | arterial | ✅ Yes |
| road_06d | Askari 4 → Drigh Road | 24.900911, 67.116371 | 24.887019, 67.125427 | 1,500m | arterial | No |

Peak hours: 07:30–09:30, 17:00–21:00

---

## Pipeline — ROAD_SEGMENTS Dict (Python)

This is the authoritative segment definition to use in `data_pipeline.py`:

```python
ROAD_SEGMENTS = {
    # ── SHAHRAE FAISAL — 6 segments ─────────────────────────────────────────
    "road_01a": {
        "name": "Shahrae Faisal",
        "segment": "Airport to Drigh Road",
        "origin": "24.900800,67.168100",
        "destination": "24.887019,67.125427",
        "distance_meters": 5800,
        "via": None,
    },
    "road_01b": {
        "name": "Shahrae Faisal",
        "segment": "Drigh Road to Karsaz",
        "origin": "24.887019,67.125427",
        "destination": "24.874779,67.095790",
        "distance_meters": 3400,
        "via": None,
    },
    "road_01c": {
        "name": "Shahrae Faisal",
        "segment": "Karsaz to Shaheed-e-Millat Bridge",
        "origin": "24.874779,67.095790",
        "destination": "24.867330,67.083804",
        "distance_meters": 1500,
        "via": None,
    },
    "road_01d": {
        "name": "Shaheed-e-Millat Rd",
        "segment": "Shaheed-e-Millat Bridge to City School PAF",
        "origin": "24.867330,67.083804",
        "destination": "24.861271,67.088200",
        "distance_meters": 850,
        "via": None,
    },
    "road_01e": {
        "name": "Shaheed-e-Millat Rd",
        "segment": "City School PAF to Manzoor Colony Parallel Rd",
        "origin": "24.861271,67.088200",
        "destination": "24.845614,67.087526",
        "distance_meters": 1800,
        "via": None,
    },
    "road_01f": {
        "name": "Shahrae Faisal",
        "segment": "Shahrah-e-Qaideen Flyover to Metropole",
        "origin": "24.859755,67.059040",
        "destination": "24.849675,67.030451",
        "distance_meters": 3300,
        "via": None,
    },
    # ── SHAHEED-E-MILLAT RD — 2 segments ────────────────────────────────────
    "road_02a": {
        "name": "Shaheed-e-Millat Rd",
        "segment": "Defence/Korangi to Manzoor Colony",
        "origin": "24.831287,67.079822",
        "destination": "24.852834,67.089831",
        "distance_meters": 2700,
        "via": None,
    },
    "road_02b": {
        "name": "Shaheed-e-Millat Rd",
        "segment": "Manzoor Colony to Shaheed-e-Millat Bridge",
        "origin": "24.852834,67.089831",
        "destination": "24.866864,67.083022",
        "distance_meters": 1800,
        "via": None,
    },
    # ── KHAYABAN-E-IQBAL (CLIFTON) — 2 segments ─────────────────────────────
    "road_04a": {
        "name": "Khayaban-e-Iqbal",
        "segment": "Metropole to Teen Talwar",
        "origin": "24.849675,67.030451",
        "destination": "24.833776,67.033724",
        "distance_meters": 1800,
        "via": None,
    },
    "road_04b": {
        "name": "Khayaban-e-Iqbal",
        "segment": "Teen Talwar to Do Talwar",
        "origin": "24.833776,67.033724",
        "destination": "24.821175,67.034203",
        "distance_meters": 1500,
        "via": None,
    },
    # ── ALLAMA SHABBIR AHMED USMANI RD — 3 segments ─────────────────────────
    "road_05a": {
        "name": "Allama Shabbir Ahmed Usmani Rd",
        "segment": "Disco Bakery to Gulshan Chowrangi",
        "origin": "24.929126,67.097527",
        "destination": "24.924578,67.091605",
        "distance_meters": 800,
        "via": "24.926800,67.094500",  # mid-road waypoint
    },
    "road_05b": {
        "name": "Rashid Minhas Road",
        "segment": "Nipa Chowrangi to Gulshan Chowrangi",
        "origin": "24.917845,67.097369",
        "destination": "24.924578,67.091605",
        "distance_meters": 900,
        "via": "24.921200,67.094400",  # mid-road waypoint
    },
    "road_05c": {
        "name": "Allama Shabbir Ahmed Usmani Rd",
        "segment": "Maskan Chowrangi to Disco Bakery",
        "origin": "24.935079,67.105263",
        "destination": "24.929126,67.097527",
        "distance_meters": 1000,
        "via": "24.932000,67.101400",  # mid-road waypoint
    },
    # ── RASHID MINHAS ROAD — 4 segments ─────────────────────────────────────
    "road_06a": {
        "name": "Rashid Minhas Road",
        "segment": "Gulshan Chowrangi to Nipa Chowrangi",
        "origin": "24.924578,67.091605",
        "destination": "24.917845,67.097369",
        "distance_meters": 900,
        "via": "24.921200,67.094400",  # mid-road waypoint
    },
    "road_06b": {
        "name": "Rashid Minhas Road",
        "segment": "Nipa Chowrangi to Johar Mor",
        "origin": "24.917845,67.097369",
        "destination": "24.903882,67.114075",
        "distance_meters": 2200,
        "via": None,
    },
    "road_06c": {
        "name": "Rashid Minhas Road",
        "segment": "Johar Mor to Askari 4",
        "origin": "24.903882,67.114075",
        "destination": "24.900911,67.116371",
        "distance_meters": 500,
        "via": "24.902400,67.115200",  # mid-road waypoint
    },
    "road_06d": {
        "name": "Rashid Minhas Road",
        "segment": "Askari 4 to Drigh Road",
        "origin": "24.900911,67.116371",
        "destination": "24.887019,67.125427",
        "distance_meters": 1500,
        "via": None,
    },
}
```

---

## Pricing — Critical Context

Google Maps pricing changed **March 1, 2025**. The old $200/month credit is gone.

| SKU tier | Free cap/month | Triggered by |
|---|---|---|
| Essentials | 10,000 events | Basic routing, no traffic |
| **Pro** | **5,000 events** | **`TRAFFIC_AWARE` or `TRAFFIC_AWARE_OPTIMAL`** |

We need `TRAFFIC_AWARE` → **Pro SKU**.

```
16 segments × 96 runs/day × 30 days = 46,080 requests/month
46,080 − 5,000 free = 41,080 billable requests/month
Estimated cost: ~$206/month (~£163)
```

The $275/month Essentials subscription does **not** cover Routes Pro. Pay-as-you-go is correct for PoC. Apply for Google for Startups credits when approaching government presentation.

### Polylines (dashboard only)

Polylines are fetched at **runtime when the dashboard loads** using `computeRoutes` — not in the pipeline. 16 requests per page load, ~$0.03 per load. Never stored. Negligible cost.

---

## Three-Step Migration Plan

1. **Migrate `data_pipeline.py`** — replace all Distance Matrix calls with `computeRouteMatrix`. Use `TRAFFIC_AWARE` + `departureTime: now`. Use the `ROAD_SEGMENTS` dict above as the authoritative source.

2. **Add `via:` waypoints** — segments marked `"via": "lat,lng"` in the dict must include that coordinate as a pass-through waypoint in the request body. After migration, flag any segment returning implausibly low `congestion_ratio` during peak hours — that is the signal of side-street routing.

3. **`speedReadingIntervals` for dashboard** — runtime only, never pipeline, never stored.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI (Replit) |
| Data source | Google Routes API `computeRouteMatrix` — **not Distance Matrix** |
| Database | Supabase (PostgreSQL) |
| ML models | XGBoost (15min–6hr), Prophet (24–48hr) |
| LLM layer | Claude API (Anthropic) — plain-English government briefings |
| Frontend | React + Vite + Leaflet + Recharts + Tailwind |
| Task tracking | Beads (`bd`) — `.beads/` committed to git |

---

## Replit Secrets Required

| Secret | Purpose |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Routes API (same key, new endpoint) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (bypasses RLS) |
| `ANTHROPIC_API_KEY` | Claude API for LLM briefing layer |
| `NOTION_TOKEN` | Notion MCP integration |

---

## Session Workflow

1. Run `bd ready` — get the highest-priority unblocked task
2. Check this CLAUDE.md for constraints relevant to that task
3. Execute the task
4. Run `bd close <task-id>` before ending the session
5. Commit `.beads/` changes to git

---

*Hero's Initiative | Confidential | v1.4 | April 2026*
*Founder: Muhammad Mir | Built with Claude (Anthropic)*
