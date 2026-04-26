import os
from notion_client import Client

notion = Client(auth=os.environ.get("NOTION_TOKEN"))

PAGES = {
    "home":             "342e2687-b7f9-811c-8f4a-f00c27be806e",
    "data_strategy":    "342e2687-b7f9-81fb-8a55-e0d24434fa76",
    "technical_design": "342e2687-b7f9-81e5-80a8-ee046c23a189",
    "gap_analysis":     "342e2687-b7f9-81e0-b2f6-f57b77e616d6",
    "ml_models":        "342e2687-b7f9-8153-8dcb-fce1258df5f3",
}

def h2(text):
    return {"object":"block","type":"heading_2","heading_2":{"rich_text":[{"type":"text","text":{"content":text}}]}}

def h3(text):
    return {"object":"block","type":"heading_3","heading_3":{"rich_text":[{"type":"text","text":{"content":text}}]}}

def para(text):
    return {"object":"block","type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":text}}]}}

def bullet(text, bold=False):
    return {"object":"block","type":"bulleted_list_item","bulleted_list_item":{"rich_text":[{"type":"text","text":{"content":text},"annotations":{"bold":bold}}]}}

def callout(text, emoji="📌"):
    return {"object":"block","type":"callout","callout":{"rich_text":[{"type":"text","text":{"content":text}}],"icon":{"type":"emoji","emoji":emoji}}}

def divider():
    return {"object":"block","type":"divider","divider":{}}

def append(page_id, blocks):
    # Notion API max 100 blocks per request
    for i in range(0, len(blocks), 100):
        notion.blocks.children.append(page_id, children=blocks[i:i+100])
    print(f"  ✅ Added {len(blocks)} blocks")

# ── HOME PAGE ─────────────────────────────────────────────────
print("\n📄 Updating Home page...")
append(PAGES["home"], [
    divider(),
    h2("Project Status — April 2026"),
    callout("Phase 1 PoC in progress. Google Maps pipeline live and saving to Supabase every 15 minutes. Synthetic dataset (~350,000 rows) generated. ML model architecture decided. Government Intelligence Platform framing confirmed.", "🟢"),
    h2("Infrastructure Status"),
    bullet("Backend: FastAPI deployed at https://heros-initiative-backend.replit.app", True),
    bullet("Scheduler: asyncio lifespan — pipeline runs every 15 minutes automatically on server start"),
    bullet("Database: Supabase PostgreSQL — 4 tables live, 10 Karachi roads seeded, real data accumulating"),
    bullet("UptimeRobot: HTTP monitor pinging every 5 minutes — 100% uptime confirmed"),
    bullet("GitHub: heros-initiative-backend and heros-initiative-frontend repos under shzmxr96"),
    bullet("Cost: ~$25/month Replit Core + $0 Google Maps (within $200 free credit) + $0 Supabase"),
    h2("Product Reframing — Government Intelligence Tool"),
    callout("Hero's Initiative is NOT a consumer app competing with Google Maps. It is Pakistan's first Government Traffic Intelligence Platform — built for Karachi Traffic Police and Government of Sindh.", "🎯"),
    bullet("Capability 1: Predictive Congestion Forecasting — multi-horizon predictions (15min to 48hr)"),
    bullet("Capability 2: Root Cause Intelligence — why is this road congested right now?"),
    bullet("Capability 3: Infrastructure Investment Prioritisation — which roads need intervention most urgently?"),
    bullet("National Dataset: Hero's Initiative is building Pakistan's first ever structured road-level traffic dataset — critical national data infrastructure"),
])

