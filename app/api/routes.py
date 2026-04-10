from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    PredictionRequest,
    PredictionResponse,
    PipelineRequest,
    PipelineResponse,
    DataIngestionRequest,
    DataIngestionResponse,
)
from app.ml.model_service import model_service
from app.pipeline.data_pipeline import data_pipeline

router = APIRouter()


@router.get("/models", summary="List available ML models")
def list_models():
    return {"models": model_service.list_models()}


@router.post("/predict", response_model=PredictionResponse, summary="Run ML prediction")
def predict(request: PredictionRequest):
    try:
        result = model_service.predict(request.features, request.model_name)
        return PredictionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/pipelines", summary="List available data pipelines")
def list_pipelines():
    return {"pipelines": data_pipeline.list_pipelines()}


@router.post("/pipeline/run", response_model=PipelineResponse, summary="Run a data pipeline")
def run_pipeline(request: PipelineRequest):
    try:
        result = data_pipeline.run(request.data, request.pipeline_name)
        return PipelineResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@router.post("/data/ingest", response_model=DataIngestionResponse, summary="Ingest data")
def ingest_data(request: DataIngestionRequest):
    try:
        return DataIngestionResponse(
            status="success",
            records_ingested=len(request.data),
            message=f"Successfully ingested {len(request.data)} records from source '{request.source}'",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
