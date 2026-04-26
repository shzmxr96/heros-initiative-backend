import os
import random
import math
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ============================================================
# ROAD BASE PROFILES
# ============================================================
ROAD_PROFILES = {
    "road_01": {"name": "Shahrae Faisal",     "weekday_base": 1.25, "weekend_evening_base": 1.55, "social": True,  "highway": False},
    "road_02": {"name": "MA Jinnah Road",     "weekday_base": 1.20, "weekend_evening_base": 1.25, "social": True,  "highway": False},
    "road_03": {"name": "University Road",    "weekday_base": 1.20, "weekend_evening_base": 1.60, "social": True,  "highway": False, "green_line": True},
    "road_04": {"name": "Korangi Road",       "weekday_base": 1.15, "weekend_evening_base": 1.00, "social": False, "highway": False},
    "road_05": {"name": "Northern Bypass",    "weekday_base": 1.05, "weekend_evening_base": 1.05, "social": False, "highway": True},
    "road_06": {"name": "Lyari Expressway",   "weekday_base": 1.10, "weekend_evening_base": 1.00, "social": False, "highway": True},
    "road_07": {"name": "Rashid Minhas Road", "weekday_base": 1.20, "weekend_evening_base": 1.45, "social": True,  "highway": False},
    "road_08": {"name": "Clifton Bridge",     "weekday_base": 1.25, "weekend_evening_base": 1.50, "social": True,  "highway": False},
    "road_09": {"name": "Superhighway",       "weekday_base": 1.05, "weekend_evening_base": 1.05, "social": False, "highway": True},
    "road_10": {"name": "Hub River Road",     "weekday_base": 1.10, "weekend_evening_base": 1.00, "social": False, "highway": False},
}

# ============================================================
# RAMADAN DATES (approximate, Pakistan)
# ============================================================
RAMADAN_PERIODS = [
    (datetime(2024, 3, 11), datetime(2024, 4, 9)),
    (datetime(2025, 3, 1),  datetime(2025, 3, 30)),
    (datetime(2026, 2, 18), datetime(2026, 3, 19)),
]

EID_FITR_PERIODS = [
    (datetime(2024, 4, 10), datetime(2024, 4, 13)),
    (datetime(2025, 3, 31), datetime(2025, 4, 3)),
    (datetime(2026, 3, 20), datetime(2026, 3, 23)),
]

EID_ADHA_PERIODS = [
    (datetime(2024, 6, 17), datetime(2024, 6, 20)),
    (datetime(2025, 6, 7),  datetime(2025, 6, 10)),
]

# PSL match days (approximate home matches in Karachi)
PSL_MATCH_DAYS_2024 = [
    datetime(2024, 2, 17), datetime(2024, 2, 19), datetime(2024, 2, 22),
    datetime(2024, 2, 25), datetime(2024, 2, 28), datetime(2024, 3, 2),
    datetime(2024, 3, 5),  datetime(2024, 3, 8),  datetime(2024, 3, 14),
    datetime(2024, 3, 17),
]
PSL_MATCH_DAYS_2025 = [
    datetime(2025, 4, 11), datetime(2025, 4, 13), datetime(2025, 4, 16),
    datetime(2025, 4, 19), datetime(2025, 4, 22), datetime(2025, 4, 25),
    datetime(2025, 4, 28), datetime(2025, 5, 1),  datetime(2025, 5, 4),
    datetime(2025, 5, 7),
]
PSL_MATCH_DAYS = PSL_MATCH_DAYS_2024 + PSL_MATCH_DAYS_2025

# Karachi Eat Festival
KARACHI_EAT_DAYS = [
    datetime(2024, 2, 2), datetime(2024, 2, 3), datetime(2024, 2, 4),
    datetime(2025, 1, 31), datetime(2025, 2, 1), datetime(2025, 2, 2),
]

