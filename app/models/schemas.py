from typing import Any, Optional
from pydantic import BaseModel


class PredictionRequest(BaseModel):
    features: list[float]
    model_name: str = "default"


class PredictionResponse(BaseModel):
    prediction: Any
    model_name: str
    confidence: Optional[float] = None


class PipelineRequest(BaseModel):
    data: list[dict[str, Any]]
    pipeline_name: str = "default"


class PipelineResponse(BaseModel):
    processed_data: list[dict[str, Any]]
    pipeline_name: str
    records_processed: int
    status: str


class DataIngestionRequest(BaseModel):
    source: str
    data: list[dict[str, Any]]


class DataIngestionResponse(BaseModel):
    status: str
    records_ingested: int
    message: str
