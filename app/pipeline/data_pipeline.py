import os
import json
import requests
from datetime import datetime

# --- 10 Karachi Road Segments ---
KARACHI_ROADS = [
    {
        "id": "road_01",
        "name": "Shahrae Faisal (Airport to Metropole)",
        "origin": "24.9008,67.1681",
        "destination": "24.8710,67.0822",
        "tomtom_point": "24.8900,67.1300"
    },
    {
        "id": "road_02",
        "name": "MA Jinnah Road (Merewether to Empress Market)",
        "origin": "24.8592,67.0104",
        "destination": "24.8607,67.0313",
        "tomtom_point": "24.8600,67.0200"
    },
    {
        "id": "road_03",
        "name": "University Road (Gulshan Chowrangi to Hassan Square)",
        "origin": "24.9312,67.1100",
        "destination": "24.9268,67.0791",
        "tomtom_point": "24.9290,67.0950"
    },
    {
        "id": "road_04",
        "name": "Korangi Road (Korangi Crossing to Landhi)",
        "origin": "24.8350,67.1300",
        "destination": "24.8450,67.1650",
        "tomtom_point": "24.8400,67.1480"
    },
    {
        "id": "road_05",
        "name": "Northern Bypass (Superhighway to M9)",
        "origin": "25.0600,67.1800",
        "destination": "24.9900,67.2300",
        "tomtom_point": "25.0200,67.2050"
    },
    {
        "id": "road_06",
        "name": "Lyari Expressway (Gharibabad to Kemari)",
        "origin": "24.8800,67.0200",
        "destination": "24.8350,66.9900",
        "tomtom_point": "24.8580,67.0050"
    },
    {
        "id": "road_07",
        "name": "Rashid Minhas Road (Gulshan to Nursery)",
        "origin": "24.9200,67.0900",
        "destination": "24.8950,67.0700",
        "tomtom_point": "24.9080,67.0800"
    },
    {
        "id": "road_08",
        "name": "Clifton Bridge to Do Talwar",
        "origin": "24.8050,67.0250",
        "destination": "24.8120,67.0350",
        "tomtom_point": "24.8080,67.0300"
    },
    {
        "id": "road_09",
        "name": "Superhighway (Toll Plaza to Karachi)",
        "origin": "25.1200,67.2800",
        "destination": "24.9800,67.2100",
        "tomtom_point": "25.0500,67.2450"
    },
    {
        "id": "road_10",
        "name": "Hub River Road (SITE to Hub Chowki)",
        "origin": "24.8900,66.9800",
        "destination": "24.8700,66.9200",
        "tomtom_point": "24.8800,66.9500"
    },
]

GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")


def fetch_google_traffic(road: dict) -> dict:
    """Fetch travel time and distance from Google Distance Matrix API."""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": road["origin"],
        "destinations": road["destination"],
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": GOOGLE_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        element = data["rows"][0]["elements"][0]
        return {
            "duration_normal_secs": element["duration"]["value"],
            "duration_in_traffic_secs": element.get("duration_in_traffic", {}).get("value"),
            "distance_meters": element["distance"]["value"],
            "status": element["status"]
        }
    except Exception as e:
        return {"error": str(e), "status": "FAILED"}


def fetch_tomtom_traffic(road: dict) -> dict:
    """Fetch real-time traffic flow from TomTom Traffic Flow API."""
    lat, lon = road["tomtom_point"].split(",")
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {
        "point": f"{lat},{lon}",
        "key": TOMTOM_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        flow = data.get("flowSegmentData", {})
        return {
            "current_speed_kmh": flow.get("currentSpeed"),
            "free_flow_speed_kmh": flow.get("freeFlowSpeed"),
            "current_travel_time_secs": flow.get("currentTravelTime"),
            "free_flow_travel_time_secs": flow.get("freeFlowTravelTime"),
            "confidence": flow.get("confidence"),
            "road_closure": flow.get("roadClosure", False)
        }
    except Exception as e:
        return {"error": str(e), "status": "FAILED"}


def calculate_congestion_level(google_data: dict) -> str:
    """Calculate congestion level from Google traffic delay ratio."""
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


def fetch_all_roads() -> list:
    """Fetch traffic data for all 10 Karachi road segments."""
    results = []
    timestamp = datetime.utcnow().isoformat()

    for road in KARACHI_ROADS:
        print(f"Fetching: {road['name']}...")

        google_data = fetch_google_traffic(road)
        tomtom_data = fetch_tomtom_traffic(road)
        congestion = calculate_congestion_level(google_data)

        result = {
            "timestamp": timestamp,
            "road_id": road["id"],
            "road_name": road["name"],
            "origin": road["origin"],
            "destination": road["destination"],
            "congestion_level": congestion,
            "google": google_data,
            "tomtom": tomtom_data
        }
        results.append(result)

    return results


def save_to_file(data: list):
    """Save fetched data to /data/raw/ as a JSON file."""
    os.makedirs("data/raw", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filepath = f"data/raw/traffic_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {filepath}")
    return filepath


def run_pipeline():
    """Main function — fetch all roads and save results."""
    print("Starting Hero's Initiative data pipeline...")
    data = fetch_all_roads()
    filepath = save_to_file(data)
    print(f"Done. {len(data)} roads fetched.")
    return {"roads_fetched": len(data), "saved_to": filepath, "data": data}


if __name__ == "__main__":
    run_pipeline()