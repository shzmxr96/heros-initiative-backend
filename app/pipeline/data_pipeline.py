"""
Hero's Initiative — Data Pipeline v2.2
=======================================
Collects derived traffic metrics from Google Routes API (computeRouteMatrix)
for 10 Karachi road segments every 15 minutes.

IMPORTANT — Google Maps ToS Compliance:
Raw API values (duration, staticDuration) are used transiently to calculate
derived metrics and then immediately discarded. Only derived calculations
are written to Supabase.

v2.2 changes:
- Migrated from legacy Distance Matrix API to Routes API (computeRouteMatrix)
- Uses TRAFFIC_AWARE routing preference for live traffic data
- Supports optional via: waypoints per segment for route accuracy
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

# distance_meters is our own reference data, NOT from the Google API.
# via: mid-road pass-through waypoint for short segments to prevent side-street routing.
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
        "origin": "24.886820,67.124261",
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
        "origin": "24.861232,67.088067",
        "destination": "24.845614,67.087526",
        "distance_meters": 1800,
        "via": None,
    },
    "road_01f": {
        "name": "Shahrae Faisal",
        "segment": "Shahrah-e-Qaideen Flyover to Metropole",
        "origin": "24.859613,67.058741",
        "destination": "24.849675,67.030451",
        "distance_meters": 3300,
        "via": None,
    },
    # ── SHAHEED-E-MILLAT RD — 2 segments ────────────────────────────────────
    "road_02a": {
        "name": "Shaheed-e-Millat Rd",
        "segment": "Defence/Korangi to Manzoor Colony",
        "origin": "24.830991,67.079535",
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
        "origin": "24.849679,67.030558",
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
        "origin": "24.928994,67.097579",
        "destination": "24.924415,67.091974",
        "distance_meters": 800,
        "via": "24.927191,67.095309",
    },
    "road_05b": {
        "name": "Rashid Minhas Road",
        "segment": "Nipa Chowrangi to Gulshan Chowrangi",
        "origin": "24.917749,67.096957",
        "destination": "24.924293,67.091536",
        "distance_meters": 900,
        "via": "24.921200,67.094400",
    },
    "road_05c": {
        "name": "Allama Shabbir Ahmed Usmani Rd",
        "segment": "Maskan Chowrangi to Disco Bakery",
        "origin": "24.935079,67.105263",
        "destination": "24.929126,67.097527",
        "distance_meters": 1000,
        "via": "24.932000,67.101400",
    },
    # ── RASHID MINHAS ROAD — 4 segments ─────────────────────────────────────
    "road_06a": {
        "name": "Rashid Minhas Road",
        "segment": "Gulshan Chowrangi to Nipa Chowrangi",
        "origin": "24.924578,67.091605",
        "destination": "24.917845,67.097369",
        "distance_meters": 900,
        "via": "24.921200,67.094400",
    },
    "road_06b": {
        "name": "Rashid Minhas Road",
        "segment": "Nipa Chowrangi to Johar Mor",
        "origin": "24.917845,67.097369",
        "destination": "24.903882,67.114075",
        "distance_meters": 2300,
        "via": None,
    },
    "road_06c": {
        "name": "Rashid Minhas Road",
        "segment": "Johar Mor to Askari 4",
        "origin": "24.903882,67.114075",
        "destination": "24.900911,67.116371",
        "distance_meters": 500,
        "via": "24.902139,67.115517",
    },
    "road_06d": {
        "name": "Rashid Minhas Road",
        "segment": "Askari 4 to Drigh Road",
        "origin": "24.900911,67.116371",
        "destination": "24.886764,67.124087",
        "distance_meters": 1900,
        "via": None,
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


def _parse_latlng(coord_str: str) -> dict:
    lat, lng = coord_str.split(",")
    return {"latitude": float(lat), "longitude": float(lng)}


async def _fetch_via_route(road_id: str, segment: dict, client: httpx.AsyncClient) -> tuple[int, int] | None:
    """
    Use computeRoutes (single route) for segments that need a via: waypoint.
    computeRouteMatrix does not support intermediates.
    Returns (duration_in_traffic_secs, duration_normal_secs) or None on error.
    """
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration",
    }
    body = {
        "origin": {"location": {"latLng": _parse_latlng(segment["origin"])}},
        "destination": {"location": {"latLng": _parse_latlng(segment["destination"])}},
        "intermediates": [{"via": True, "location": {"latLng": _parse_latlng(segment["via"])}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    resp = await client.post(url, headers=headers, json=body)
    data = resp.json()
    routes = data.get("routes", [])
    if not routes:
        print(f"  [{road_id}] computeRoutes error: {data}")
        return None
    route = routes[0]
    duration_secs = int(route.get("duration", "0s").rstrip("s"))
    static_secs = int(route.get("staticDuration", "0s").rstrip("s"))
    return duration_secs, static_secs


async def _fetch_matrix_route(road_id: str, segment: dict, client: httpx.AsyncClient) -> tuple[int, int] | None:
    """
    Use computeRouteMatrix for standard segments (no via: waypoint needed).
    Returns (duration_in_traffic_secs, duration_normal_secs) or None on error.
    """
    url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
    headers = {
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "originIndex,destinationIndex,duration,staticDuration,status,condition",
    }
    body = {
        "origins": [{"waypoint": {"location": {"latLng": _parse_latlng(segment["origin"])}}}],
        "destinations": [{"waypoint": {"location": {"latLng": _parse_latlng(segment["destination"])}}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    resp = await client.post(url, headers=headers, json=body)
    data = resp.json()
    if not isinstance(data, list) or not data:
        print(f"  [{road_id}] computeRouteMatrix error: {data}")
        return None
    element = data[0]
    if element.get("condition") == "ROUTE_NOT_FOUND" or element.get("status", {}).get("code", 0) != 0:
        print(f"  [{road_id}] Route error: {element.get('condition')} / {element.get('status')}")
        return None
    duration_secs = int(element.get("duration", "0s").rstrip("s"))
    static_secs = int(element.get("staticDuration", "0s").rstrip("s"))
    return duration_secs, static_secs


async def fetch_road_metrics(road_id: str, segment: dict) -> dict | None:
    """
    Fetch live traffic for one road segment via Google Routes API.
    Segments with a via: waypoint use computeRoutes; all others use computeRouteMatrix.

    Raw values from the API (duration, staticDuration) are used transiently
    to compute derived metrics and then discarded — never written to Supabase.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if segment.get("via"):
                result = await _fetch_via_route(road_id, segment, client)
            else:
                result = await _fetch_matrix_route(road_id, segment, client)

        if result is None:
            return None

        duration_in_traffic_secs, duration_normal_secs = result
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
