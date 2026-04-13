import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_pipeline_loop():
    """Runs the data pipeline every 15 minutes in the background."""
    from app.pipeline.data_pipeline import run_pipeline
    while True:
        try:
            logger.info("Scheduler: running pipeline...")
            run_pipeline()
            logger.info("Scheduler: pipeline complete. Next run in 15 minutes.")
        except Exception as e:
            logger.error(f"Scheduler: pipeline failed — {e}")
        await asyncio.sleep(15 * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Hero's Initiative backend...")
    task = asyncio.create_task(run_pipeline_loop())
    yield
    task.cancel()
    logger.info("Scheduler stopped.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Powered Traffic Prediction & Congestion Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "message": "Hero's Initiative Backend API",
        "status": "running",
        "docs": "/docs",
        "scheduler": "active — pipeline runs every 15 minutes"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "scheduler": "active"}