# IDEAS Defence Exhibition
IDEAS_DAYS = [
    datetime(2024, 11, 19), datetime(2024, 11, 20),
    datetime(2024, 11, 21), datetime(2024, 11, 22),
]

# University Road pipeline closure Nov-Dec 2025
UNIV_ROAD_CLOSURE = (datetime(2025, 11, 10), datetime(2025, 12, 30))

# Wedding season months
WEDDING_SEASON_MONTHS = [11, 12, 1, 2, 5, 6]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def is_ramadan(dt):
    for start, end in RAMADAN_PERIODS:
        if start <= dt <= end:
            return True
    return False

def is_eid(dt):
    for start, end in EID_FITR_PERIODS + EID_ADHA_PERIODS:
        if start <= dt <= end:
            return True
    return False

def eid_day_number(dt):
    """Returns 1, 2, 3 for first/second/third day of Eid, else 0"""
    for start, end in EID_FITR_PERIODS + EID_ADHA_PERIODS:
        if start <= dt <= end:
            return (dt - start).days + 1
    return 0

def is_monsoon(dt):
    return dt.month in [7, 8, 9]

def is_psl_match_day(dt):
    return any(d.date() == dt.date() for d in PSL_MATCH_DAYS)

def is_karachi_eat_day(dt):
    return any(d.date() == dt.date() for d in KARACHI_EAT_DAYS)

def is_ideas_day(dt):
    return any(d.date() == dt.date() for d in IDEAS_DAYS)

def is_wedding_season(dt):
    return dt.month in WEDDING_SEASON_MONTHS

def get_green_line_addition(dt):
    """Progressive construction worsening for University Road"""
    if dt < datetime(2024, 7, 1):
        return 0.25
    elif dt < datetime(2025, 1, 1):
        return 0.35
    elif dt < datetime(2025, 7, 1):
        return 0.45
    elif dt < datetime(2025, 11, 10):
        return 0.55
    else:
        return 0.65

def get_time_multiplier(hour, road_id, is_weekend_day, dt):
    """Get congestion multiplier based on time of day and road"""

    # University Road triple peak (school + social)
    if road_id == "road_03":
        if 7 <= hour < 9:
            m = 1.9  # School morning rush
        elif 9 <= hour < 10:
            m = 1.3
        elif 13 <= hour < 15:
            m = 1.8  # School pickup
        elif 15 <= hour < 17:
            m = 1.2
        elif 19 <= hour < 23:
            m = 2.0 if not is_weekend_day else 2.2  # Social peak
        elif 23 <= hour or hour < 5:
            m = 0.7
        elif 5 <= hour < 7:
            m = 0.9
        else:
            m = 1.1

    # Rashid Minhas — Gulshan feeder, school + social
    elif road_id == "road_07":
        if 7 <= hour < 9:
            m = 1.7
        elif 13 <= hour < 15:
            m = 1.6
        elif 19 <= hour < 23:
            m = 1.8 if not is_weekend_day else 2.0
        elif 23 <= hour or hour < 5:
            m = 0.7
        else:
            m = 1.1

    # Shahrae Faisal — main social corridor
    elif road_id == "road_01":
        if 8 <= hour < 10:
            m = 1.8
        elif 17 <= hour < 20:
            m = 1.9
        elif 20 <= hour < 23:
            m = 1.6 if not is_weekend_day else 1.9
        elif 23 <= hour or hour < 5:
            m = 0.7
        else:
            m = 1.1

    # MA Jinnah Road — Burns Road / Saddar
    elif road_id == "road_02":
        if 8 <= hour < 10:
            m = 1.6
        elif 17 <= hour < 19:
            m = 1.7
        elif 19 <= hour < 23:
            m = 1.5
        elif 23 <= hour or hour < 5:
            m = 0.7
        else:
            m = 1.1

    # Clifton Bridge — bottleneck
    elif road_id == "road_08":
        if 8 <= hour < 10:
            m = 1.7
        elif 18 <= hour < 21:
            m = 1.8 if not is_weekend_day else 2.0
        elif 23 <= hour or hour < 5:
            m = 0.7
        else:
            m = 1.1

    # Highways — Northern Bypass, Superhighway
    elif road_id in ["road_05", "road_09"]:
        if 7 <= hour < 9:
            m = 1.3
        elif 17 <= hour < 20:
            m = 1.4
        elif 23 <= hour or hour < 5:
            m = 0.7
        else:
            m = 1.0

    # Industrial roads — Korangi, Hub River, Lyari
    else:
        if 7 <= hour < 9:
            m = 1.5
        elif 17 <= hour < 19:
            m = 1.4
        elif 23 <= hour or hour < 5:
            m = 0.6
        else:
            m = 1.0

    # Weekend adjustment for social roads
    if is_weekend_day and road_id in ["road_01", "road_03", "road_07", "road_08"]:
        if 19 <= hour < 24:
            m *= 1.15
        elif hour < 7:
            m *= 0.8

    return m


