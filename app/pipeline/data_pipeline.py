"""
Hero's Initiative — Data Pipeline v2.1
=======================================
Collects derived traffic metrics from Google Maps Distance Matrix API
for 10 Karachi road segments every 15 minutes.

IMPORTANT — Google Maps ToS Compliance:
Raw API values (duration_normal_secs, duration_in_traffic_secs) are used
transiently to calculate derived metrics and then immediately discarded.
Only derived calculations are written to Supabase.

v2.1 changes:
- Captures inserted row IDs from Supabase response
- Calls XGBoost inference after each pipeline run (if model is trained)
- Calls accuracy backfill after inference
"""

import os
import httpx
import asyncio
from datetime import datetime, timezone
from supabase import create_client, Client

# ── Environment ────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Road segments — static reference data ─────────────────────────────────────

# distance_meters is our own reference data, NOT from the Google API
ROAD_SEGMENTS = {
    "road_01": {
        "name": "Shahrae Faisal",
        "origin": "24.9008,67.1681",
        "destination": "24.8710,67.0822",
        "distance_meters": 12000,
    },
    "road_02": {
        "name": "MA Jinnah Road",
        "origin": "24.8592,67.0104",
        "destination": "24.8607,67.0313",
        "distance_meters": 3500,
    },
    "road_03": {
        "name": "University Road",
        "origin": "24.9312,67.1100",
        "destination": "24.9268,67.0791",
        "distance_meters": 6000,
    },
    "road_04": {
        "name": "Korangi Road",
        "origin": "24.8350,67.1300",
        "destination": "24.8450,67.1650",
        "distance_meters": 6000,
    },
    "road_05": {
        "name": "Northern Bypass",
        "origin": "25.0600,67.1800",
        "destination": "24.9900,67.2300",
        "distance_meters": 15000,
    },
    "road_06": {
        "name": "Lyari Expressway",
        "origin": "24.8800,67.0200",
        "destination": "24.8350,66.9900",
        "distance_meters": 10000,
    },
    "road_07": {
        "name": "Rashid Minhas Road",
        "origin": "24.9200,67.0900",
        "destination": "24.8950,67.0700",
        "distance_meters": 4500,
    },
    "road_08": {
        "name": "Clifton Bridge",
        "origin": "24.8050,67.0250",
        "destination": "24.8120,67.0350",
        "distance_meters": 4000,
    },
    "road_09": {
        "name": "Superhighway",
        "origin": "25.1200,67.2800",
        "destination": "24.9800,67.2100",
        "distance_meters": 20000,
    },
    "road_10": {
        "name": "Hub River Road",
        "origin": "24.8900,66.9800",
        "destination": "24.8700,66.9200",
        "distance_meters": 11000,
    },
}

# ── Calendar context ───────────────────────────────────────────────────────────

RAMADAN_PERIODS = [
    ("2024-03-11", "2024-04-09"),
    ("2025-03-01", "2025-03-30"),
    ("2026-02-18", "2026-03-19"),
]

EID_PERIODS = [
    ("2024-04-10", "2024-04-13"),
    ("2024-06-17", "2024-06-20"),
    ("2025-03-31", "2025-04-03"),
    ("2025-06-07", "2025-06-10"),
    ("2026-03-20", "2026-03-23"),
]


def is_ramadan(dt: datetime) -> bool:
    d = dt.strftime("%Y-%m-%d")
    return any(s <= d <= e for s, e in RAMADAN_PERIODS)


def is_eid(dt: datetime) -> bool:
    d = dt.strftime("%Y-%m-%d")
    return any(s <= d <= e for s, e in EID_PERIODS)


def is_monsoon(dt: datetime) -> bool:
    return dt.month in [7, 8, 9]


def classify_congestion(ratio: float) -> str:
    """Classify congestion ratio into Hero's Initiative levels."""
    if ratio < 1.10:
        return "free_flow"
    elif ratio < 1.30:
        return "light"
    elif ratio < 1.60:
        return "moderate"
    else:
        return "heavy"


# ── Core pipeline function ─────────────────────────────────────────────────────


