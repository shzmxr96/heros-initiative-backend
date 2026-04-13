from fastapi import APIRouter, HTTPException
from app.pipeline.data_pipeline import run_pipeline

router = APIRouter()

@router.get("/traffic", summary="Get latest traffic for all 10 Karachi roads")
def get_traffic():
    try:
        from supabase import create_client
        import os
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        supabase = create_client(url, key)
        result = supabase.table("traffic_readings").select(
            "road_id, timestamp, congestion_level, congestion_ratio, duration_normal_secs, duration_in_traffic_secs, distance_meters, hour_of_day, day_of_week, data_source"
        ).order("timestamp", desc=True).limit(10).execute()
        return {"status": "ok", "roads": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pipeline/run", summary="Manually trigger the data pipeline")
def trigger_pipeline():
    try:
        count = run_pipeline()
        return {"status": "ok", "roads_fetched": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/readings", summary="Get recent traffic readings from Supabase")
def get_readings(road_id: str = None, limit: int = 100):
    try:
        from supabase import create_client
        import os
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        supabase = create_client(url, key)
        query = supabase.table("traffic_readings").select("*").order("timestamp", desc=True).limit(limit)
        if road_id:
            query = query.eq("road_id", road_id)
        result = query.execute()
        return {"status": "ok", "count": len(result.data), "readings": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models", summary="List available ML models")
def list_models():
    return {"models": ["arima", "lstm", "random_forest"], "status": "not yet trained — awaiting sufficient data"}

@router.get("/accuracy", summary="Get rolling 7-day prediction accuracy")
def get_accuracy():
    try:
        from supabase import create_client
        import os
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        supabase = create_client(url, key)
        result = supabase.rpc("prediction_accuracy").execute()
        return {"status": "ok", "accuracy": result.data}
    except Exception as e:
        return {"status": "no predictions yet", "accuracy": []}