def get_event_multiplier(dt, road_id, hour):
    """Get additional event-based multiplier"""
    multiplier = 1.0
    hour_int = hour

    # Eid
    eid_day = eid_day_number(dt)
    if eid_day in [1, 2]:
        multiplier *= 0.4  # Dead — everyone home
    elif eid_day == 3:
        multiplier *= 1.4  # Visiting relatives

    # PSL match days
    if is_psl_match_day(dt) and road_id in ["road_03", "road_07"] and 17 <= hour_int < 24:
        multiplier *= 2.1

    # Karachi Eat Festival
    if is_karachi_eat_day(dt) and road_id in ["road_01", "road_08"] and 17 <= hour_int < 24:
        multiplier *= 1.7

    # IDEAS Defence Exhibition
    if is_ideas_day(dt) and road_id in ["road_03", "road_07"] and 7 <= hour_int < 20:
        multiplier *= 2.4

    # Ramadan
    if is_ramadan(dt):
        if 4 <= hour_int < 6:  # Sehri rush
            multiplier *= random.uniform(1.2, 1.5)
        elif 6 <= hour_int < 12:  # Slow mornings
            multiplier *= 0.75
        elif 18 <= hour_int < 20:  # Iftar rush
            multiplier *= random.uniform(1.3, 1.7)
        elif 20 <= hour_int < 24:  # Post-Iftar/Tarawih
            if road_id in ["road_01", "road_03", "road_07", "road_08"]:
                multiplier *= random.uniform(1.4, 2.2)  # Gulshan worst
            else:
                multiplier *= random.uniform(1.1, 1.5)

    # Wedding season Friday-Sunday evenings
    if is_wedding_season(dt) and dt.weekday() in [4, 5, 6] and 19 <= hour_int < 24:
        if road_id in ["road_01", "road_03", "road_07", "road_08"]:
            multiplier *= 1.4

    # Monsoon rain effect
    if is_monsoon(dt) and random.random() < 0.3:  # 30% chance of rain
        multiplier *= random.uniform(1.3, 1.8)

    # 14 August
    if dt.month == 8 and dt.day == 14:
        if hour_int < 12:
            multiplier *= 0.5
        elif 20 <= hour_int < 24:
            multiplier *= 1.8

    # University Road pipeline closure Nov-Dec 2025
    if road_id == "road_03":
        closure_start, closure_end = UNIV_ROAD_CLOSURE
        if closure_start <= dt <= closure_end:
            multiplier *= 1.4  # Additional closure chaos

    # Random concert/large event (8-10 times per year)
    if road_id in ["road_01", "road_07", "road_08"]:
        if random.random() < 0.003 and 19 <= hour_int < 24:
            multiplier *= 1.6

    # Random accident spike (1 in 50 readings)
    if random.random() < 0.02:
        multiplier *= random.uniform(1.3, 1.8)

    return multiplier