async def fetch_road_metrics(road_id: str, segment: dict) -> dict | None:
    """
    Call Google Maps Distance Matrix API for one road segment.

    Raw values from the API response (duration_normal_secs,
    duration_in_traffic_secs) are used ONLY to compute derived metrics
    and are then discarded — never written to Supabase.
    """
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": segment["origin"],
        "destinations": segment["destination"],
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if data.get("status") != "OK":
            print(f"  [{road_id}] API error: {data.get('status')}")
            return None

        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            print(f"  [{road_id}] Element error: {element.get('status')}")
            return None

        # ── TRANSIENT: raw API values — used for calculation only, never stored ──
        duration_normal_secs = element["duration"]["value"]
        duration_in_traffic_secs = element["duration_in_traffic"]["value"]
        distance_meters = segment["distance_meters"]  # our static reference

        # ── DERIVED: our calculations — these are what get stored ──────────────
        congestion_ratio = round(duration_in_traffic_secs / duration_normal_secs, 3)
        congestion_level = classify_congestion(congestion_ratio)
        delay_seconds = max(0, duration_in_traffic_secs - duration_normal_secs)
        estimated_speed_kmh = (
            round((distance_meters / duration_in_traffic_secs) * 3.6, 1)
            if duration_in_traffic_secs > 0
            else 0.0
        )

        # ── CONTEXT: enrichment flags — our derivations ─────────────────────────
        now = datetime.now(timezone.utc)
        hour_of_day = now.hour
        day_of_week = now.weekday()
        is_weekend = day_of_week >= 5

        record = {
            "road_id": road_id,
            "timestamp": now.isoformat(),
            # Derived metrics — our calculations, legally ours
            "congestion_ratio": congestion_ratio,
            "congestion_level": congestion_level,
            "delay_seconds": delay_seconds,
            "estimated_speed_kmh": estimated_speed_kmh,
            "distance_meters": distance_meters,  # static reference
            # Time features
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            # Context enrichment
            "is_ramadan": is_ramadan(now),
            "is_eid": is_eid(now),
            "is_monsoon": is_monsoon(now),
            # Source
            "data_source": "google_maps",
        }

        return record

    except Exception as e:
        print(f"  [{road_id}] Exception: {e}")
        return None


# ── ML Inference (non-fatal) ───────────────────────────────────────────────────


def _run_inference(inserted_rows: list[dict]) -> None:
    """
    Run XGBoost inference for each successfully inserted road reading.
    Silently skips if the model hasn't been trained yet.
    Errors here are logged but never crash the pipeline.
    """
    try:
        from app.ml.model_service import (
            build_feature_dict,
            predict_road,
            model_is_trained,
            backfill_accuracy,
        )

        if not model_is_trained():
            print(
                "  [ML] Model not yet trained — skipping inference. POST /api/v1/models/train to train."
            )
            return

        for row in inserted_rows:
            road_id = row["road_id"]
            reading_id = row["id"]

            # Fetch last 97 readings for lag features (97 = 96 prior + skip current)
            history = (
                supabase.table("traffic_readings")
                .select("congestion_ratio")
                .eq("road_id", road_id)
                .order("timestamp", desc=True)
                .limit(97)
                .execute()
            )
            # Reverse to oldest-first; skip index 0 which is the just-inserted row
            history_list = list(reversed(history.data[1:]))

            features = build_feature_dict(row, history_list)
            predict_road(road_id, reading_id, features)

        # Backfill accuracy for any predictions whose horizon has now elapsed
        updated = backfill_accuracy()
        if updated:
            print(f"  [ML] Backfilled {updated} prediction rows")

    except Exception as e:
        print(f"  [ML] Inference error (non-fatal): {e}")


# ── Main pipeline ──────────────────────────────────────────────────────────────


async def run_pipeline() -> int:
    """
    Collect derived traffic metrics for all 10 Karachi road segments.
    Called every 15 minutes by the FastAPI lifespan scheduler.
    Returns number of roads successfully collected.
    """
    now = datetime.now(timezone.utc)
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')} UTC] Pipeline run starting...")

    # Fetch all roads concurrently
    tasks = [fetch_road_metrics(rid, seg) for rid, seg in ROAD_SEGMENTS.items()]
    results = await asyncio.gather(*tasks)

    records = [r for r in results if r is not None]
    failed = len(ROAD_SEGMENTS) - len(records)

    if records:
        # Insert and capture returned rows (includes generated UUIDs for inference)
        insert_result = supabase.table("traffic_readings").insert(records).execute()
        inserted_rows = insert_result.data

        print(f"  ✅ Inserted {len(records)}/10 roads | Failed: {failed}")
        for r in records:
            print(
                f"  {r['road_id']} ({ROAD_SEGMENTS[r['road_id']]['name']}): "
                f"ratio={r['congestion_ratio']} ({r['congestion_level']}) | "
                f"delay={r['delay_seconds']}s | "
                f"speed={r['estimated_speed_kmh']}kmh"
            )

        # Run ML inference against the just-inserted rows
        _run_inference(inserted_rows)

    else:
        print("  ❌ No records inserted — all roads failed")

    return len(records)


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    count = asyncio.run(run_pipeline())
    print(f"\nPipeline complete: {count} roads collected")
