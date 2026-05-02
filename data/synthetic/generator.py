import os
import random
import math
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Road profiles for the 17 PoC segments ─────────────────────────────────────
#
# corridor groups:
#   shahrae_faisal — office/airport commuter, moderate social
#   sem            — Shaheed-e-Millat expressway, pure commuter
#   clifton        — social corridor, extended evening
#   gulshan        — Gulshan/Rashid Minhas, school + social + commercial
#
# green_line: True for Usmani Rd segments affected by BRT construction
#
ROAD_PROFILES = {
    "road_01a": {"name": "Shahrae Faisal",   "corridor": "shahrae_faisal", "social": False, "weekday_base": 1.15, "weekend_evening_base": 1.20},
    "road_01b": {"name": "Shahrae Faisal",   "corridor": "shahrae_faisal", "social": False, "weekday_base": 1.15, "weekend_evening_base": 1.20},
    "road_01c": {"name": "Shahrae Faisal",   "corridor": "shahrae_faisal", "social": False, "weekday_base": 1.20, "weekend_evening_base": 1.25},
    "road_01d": {"name": "Shaheed-e-Millat", "corridor": "shahrae_faisal", "social": False, "weekday_base": 1.20, "weekend_evening_base": 1.25},
    "road_01e": {"name": "Shaheed-e-Millat", "corridor": "shahrae_faisal", "social": False, "weekday_base": 1.15, "weekend_evening_base": 1.20},
    "road_01f": {"name": "Shahrae Faisal",   "corridor": "shahrae_faisal", "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55},
    "road_02a": {"name": "Shaheed-e-Millat", "corridor": "sem",            "social": False, "weekday_base": 1.10, "weekend_evening_base": 1.10},
    "road_02b": {"name": "Shaheed-e-Millat", "corridor": "sem",            "social": False, "weekday_base": 1.10, "weekend_evening_base": 1.10},
    "road_04a": {"name": "Khayaban-e-Iqbal", "corridor": "clifton",        "social": True,  "weekday_base": 1.15, "weekend_evening_base": 1.70},
    "road_04b": {"name": "Khayaban-e-Iqbal", "corridor": "clifton",        "social": True,  "weekday_base": 1.15, "weekend_evening_base": 1.70},
    "road_05a": {"name": "Usmani Rd",        "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55, "green_line": True},
    "road_05b": {"name": "Rashid Minhas",    "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55},
    "road_05c": {"name": "Usmani Rd",        "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55, "green_line": True},
    "road_06a": {"name": "Rashid Minhas",    "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55},
    "road_06b": {"name": "Rashid Minhas",    "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55},
    "road_06c": {"name": "Rashid Minhas",    "corridor": "gulshan",        "social": True,  "weekday_base": 1.25, "weekend_evening_base": 1.60},
    "road_06d": {"name": "Rashid Minhas",    "corridor": "gulshan",        "social": True,  "weekday_base": 1.20, "weekend_evening_base": 1.55},
}

# Free-flow (static) travel time in seconds — derived from distance / free-flow speed.
# These mirror the actual segment distances in data_pipeline.py.
BASE_DURATIONS = {
    "road_01a": 380, "road_01b": 225, "road_01c": 108,
    "road_01d":  75, "road_01e": 162, "road_01f": 240,
    "road_02a": 162, "road_02b": 108,
    "road_04a": 162, "road_04b": 135,
    "road_05a":  96, "road_05b": 108, "road_05c": 120,
    "road_06a": 108, "road_06b": 184, "road_06c":  72, "road_06d": 138,
}

BASE_DISTANCES = {
    "road_01a": 5800, "road_01b": 3400, "road_01c": 1500,
    "road_01d":  850, "road_01e": 1800, "road_01f": 3300,
    "road_02a": 2700, "road_02b": 1800,
    "road_04a": 1800, "road_04b": 1500,
    "road_05a":  800, "road_05b":  900, "road_05c": 1000,
    "road_06a":  900, "road_06b": 2300, "road_06c":  500, "road_06d": 1900,
}

# ── Calendar context ───────────────────────────────────────────────────────────

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

PSL_MATCH_DAYS = [
    datetime(2024, 2, 17), datetime(2024, 2, 19), datetime(2024, 2, 22),
    datetime(2024, 2, 25), datetime(2024, 2, 28), datetime(2024, 3, 2),
    datetime(2024, 3, 5),  datetime(2024, 3, 8),  datetime(2024, 3, 14),
    datetime(2024, 3, 17),
    datetime(2025, 4, 11), datetime(2025, 4, 13), datetime(2025, 4, 16),
    datetime(2025, 4, 19), datetime(2025, 4, 22), datetime(2025, 4, 25),
    datetime(2025, 4, 28), datetime(2025, 5, 1),  datetime(2025, 5, 4),
    datetime(2025, 5, 7),
]
KARACHI_EAT_DAYS = [
    datetime(2024, 2, 2), datetime(2024, 2, 3), datetime(2024, 2, 4),
    datetime(2025, 1, 31), datetime(2025, 2, 1), datetime(2025, 2, 2),
]
IDEAS_DAYS = [
    datetime(2024, 11, 19), datetime(2024, 11, 20),
    datetime(2024, 11, 21), datetime(2024, 11, 22),
]
# Green Line BRT construction worsening on Usmani Rd (road_05a, road_05c)
USMANI_CONSTRUCTION = (datetime(2024, 7, 1), datetime(2026, 12, 31))
WEDDING_SEASON_MONTHS = [11, 12, 1, 2, 5, 6]

# ── Calendar helpers ───────────────────────────────────────────────────────────

def is_ramadan(dt):
    return any(s <= dt <= e for s, e in RAMADAN_PERIODS)

def is_eid(dt):
    return any(s <= dt <= e for s, e in EID_FITR_PERIODS + EID_ADHA_PERIODS)

def eid_day_number(dt):
    for s, e in EID_FITR_PERIODS + EID_ADHA_PERIODS:
        if s <= dt <= e:
            return (dt - s).days + 1
    return 0

def is_monsoon(dt):
    return dt.month in [7, 8, 9]

def is_psl_day(dt):
    return any(d.date() == dt.date() for d in PSL_MATCH_DAYS)

def is_karachi_eat_day(dt):
    return any(d.date() == dt.date() for d in KARACHI_EAT_DAYS)

def is_ideas_day(dt):
    return any(d.date() == dt.date() for d in IDEAS_DAYS)

def get_green_line_addition(dt):
    if dt < datetime(2024, 7, 1):
        return 0.0
    elif dt < datetime(2025, 1, 1):
        return 0.20
    elif dt < datetime(2025, 7, 1):
        return 0.30
    elif dt < datetime(2025, 11, 1):
        return 0.40
    else:
        return 0.50

# ── Traffic pattern multipliers ────────────────────────────────────────────────

def get_time_multiplier(hour, corridor, is_weekend_day):
    """Congestion multiplier by hour and corridor. Weekday unless is_weekend_day."""
    if corridor == "shahrae_faisal":
        if 8 <= hour < 10:
            m = 1.85
        elif 17 <= hour < 20:
            m = 1.90
        elif 20 <= hour < 23:
            m = 1.40 if not is_weekend_day else 1.65
        elif hour >= 23 or hour < 5:
            m = 0.65
        elif 5 <= hour < 8:
            m = 0.90
        else:
            m = 1.10

    elif corridor == "sem":
        if 8 <= hour < 10:
            m = 1.70
        elif 17 <= hour < 20:
            m = 1.80
        elif hour >= 23 or hour < 5:
            m = 0.60
        elif 5 <= hour < 8:
            m = 0.85
        else:
            m = 1.05

    elif corridor == "clifton":
        if 7 <= hour < 9:
            m = 1.60
        elif 9 <= hour < 10:
            m = 1.20
        elif 17 <= hour < 21:
            m = 1.75 if not is_weekend_day else 2.00
        elif 21 <= hour < 23:
            m = 1.40 if not is_weekend_day else 1.70
        elif hour >= 23 or hour < 5:
            m = 0.65
        elif 5 <= hour < 7:
            m = 0.85
        else:
            m = 1.10

    elif corridor == "gulshan":
        if 7 <= hour < 9:
            m = 1.80
        elif 9 <= hour < 10:
            m = 1.30
        elif 13 <= hour < 15:
            m = 1.70
        elif 15 <= hour < 17:
            m = 1.20
        elif 17 <= hour < 21:
            m = 1.85 if not is_weekend_day else 2.10
        elif 21 <= hour < 23:
            m = 1.40 if not is_weekend_day else 1.65
        elif hour >= 23 or hour < 5:
            m = 0.65
        elif 5 <= hour < 7:
            m = 0.85
        else:
            m = 1.10

    else:
        m = 1.0

    # Friday evening bump everywhere
    return m


def get_event_multiplier(dt, road_id, hour, corridor):
    mult = 1.0

    # Eid — roads go dead day 1-2, spike day 3 (visiting relatives)
    eid_day = eid_day_number(dt)
    if eid_day in [1, 2]:
        mult *= 0.35
    elif eid_day == 3:
        mult *= 1.40

    # PSL at National Stadium — near Gulshan corridor
    if is_psl_day(dt) and corridor == "gulshan" and 17 <= hour < 24:
        mult *= 2.00

    # Karachi Eat Festival — near Clifton / Shahrae Faisal south
    if is_karachi_eat_day(dt) and corridor in ("clifton", "shahrae_faisal") and 17 <= hour < 24:
        mult *= 1.70

    # IDEAS Defence Exhibition — near Expo Center (Gulshan area)
    if is_ideas_day(dt) and corridor == "gulshan" and 7 <= hour < 20:
        mult *= 2.20

    # Ramadan
    if is_ramadan(dt):
        if 4 <= hour < 6:       # Sehri rush
            mult *= random.uniform(1.20, 1.50)
        elif 6 <= hour < 12:    # Slow mornings
            mult *= 0.75
        elif 18 <= hour < 20:   # Iftar rush
            mult *= random.uniform(1.40, 1.80)
        elif 20 <= hour < 24:   # Post-Iftar / Tarawih
            if corridor in ("gulshan", "clifton"):
                mult *= random.uniform(1.50, 2.20)
            else:
                mult *= random.uniform(1.10, 1.50)

    # Wedding season (Nov-Feb + May-Jun) Fri-Sun evenings
    if dt.month in WEDDING_SEASON_MONTHS and dt.weekday() in [4, 5, 6] and 19 <= hour < 24:
        if corridor in ("gulshan", "clifton", "shahrae_faisal"):
            mult *= 1.40

    # Monsoon — random rain events (~25% of hours in season)
    if is_monsoon(dt) and random.random() < 0.25:
        mult *= random.uniform(1.30, 1.80)

    # Independence Day 14 Aug
    if dt.month == 8 and dt.day == 14:
        if hour < 12:
            mult *= 0.50
        elif 20 <= hour < 24:
            mult *= 1.70

    # Green Line BRT construction (Usmani Rd segments only)
    if ROAD_PROFILES[road_id].get("green_line"):
        if USMANI_CONSTRUCTION[0] <= dt <= USMANI_CONSTRUCTION[1]:
            mult *= (1.0 + get_green_line_addition(dt))

    # Random incident spike — 1 in 60 readings
    if random.random() < 0.017:
        mult *= random.uniform(1.30, 1.80)

    return mult


# ── Congestion classification — mirrors data_pipeline.py ──────────────────────

def classify_congestion(ratio):
    if ratio < 1.10:
        return "free_flow"
    elif ratio < 1.30:
        return "light"
    elif ratio < 1.60:
        return "moderate"
    else:
        return "heavy"


# ── Single reading ─────────────────────────────────────────────────────────────

def generate_reading(dt, road_id):
    profile = ROAD_PROFILES[road_id]
    corridor = profile["corridor"]
    hour = dt.hour
    dow = dt.weekday()
    is_weekend_day = dow >= 5

    # Base ratio
    base = profile["weekday_base"]
    if is_weekend_day and profile["social"] and 19 <= hour < 24:
        base = profile["weekend_evening_base"]
    elif is_weekend_day and profile["social"] and hour < 7:
        base = profile["weekday_base"] * 0.85

    time_mult  = get_time_multiplier(hour, corridor, is_weekend_day)
    event_mult = get_event_multiplier(dt, road_id, hour, corridor)
    noise      = random.uniform(0.90, 1.10)

    ratio = max(0.60, min(3.0, round(base * time_mult * event_mult * noise, 3)))
    congestion_level = classify_congestion(ratio)

    duration_normal   = BASE_DURATIONS[road_id]
    duration_traffic  = int(duration_normal * ratio)
    distance_meters   = BASE_DISTANCES[road_id]
    delay_seconds     = max(0, duration_traffic - duration_normal)
    estimated_speed   = round((distance_meters / duration_traffic) * 3.6, 1) if duration_traffic > 0 else 0.0

    return {
        "road_id":              road_id,
        "timestamp":            dt.replace(tzinfo=timezone.utc).isoformat(),
        "congestion_ratio":     ratio,
        "congestion_level":     congestion_level,
        "delay_seconds":        delay_seconds,
        "estimated_speed_kmh":  estimated_speed,
        "distance_meters":      distance_meters,
        "hour_of_day":          hour,
        "day_of_week":          dow,
        "is_weekend":           is_weekend_day,
        "is_ramadan":           is_ramadan(dt),
        "is_eid":               is_eid(dt),
        "is_monsoon":           is_monsoon(dt),
        "data_source":          "synthetic",
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def run_generator():
    start_date = datetime(2024, 4, 1)
    end_date   = datetime(2026, 4, 1)
    interval   = timedelta(minutes=15)
    road_ids   = list(ROAD_PROFILES.keys())

    batch, batch_size, total = [], 500, 0

    print("Synthetic data generation — Hero's Initiative PoC segments")
    print(f"Period : {start_date.date()} → {end_date.date()}")
    print(f"Roads  : {len(road_ids)} segments | Interval: 15 min")
    expected = int((end_date - start_date).total_seconds() / 900) * len(road_ids)
    print(f"Expected rows: ~{expected:,}\n")

    current = start_date
    while current < end_date:
        for road_id in road_ids:
            batch.append(generate_reading(current, road_id))

        if len(batch) >= batch_size:
            supabase.table("traffic_readings").insert(batch).execute()
            total += len(batch)
            batch = []
            if total % 50000 == 0:
                print(f"  {total:,} rows inserted... ({current.date()})")

        current += interval

    if batch:
        supabase.table("traffic_readings").insert(batch).execute()
        total += len(batch)

    print(f"\nDone — {total:,} rows inserted")
    return total


if __name__ == "__main__":
    run_generator()