# ── DATA STRATEGY ─────────────────────────────────────────────
print("\n📄 Updating Data Strategy & Decisions...")
append(PAGES["data_strategy"], [
    divider(),
    h2("Synthetic Data — Karachi-Specific Patterns Encoded"),
    para("24 months of synthetic data (April 2024 to April 2026) generated and loaded into Supabase (~350,000 rows). Tagged with data_source = synthetic. Real Google Maps data takes priority over synthetic for the same timestamps during ML training."),
    h3("Road Base Profiles"),
    bullet("road_01 Shahrae Faisal: weekday base 1.25, weekend evening 1.55 — main social corridor, airport + commercial"),
    bullet("road_02 MA Jinnah Road: weekday base 1.20, weekend evening 1.25 — Burns Road / Saddar food street evening boost"),
    bullet("road_03 University Road: weekday base 1.20 + Green Line addition, weekend evening 1.60 — triple peak school + social pattern"),
    bullet("road_04 Korangi Road: weekday base 1.15, weekend 1.00 — industrial corridor, quiet weekends"),
    bullet("road_05 Northern Bypass: base 1.05 — highway, unaffected by social patterns"),
    bullet("road_06 Lyari Expressway: base 1.10 — freight corridor, quiet weekends"),
    bullet("road_07 Rashid Minhas Road: weekday base 1.20, weekend evening 1.45 — Gulshan feeder, school + social peaks"),
    bullet("road_08 Clifton Bridge: weekday base 1.25, weekend evening 1.50 — bottleneck, major social destination"),
    bullet("road_09 Superhighway: base 1.05 — highway, unaffected by social patterns"),
    bullet("road_10 Hub River Road: base 1.10 — industrial, quiet weekends"),
    h3("University Road — Triple Peak Pattern (road_03)"),
    bullet("7:00-9:30am: 1.9x multiplier — school morning rush (parents dropping at Gulshan schools)"),
    bullet("1:00-3:30pm: 1.8x multiplier — school pickup rush"),
    bullet("7:00-11:00pm: 2.0x weekdays, 2.2x weekends — Gulshan social scene (restaurants, cafes, Dolmen Mall)"),
    bullet("Gulshan Chowrangi to Maskan Chowrangi confirmed as primary gridlock zone"),
    bullet("Busy year-round including Ramadan — worst post-Iftar (2.2x) and post-Tarawih (1.8x sporadic)"),
    h3("Green Line / Red Line BRT Construction — Progressive Worsening"),
    bullet("Apr-Jun 2024: +0.25 baseline addition — construction ramping up"),
    bullet("Jul-Dec 2024: +0.35 — progressively worse, IDEAS 2024 closure Nov 19-22"),
    bullet("Jan-Jun 2025: +0.45 — severe disruption, Feb 2025 full pipeline burst closure"),
    bullet("Jul-Nov 2025: +0.55 — near chaos, pedestrian bridges dismantled"),
    bullet("Nov 2025-Apr 2026: +0.65 — additional KWSSIP pipeline closure Nov 10-Dec 30 stacks on top"),
    bullet("Red Line BRT completion delayed beyond Dec 2026 — chaos continues throughout entire PoC period"),
    h3("Annual Events Encoded"),
    bullet("PSL match days Feb-May: road_03 and road_07 reach 2.0-2.2x on match evenings — severe gridlock"),
    bullet("IDEAS Defence Exhibition Nov 19-22 annually: University Road + Rashid Minhas reach 2.4x"),
    bullet("Karachi Eat Festival Jan-Feb weekends: road_08 Clifton + road_01 Shahrae Faisal reach 1.7x"),
    bullet("Wedding season Nov-Feb and May-Jun: Friday-Sunday evenings 1.4x on all social roads"),
    bullet("Ramadan: slow mornings (0.75x), post-Iftar spike (1.3-1.7x), post-Tarawih sporadic (1.2-1.6x)"),
    bullet("Eid: 0.4x days 1-2 (city near-empty), 1.5-1.6x surge from day 3 onwards"),
    bullet("Monsoon July-Sept: 30% rain probability per reading, 1.3-1.8x multiplier city-wide"),
    bullet("14 August: 0.5x morning (holiday), 1.8x evening (Independence Day celebrations)"),
    h3("Weekend Social Pattern — Karachi Nightlife"),
    bullet("Karachiites are very social — Friday-Sunday evenings are as busy as weekday rush hours on social roads"),
    bullet("Social roads: Shahrae Faisal, University Road (Gulshan), Rashid Minhas, Clifton Bridge"),
    bullet("Peak social hours: 7pm-12am Friday, Saturday, Sunday — 1.4-2.1x multipliers"),
    bullet("Burns Road (MA Jinnah Road) elevated year-round evenings — food street destination"),
    bullet("Industrial roads (Korangi, Hub River, Lyari): significantly quieter on weekends"),
    h3("Training Data Strategy"),
    bullet("Real data: data_source = google_maps — accumulating at ~960 rows/day automatically"),
    bullet("Synthetic data: data_source = synthetic — ~350,000 rows covering Apr 2024 to Apr 2026"),
    bullet("Priority rule: for same road + same timestamp, real data takes priority over synthetic"),
    bullet("SQL for real-only: SELECT * FROM traffic_readings WHERE data_source = 'google_maps'"),
    bullet("SQL for combined: SELECT DISTINCT ON (road_id, date_trunc('hour', timestamp)) * FROM traffic_readings ORDER BY road_id, date_trunc('hour', timestamp), CASE WHEN data_source = 'google_maps' THEN 1 ELSE 2 END"),
])

