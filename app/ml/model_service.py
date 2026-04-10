import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(self):
        self._models: dict[str, Any] = {}
        self._scalers: dict[str, StandardScaler] = {}
        self._setup_default_model()

    def _setup_default_model(self):
        np.random.seed(42)
        X_train = np.random.randn(200, 4)
        y_train = (X_train[:, 0] + X_train[:, 1] > 0).astype(int)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)

        model = LogisticRegression(random_state=42)
        model.fit(X_scaled, y_train)

        self._models["default"] = model
        self._scalers["default"] = scaler
        logger.info("Default ML model initialized.")

    def predict(self, features: list[float], model_name: str = "default") -> dict[str, Any]:
        if model_name not in self._models:
            raise ValueError(f"Model '{model_name}' not found. Available: {list(self._models.keys())}")

        model = self._models[model_name]
        scaler = self._scalers.get(model_name)

        X = np.array(features).reshape(1, -1)
        if scaler:
            X = scaler.transform(X)

        prediction = model.predict(X)[0]
        probabilities = model.predict_proba(X)[0]
        confidence = float(max(probabilities))

        return {
            "prediction": int(prediction),
            "model_name": model_name,
            "confidence": confidence,
        }

    def list_models(self) -> list[str]:
        return list(self._models.keys())


model_service = ModelService()