def calculate_congestion_level(ratio):
    if ratio <= 1.1:
        return "free_flow"
    elif ratio <= 1.3:
        return "light"
    elif ratio <= 1.6:
        return "moderate"
    else:
        return "heavy"


def generate_reading(dt, road_id):
    """Generate a single synthetic traffic reading"""
    profile = ROAD_PROFILES[road_id]
    hour = dt.hour
    dow = dt.weekday()
    is_weekend_day = dow >= 5

    # Base ratio
    base = profile["weekday_base"]
    if is_weekend_day and profile["social"]:
        if 19 <= hour < 24:
            base = profile["weekend_evening_base"]
        elif hour < 7:
            base = profile["weekday_base"] * 0.85

    # Green Line construction progressive worsening
    if profile.get("green_line"):
        base += get_green_line_addition(dt)

    # Time multiplier
    time_mult = get_time_multiplier(hour, road_id, is_weekend_day, dt)

    # Event multiplier
    event_mult = get_event_multiplier(dt, road_id, hour)

    # Noise ±10%
    noise = random.uniform(0.90, 1.10)

    # Final ratio
    ratio = base * time_mult * event_mult * noise

    # Cap between 0.6 and 3.0
    ratio = max(0.6, min(3.0, ratio))
    ratio = round(ratio, 3)

    congestion_level = calculate_congestion_level(ratio)

    # Estimate realistic travel times (base ~600-2400 secs depending on road)
    base_durations = {
        "road_01": 1800, "road_02": 900, "road_03": 1200,
        "road_04": 1200, "road_05": 1800, "road_06": 1500,
        "road_07": 900,  "road_08": 600,  "road_09": 2400,
        "road_10": 1500
    }
    base_distances = {
        "road_01": 12000, "road_02": 3500, "road_03": 6000,
        "road_04": 6000,  "road_05": 15000, "road_06": 10000,
        "road_07": 4500,  "road_08": 4000,  "road_09": 20000,
        "road_10": 11000
    }

    duration_normal = base_durations[road_id]
    duration_in_traffic = int(duration_normal * ratio)
    distance_meters = base_distances[road_id]

    return {
        "road_id": road_id,
        "timestamp": dt.replace(tzinfo=timezone.utc).isoformat(),
        "duration_normal_secs": duration_normal,
        "duration_in_traffic_secs": duration_in_traffic,
        "distance_meters": distance_meters,
        "congestion_ratio": ratio,
        "congestion_level": congestion_level,
        "google_status": "OK",
        "hour_of_day": hour,
        "day_of_week": dow,
        "is_weekend": is_weekend_day,
        "is_ramadan": is_ramadan(dt),
        "is_eid": is_eid(dt),
        "is_monsoon": is_monsoon(dt),
        "data_source": "synthetic"
    }


def run_generator():
    """Generate 24 months of synthetic data and insert into Supabase"""
    start_date = datetime(2024, 4, 1)
    end_date = datetime(2026, 4, 1)
    interval = timedelta(minutes=15)

    road_ids = list(ROAD_PROFILES.keys())
    batch = []
    batch_size = 500
    total_inserted = 0

    print("Starting synthetic data generation...")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Roads: {len(road_ids)} | Interval: 15 minutes")

    current = start_date
    while current < end_date:
        for road_id in road_ids:
            record = generate_reading(current, road_id)
            batch.append(record)

        if len(batch) >= batch_size:
            supabase.table("traffic_readings").insert(batch).execute()
            total_inserted += len(batch)
            print(f"  Inserted {total_inserted:,} rows... ({current.date()})")
            batch = []

        current += interval

    # Insert remaining
    if batch:
        supabase.table("traffic_readings").insert(batch).execute()
        total_inserted += len(batch)

    print(f"\nDone! Total synthetic rows inserted: {total_inserted:,}")
    return total_inserted


if __name__ == "__main__":
    run_generator()