from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.pipeline.data_pipeline import run_pipeline

router = APIRouter()


def _db(service_key: bool = False):
    """Return a Supabase client. Uses service key for write operations."""
    from supabase import create_client
    import os

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY" if service_key else "SUPABASE_ANON_KEY")
    return create_client(url, key)


# ── Traffic ────────────────────────────────────────────────────────────────────


@router.get("/traffic", summary="Get latest traffic for all 10 Karachi roads")
def get_traffic():
    """
    Reads from the latest_traffic view — one row per road, most recent reading.
    FIX: previous version requested duration_normal_secs and duration_in_traffic_secs
    which were removed in migration v2. Now reads from the view directly.
    """
    try:
        result = _db().table("latest_traffic").select("*").execute()
        return {"status": "ok", "roads": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/readings", summary="Get recent traffic readings from Supabase")
def get_readings(road_id: str = None, limit: int = 100):
    try:
        query = (
            _db()
            .table("traffic_readings")
            .select(
                "road_id,timestamp,congestion_ratio,congestion_level,"
                "delay_seconds,estimated_speed_kmh,distance_meters,"
                "hour_of_day,day_of_week,is_weekend,is_ramadan,is_eid,"
                "is_monsoon,data_source"
            )
            .order("timestamp", desc=True)
            .limit(limit)
        )
        if road_id:
            query = query.eq("road_id", road_id)
        result = query.execute()
        return {"status": "ok", "count": len(result.data), "readings": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Pipeline ───────────────────────────────────────────────────────────────────


@router.post("/pipeline/run", summary="Manually trigger the data pipeline")
async def trigger_pipeline():
    """
    FIX: was a sync endpoint calling an async function without await.
    Coroutine was being discarded and nothing was running.
    """
    try:
        count = await run_pipeline()
        return {"status": "ok", "roads_fetched": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Models ─────────────────────────────────────────────────────────────────────


@router.get("/models", summary="List ML models and training history")
def list_models():
    """
    FIX: was returning hardcoded arima/lstm/random_forest placeholder.
    Now reads from model_runs table.
    """
    try:
        result = (
            _db()
            .table("model_runs")
            .select(
                "run_id,model_name,model_version,trained_at,"
                "accuracy_score,training_rows,training_data_range,is_active,notes"
            )
            .order("trained_at", desc=True)
            .limit(20)
            .execute()
        )
        active = [r for r in result.data if r.get("is_active")]
        return {
            "status": "ok",
            "active_models": active,
            "all_runs": result.data,
        }
    except Exception as e:
        return {"status": "no models trained yet", "active_models": [], "all_runs": []}


@router.post(
    "/models/train", summary="Train XGBoost model on all available traffic data"
)
def train_model(background_tasks: BackgroundTasks):
    """
    Triggers XGBoost training in the background.
    Training runs asynchronously — check GET /models for completion and accuracy.
    Requires at least 500 rows in traffic_readings (synthetic data satisfies this).
    """
    try:
        from app.ml.model_service import train_xgboost

        background_tasks.add_task(train_xgboost)
        return {
            "status": "training started",
            "message": "XGBoost training running in background. Check GET /models for status and accuracy score.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Predictions ────────────────────────────────────────────────────────────────


@router.post("/predict", summary="Run XGBoost inference for a specific road")
def predict(road_id: str):
    """
    Runs inference for the given road_id against its latest reading.
    Inserts 6 prediction rows (15, 30, 60, 120, 240, 360 min horizons)
    with feature_snapshot and shap_values populated.
    Returns 503 if no model has been trained yet.
    """
    try:
        from app.ml.model_service import (
            model_is_trained,
            build_feature_dict,
            predict_road,
        )

        if not model_is_trained():
            raise HTTPException(
                status_code=503,
                detail="No trained model found. POST /api/v1/models/train first.",
            )

        db = _db(service_key=True)

        # Latest reading for this road
        latest = (
            db.table("traffic_readings")
            .select("*")
            .eq("road_id", road_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if not latest.data:
            raise HTTPException(
                status_code=404, detail=f"No readings found for {road_id}"
            )

        row = latest.data[0]
        reading_id = row["id"]

        # History for lag features (97 = 96 prior + skip current)
        history = (
            db.table("traffic_readings")
            .select("congestion_ratio")
            .eq("road_id", road_id)
            .order("timestamp", desc=True)
            .limit(97)
            .execute()
        )
        history_list = list(reversed(history.data[1:]))

        features = build_feature_dict(row, history_list)
        predictions = predict_road(road_id, reading_id, features)

        return {"status": "ok", "road_id": road_id, "predictions": predictions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Accuracy ───────────────────────────────────────────────────────────────────


@router.get("/accuracy", summary="Get rolling 7-day prediction accuracy per model")
def get_accuracy():
    try:
        result = _db().table("prediction_accuracy").select("*").execute()
        return {"status": "ok", "accuracy": result.data}
    except Exception as e:
        return {"status": "no predictions yet", "accuracy": []}
