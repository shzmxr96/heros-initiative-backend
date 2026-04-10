# Hero's Initiative Backend

FastAPI backend service with ML models and data pipeline processing.

## Architecture

- **Framework**: FastAPI (Python 3.11)
- **Server**: Uvicorn (dev) / Gunicorn (production)
- **ML**: scikit-learn, numpy
- **Data**: pandas
- **Port**: 5000

## Project Structure

```
main.py                  # FastAPI app entry point
app/
  api/
    routes.py            # API route handlers
  core/
    config.py            # Settings / configuration (pydantic-settings)
  models/
    schemas.py           # Pydantic request/response schemas
  ml/
    model_service.py     # ML model management and inference
  pipeline/
    data_pipeline.py     # Data pipeline processing (default, normalize, filter)
```

## API Endpoints

- `GET /` - Root, returns status
- `GET /health` - Health check
- `GET /docs` - Interactive Swagger UI
- `GET /api/v1/models` - List available ML models
- `POST /api/v1/predict` - Run ML prediction
- `GET /api/v1/pipelines` - List available data pipelines
- `POST /api/v1/pipeline/run` - Run a data pipeline
- `POST /api/v1/data/ingest` - Ingest data

## Running Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

## Dependencies

Managed via `pyproject.toml` using uv:
- fastapi
- uvicorn[standard]
- gunicorn
- pydantic
- pydantic-settings
- scikit-learn
- pandas
- numpy
- httpx
- python-multipart
