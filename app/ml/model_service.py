"""
app/ml/model_service.py

XGBoost training, inference, SHAP computation, and prediction persistence
for Hero's Initiative Vertical 1 — Traffic Intelligence.

Responsibilities:
  - Load and feature-engineer training data from Supabase
  - Train XGBoost classifier, log to model_runs, save to disk
  - Run inference with SHAP attribution at prediction time
  - Populate predictions table with feature_snapshot + shap_values
  - Backfill was_correct and actual_congestion_level as horizons elapse

Called by:
  - app/pipeline/data_pipeline.py  (inference after each pipeline run)
  - app/api/routes.py               (POST /api/v1/predict, POST /api/v1/models/train)
"""

import logging
import os
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "xgboost_congestion.pkl"
EXPLAINER_PATH = MODEL_DIR / "xgboost_explainer.pkl"

# ── Constants ──────────────────────────────────────────────────────────────────

# XGBoost handles short-to-medium horizons.
# Prophet will handle 720+ minutes and is managed in prophet_service.py (Phase 2).
XGBOOST_HORIZONS = [15, 30, 60, 120, 240, 360]

# Congestion level ↔ integer encoding (must be stable — do not reorder)
LEVEL_ENCODE = {"free_flow": 0, "light": 1, "moderate": 2, "heavy": 3}
LEVEL_DECODE = {v: k for k, v in LEVEL_ENCODE.items()}

# Representative congestion_ratio midpoint per level (for predicted_ratio field)
RATIO_MIDPOINT = {
    "free_flow": 1.05,
    "light": 1.20,
    "moderate": 1.45,
    "heavy": 1.85,
}

# Road ID ordinal encoding — matches road_segments insert order
ROAD_ENCODE = {
    "road_01": 0,
    "road_02": 1,
    "road_03": 2,
    "road_04": 3,
    "road_05": 4,
    "road_06": 5,
    "road_07": 6,
    "road_08": 7,
    "road_09": 8,
    "road_10": 9,
}

# Feature column order — must be identical between training and inference
FEATURES = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_ramadan",
    "is_eid",
    "is_monsoon",
    "road_id_encoded",
    "congestion_ratio",
    "lag_1",
    "lag_4",
    "lag_96",
    "rolling_mean_4",
    "rolling_std_4",
]

# Confidence decay by horizon — longer horizon = lower base confidence
HORIZON_DECAY = {
    15: 1.00,
    30: 0.95,
    60: 0.90,
    120: 0.82,
    240: 0.72,
    360: 0.62,
}

# ── Supabase Client ────────────────────────────────────────────────────────────


def _db() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


