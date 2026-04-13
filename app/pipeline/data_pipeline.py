import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

KARACHI_ROADS = [
    {
        "id": "road_01",
        "name": "Shahrae Faisal",
        "origin": "24.9008,67.1681",
        "destination": "24.8710,67.0822",
    },
    {
        "id": "road_02",
        "name": "MA Jinnah Road",
        "origin": "24.8592,67.0104",
        "destination": "24.8607,67.0313",
    },
    {
        "id": "road_03",
        "name": "University Road",
        "origin": "24.9312,67.1100",
        "destination": "24.9268,67.0791",
    },
    {
        "id": "road_04",
        "name": "Korangi Road",
        "origin": "24.8350,67.1300",
        "destination": "24.8450,67.1650",
    },
    {
        "id": "road_05",
        "name": "Northern Bypass",
        "origin": "25.0600,67.1800",
        "destination": "24.9900,67.2300",
    },
    {
        "id": "road_06",
        "name": "Lyari Expressway",
        "origin": "24.8800,67.0200",
        "destination": "24.8350,66.9900",
    },
    {
        "id": "road_07",
        "name": "Rashid Minhas Road",
        "origin": "24.9200,67.0900",
        "destination": "24.8950,67.0700",
    },
    {
        "id": "road_08",
        "name": "Clifton Bridge",
        "origin": "24.8050,67.0250",
        "destination": "24.8120,67.0350",
    },
    {
        "id": "road_09",
        "name": "Superhighway",
        "origin": "25.1200,67.2800",
        "destination": "24.9800,67.2100",
    },
    {
        "id": "road_10",
        "name": "Hub River Road",
        "origin": "24.8900,66.9800",
        "destination": "24.8700,66.9200",
    },
]


def calculate_congestion_level(google_data: dict) -> str:
    try:
        normal = google_data.get("duration_normal_secs")
        in_traffic = google_data.get("duration_in_traffic_secs")
        if not normal or not in_traffic:
            return "unknown"
        ratio = in_traffic / normal
        if ratio <= 1.1:
            return "free_flow"
        elif ratio <= 1.3:
            return "light"
        elif ratio <= 1.6:
            return "moderate"
        else:
            return "heavy"
    except Exception:
        return "unknown"


def fetch_google_traffic(road: dict) -> dict:
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": road["origin"],
        "destinations": road["destination"],
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": GOOGLE_API_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        element = data["rows"][0]["elements"][0]
        return {
            "duration_normal_secs": element["duration"]["value"],
            "duration_in_traffic_secs": element.get("duration_in_traffic", {}).get(
                "value"
            ),
            "distance_meters": element["distance"]["value"],
            "status": element["status"],
        }
    except Exception as e:
        return {"error": str(e), "status": "FAILED"}


def insert_to_supabase(
    road: dict, google_data: dict, congestion_level: str, timestamp: str
):
    now = datetime.now(timezone.utc)
    record = {
        "road_id": road["id"],
        "timestamp": timestamp,
        "duration_normal_secs": google_data.get("duration_normal_secs"),
        "duration_in_traffic_secs": google_data.get("duration_in_traffic_secs"),
        "distance_meters": google_data.get("distance_meters"),
        "congestion_ratio": round(
            google_data["duration_in_traffic_secs"]
            / google_data["duration_normal_secs"],
            3,
        )
        if google_data.get("duration_normal_secs")
        and google_data.get("duration_in_traffic_secs")
        else None,
        "congestion_level": congestion_level,
        "google_status": google_data.get("status", "OK"),
        "hour_of_day": now.hour,
        "day_of_week": now.weekday(),
        "is_weekend": now.weekday() >= 5,
        "is_ramadan": False,
        "is_eid": False,
        "is_monsoon": now.month in [7, 8, 9],
        "data_source": "google_maps",
    }
    try:
        result = supabase.table("traffic_readings").insert(record).execute()
        return True
    except Exception as e:
        print(f"  Supabase insert error for {road['id']}: {e}")
        return False


def run_pipeline():
    print("Starting Hero's Initiative data pipeline...")
    timestamp = datetime.now(timezone.utc).isoformat()
    success_count = 0

    for road in KARACHI_ROADS:
        print(f"Fetching: {road['name']}...")
        google_data = fetch_google_traffic(road)

        if google_data.get("status") == "FAILED":
            print(f"  Google API failed for {road['id']}: {google_data.get('error')}")
            continue

        congestion_level = calculate_congestion_level(google_data)
        inserted = insert_to_supabase(road, google_data, congestion_level, timestamp)

        if inserted:
            ratio = round(
                google_data["duration_in_traffic_secs"]
                / google_data["duration_normal_secs"],
                2,
            )
            print(
                f"  {road['id']} -> {congestion_level} (ratio: {ratio}) saved to Supabase"
            )
            success_count += 1

    print(f"\nDone. {success_count}/10 roads saved to Supabase.")
    return success_count


if __name__ == "__main__":
    run_pipeline()