# ── TECHNICAL DESIGN ──────────────────────────────────────────
print("\n📄 Updating Technical Design & Architecture...")
append(PAGES["technical_design"], [
    divider(),
    h2("Deployment & Infrastructure — Live Status"),
    callout("Backend is live and running 24/7 as of April 2026", "🟢"),
    bullet("Production URL: https://heros-initiative-backend.replit.app", True),
    bullet("Platform: Replit Core (~$25/month) — Autoscale deployment, 2 vCPU / 4GB RAM"),
    bullet("Scheduler: asyncio lifespan event in FastAPI startup — runs run_pipeline() every 15 minutes automatically"),
    bullet("UptimeRobot: HTTP(S) monitor pinging every 5 minutes — 100% uptime confirmed — prevents Replit sleep"),
    bullet("HEAD endpoint: @app.head('/') added to handle UptimeRobot HEAD requests without 405 errors"),
    bullet("Frontend: React + Vite at localhost:5173 — to be deployed separately once dashboard is built"),
    bullet("Database: Supabase project emuanrspalqyejhpbefh — Northeast Asia (Seoul)"),
    bullet("GitHub: heros-initiative-backend and heros-initiative-frontend under shzmxr96"),
    h2("Updated API Endpoints — Live"),
    bullet("GET / — returns API status + scheduler: active confirmation"),
    bullet("GET /health — returns { status: healthy, scheduler: active }"),
    bullet("HEAD / — returns 200 for UptimeRobot monitoring"),
    bullet("GET /api/v1/traffic — latest congestion for all 10 roads from Supabase latest_traffic view"),
    bullet("POST /api/v1/pipeline/run — manually trigger data collection for all 10 roads"),
    bullet("GET /api/v1/readings — recent traffic readings with optional road_id and limit filters"),
    bullet("GET /api/v1/accuracy — rolling 7-day prediction accuracy from prediction_accuracy view"),
    bullet("GET /api/v1/models — available ML models list"),
    bullet("GET /docs — Swagger interactive UI"),
    h2("Cost Breakdown — April 2026"),
    bullet("Replit Core: ~$25/month — Always On deployment, no sleep"),
    bullet("Google Maps API: ~$144/month cost, $200/month free credit = $0 net cost for 10 roads"),
    bullet("Supabase: $0 — free tier sufficient for 12+ months at current data volume"),
    bullet("UptimeRobot: $0 — free tier, 5-minute interval monitoring"),
    bullet("Total monthly cost: ~$25/month to run entire Hero's Initiative infrastructure"),
    bullet("Scale warning: expanding to 50 roads = ~$720/month Google Maps cost — needs budget or Google for Startups credits"),
])

# ── GAP ANALYSIS ──────────────────────────────────────────────
print("\n📄 Updating GAP Analysis...")
append(PAGES["gap_analysis"], [
    h2("GAP Analysis — Updated April 2026"),
    callout("Gaps resolved since original PRD v1.0", "✅"),
    bullet("Database persistence: RESOLVED — Supabase connected, all data writing to PostgreSQL permanently"),
    bullet("Pipeline reliability: RESOLVED — asyncio scheduler + UptimeRobot keep pipeline running 24/7"),
    bullet("TomTom coverage: RESOLVED — removed from pipeline, Google Maps confirmed as sole primary source"),
    bullet("Replit filesystem loss risk: RESOLVED — data writes to Supabase, not local files"),
    divider(),
    callout("Gaps remaining — open and tracked", "⚠️"),
    bullet("No real historical traffic data: MITIGATION — 24-month synthetic dataset loaded; real data accumulating at 960 rows/day; replace synthetic with real as it grows", True),
    bullet("Waze historical data locked: MITIGATION — post-PoC government partnership to unlock Waze for Cities; this is the Phase 2 data upgrade that transforms model accuracy", True),
    bullet("70% ML accuracy uncertain on synthetic data: MITIGATION — XGBoost with rich Karachi-specific features expected to hit 70%+ faster than LSTM; blending real + synthetic data as it accumulates", True),
    bullet("Frontend dashboard not yet connected to backend: MITIGATION — next sprint: connect React to /api/v1/traffic via axios; build government intelligence UI", True),
    bullet("was_correct backfill logic not built: MITIGATION — simple scheduled job querying predictions where actual_congestion_level IS NULL and timestamp has passed", True),
    bullet("No real incident data for root cause training: MITIGATION — event ingestion form in dashboard lets Traffic Police log incidents; crowdsourced ground truth grows over time", True),
    bullet("Google Maps cost at scale: MITIGATION — current 10 roads = $144/month within free credit; Phase 2 (50 roads) = ~$720/month — needs budget or Google for Startups credits", True),
    bullet("Root cause attribution without incident labels: MITIGATION — pattern deviation detection + known event calendar gives ~70% cause attribution without manual labels initially", True),
    bullet("Replit Core deployment may not support long-running scheduler reliably: MITIGATION — UptimeRobot as backup watchdog; Railway/Render as fallback if needed", True),
])

print("\n✅ All Notion pages updated successfully!")