# ── Feature Engineering ────────────────────────────────────────────────────────


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame of traffic_readings sorted by (road_id, timestamp),
    compute lag and rolling features per road segment.

    Lag definitions:
      lag_1  = congestion_ratio 15 minutes prior  (1 reading back)
      lag_4  = congestion_ratio 1 hour prior       (4 readings back)
      lag_96 = congestion_ratio 24 hours prior     (96 readings back)

    Rows without sufficient lag history are dropped.
    """
    df = df.copy()

    # Encode categoricals as integers
    df["road_id_encoded"] = df["road_id"].map(ROAD_ENCODE).fillna(-1).astype(int)
    for flag in ("is_weekend", "is_ramadan", "is_eid", "is_monsoon"):
        df[flag] = df[flag].astype(int)

    df = df.sort_values(["road_id", "timestamp"]).reset_index(drop=True)

    # Per-road lag features
    df["lag_1"] = df.groupby("road_id")["congestion_ratio"].shift(1)
    df["lag_4"] = df.groupby("road_id")["congestion_ratio"].shift(4)
    df["lag_96"] = df.groupby("road_id")["congestion_ratio"].shift(96)

    # Per-road rolling stats over the previous 4 readings (excluding current)
    df["rolling_mean_4"] = df.groupby("road_id")["congestion_ratio"].transform(
        lambda x: x.shift(1).rolling(4, min_periods=2).mean()
    )
    df["rolling_std_4"] = df.groupby("road_id")["congestion_ratio"].transform(
        lambda x: x.shift(1).rolling(4, min_periods=2).std().fillna(0.0)
    )

    # Encode target
    df["target"] = df["congestion_level"].map(LEVEL_ENCODE)

    # Drop rows with missing lag history or unrecognised congestion_level
    df = df.dropna(subset=["lag_1", "lag_4", "rolling_mean_4", "target"])
    df["target"] = df["target"].astype(int)

    return df


# ── Training ───────────────────────────────────────────────────────────────────


def train_xgboost(notes: str = "") -> dict:
    """
    Load all traffic_readings from Supabase, engineer features, train
    XGBoost multiclass classifier, persist model + SHAP explainer to disk,
    and log the run to model_runs.

    Returns the inserted model_runs row as a dict.
    """
    db = _db()
    logger.info("train_xgboost: loading traffic_readings from Supabase...")

    # Paginate — Supabase caps responses at 1000 rows per call
    rows, page = [], 0
    while True:
        batch = (
            db.table("traffic_readings")
            .select(
                "road_id,timestamp,congestion_ratio,congestion_level,"
                "hour_of_day,day_of_week,is_weekend,is_ramadan,is_eid,is_monsoon"
            )
            .order("timestamp", desc=False)
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        if not batch.data:
            break
        rows.extend(batch.data)
        if len(batch.data) < 1000:
            break
        page += 1

    logger.info(f"train_xgboost: loaded {len(rows):,} rows")

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
    df = engineer_features(df)

    if len(df) < 500:
        raise ValueError(
            f"Only {len(df)} usable training rows after feature engineering. "
            "Need at least 500. Ensure synthetic data is loaded."
        )

    X = df[FEATURES].values
    y = df["target"].values

    logger.info(
        f"train_xgboost: training on {len(df):,} rows, {len(FEATURES)} features"
    )

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y)

    preds = model.predict(X)
    accuracy = float((preds == y).mean())
    logger.info(f"train_xgboost: in-sample accuracy = {accuracy:.4f}")

    # SHAP TreeExplainer — exact and fast for XGBoost
    logger.info("train_xgboost: building SHAP TreeExplainer...")
    explainer = shap.TreeExplainer(model)

    # Persist to disk
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(EXPLAINER_PATH, "wb") as f:
        pickle.dump(explainer, f)
    logger.info(f"train_xgboost: model saved to {MODEL_PATH}")

    # Deactivate previous active XGBoost runs
    db.table("model_runs").update({"is_active": False}).eq(
        "model_name", "xgboost"
    ).execute()

    model_version = datetime.now(timezone.utc).strftime("xgb-%Y%m%d-%H%M")
    run_row = {
        "model_name": "xgboost",
        "model_version": model_version,
        "accuracy_score": round(accuracy, 4),
        "training_rows": int(len(df)),
        "training_data_range": (
            f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}"
        ),
        "hyperparameters": {
            "n_estimators": 400,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
        "is_active": True,
        "notes": notes or "XGBoost training — Hero's Initiative Vertical 1",
    }

    result = db.table("model_runs").insert(run_row).execute()
    run_id = result.data[0]["run_id"]
    logger.info(f"train_xgboost: model_runs row inserted — run_id={run_id}")

    # Reset in-memory cache so next inference reloads from disk
    _reset_cache()

    return result.data[0]


# ── Model Cache ────────────────────────────────────────────────────────────────

_cached_model: Optional[xgb.XGBClassifier] = None
_cached_explainer: Optional[shap.TreeExplainer] = None


def _reset_cache():
    global _cached_model, _cached_explainer
    _cached_model = None
    _cached_explainer = None


def _load_model() -> tuple[xgb.XGBClassifier, shap.TreeExplainer]:
    global _cached_model, _cached_explainer
    if _cached_model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                "No trained XGBoost model found in data/models/. "
                "Call train_xgboost() or POST /api/v1/models/train first."
            )
        with open(MODEL_PATH, "rb") as f:
            _cached_model = pickle.load(f)
        with open(EXPLAINER_PATH, "rb") as f:
            _cached_explainer = pickle.load(f)
        logger.info("_load_model: XGBoost model and SHAP explainer loaded from disk")
    return _cached_model, _cached_explainer


# ── Inference ──────────────────────────────────────────────────────────────────


def predict_road(
    road_id: str,
    reading_id: str,
    current_features: dict,
) -> list[dict]:
    """
    Run XGBoost inference for one road across all XGBOOST_HORIZONS.
    Inserts one predictions row per horizon with feature_snapshot and
    shap_values populated. Returns the list of inserted rows.
    """
    model, explainer = _load_model()

    # Build input matrix — shape (1, 13), preserving FEATURES column order
    X = np.array([[current_features[f] for f in FEATURES]], dtype=float)

    # Class probabilities — shape (1, 4)
    proba = model.predict_proba(X)[0]
    predicted_class = int(np.argmax(proba))
    predicted_level = LEVEL_DECODE[predicted_class]
    base_confidence = float(proba[predicted_class])

    # SHAP values for multiclass — returns list of 4 arrays, each shape (1, n_features)
    # We take values for the predicted class to show what drove that specific prediction
    shap_vals_raw = explainer.shap_values(X)
    # XGBoost 2.x returns 3D array (1, n_features, n_classes), older returns list of arrays
    if isinstance(shap_vals_raw, list):
        shap_for_class = shap_vals_raw[predicted_class][0]
    else:
        shap_for_class = shap_vals_raw[0, :, predicted_class]
    shap_dict = {
        FEATURES[i]: round(float(shap_for_class[i]), 6) for i in range(len(FEATURES))
    }

    # Feature snapshot — exact input vector, JSON-serialisable
    feature_snap = {f: _to_python(current_features[f]) for f in FEATURES}

    predicted_ratio = RATIO_MIDPOINT[predicted_level]

    db = _db()
    now = datetime.now(timezone.utc)

    rows = [
        {
            "road_id": road_id,
            "reading_id": reading_id,
            "predicted_at": now.isoformat(),
            "horizon_mins": horizon,
            "predicted_congestion_level": predicted_level,
            "predicted_ratio": predicted_ratio,
            "confidence_score": round(base_confidence * HORIZON_DECAY[horizon], 4),
            "model_used": "xgboost",
            "feature_snapshot": feature_snap,
            "shap_values": shap_dict,
        }
        for horizon in XGBOOST_HORIZONS
    ]

    result = db.table("predictions").insert(rows).execute()
    logger.info(
        f"predict_road: {road_id} → {predicted_level} "
        f"(conf={base_confidence:.3f}, {len(rows)} horizons inserted)"
    )
    return result.data


# ── Feature Builder — called from data_pipeline.py ────────────────────────────


def build_feature_dict(row: dict, history: list[dict]) -> dict:
    """
    Build the current_features dict for a single road segment.

    Args:
        row:     The just-inserted traffic_readings row (as returned by Supabase).
        history: List of the last 96 traffic_readings dicts for this road,
                 ordered oldest-first, NOT including the current row.
                 Each dict must contain 'congestion_ratio'.

    Returns:
        current_features dict ready for predict_road().
    """
    ratios = [r["congestion_ratio"] for r in history]
    n = len(ratios)

    current_ratio = float(row["congestion_ratio"])

    lag_1 = float(ratios[-1]) if n >= 1 else current_ratio
    lag_4 = float(ratios[-4]) if n >= 4 else lag_1
    lag_96 = float(ratios[-96]) if n >= 96 else lag_1

    window = ratios[-4:] if n >= 4 else (ratios if ratios else [current_ratio])
    rolling_mean_4 = float(np.mean(window))
    rolling_std_4 = float(np.std(window)) if len(window) > 1 else 0.0

    return {
        "hour_of_day": int(row["hour_of_day"]),
        "day_of_week": int(row["day_of_week"]),
        "is_weekend": int(bool(row["is_weekend"])),
        "is_ramadan": int(bool(row["is_ramadan"])),
        "is_eid": int(bool(row["is_eid"])),
        "is_monsoon": int(bool(row["is_monsoon"])),
        "road_id_encoded": ROAD_ENCODE.get(row["road_id"], -1),
        "congestion_ratio": current_ratio,
        "lag_1": lag_1,
        "lag_4": lag_4,
        "lag_96": lag_96,
        "rolling_mean_4": rolling_mean_4,
        "rolling_std_4": rolling_std_4,
    }


# ── Accuracy Backfill ──────────────────────────────────────────────────────────


def backfill_accuracy() -> int:
    """
    For every unresolved prediction whose horizon has elapsed, look up the
    nearest actual traffic_readings row and back-fill:
      - actual_congestion_level
      - was_correct

    Returns the number of prediction rows updated.
    """
    db = _db()
    now = datetime.now(timezone.utc)

    pending = (
        db.table("predictions")
        .select(
            "prediction_id,road_id,predicted_at,horizon_mins,predicted_congestion_level"
        )
        .is_("was_correct", "null")
        .execute()
    )

    if not pending.data:
        return 0

    updated = 0
    for pred in pending.data:
        target_time = datetime.fromisoformat(pred["predicted_at"]) + timedelta(
            minutes=pred["horizon_mins"]
        )
        if target_time > now:
            continue  # horizon hasn't elapsed yet

        actual = (
            db.table("traffic_readings")
            .select("congestion_level")
            .eq("road_id", pred["road_id"])
            .gte("timestamp", target_time.isoformat())
            .order("timestamp", desc=False)
            .limit(1)
            .execute()
        )

        if not actual.data:
            continue

        actual_level = actual.data[0]["congestion_level"]
        was_correct = actual_level == pred["predicted_congestion_level"]

        db.table("predictions").update(
            {
                "actual_congestion_level": actual_level,
                "was_correct": was_correct,
            }
        ).eq("prediction_id", pred["prediction_id"]).execute()

        updated += 1

    return updated


# ── Utilities ──────────────────────────────────────────────────────────────────


def _to_python(val):
    """Convert numpy scalar types to JSON-serialisable Python primitives."""
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    return val


def model_is_trained() -> bool:
    """Quick check used by pipeline and health endpoints."""
    return MODEL_PATH.exists() and EXPLAINER_PATH.exists()
