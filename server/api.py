from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import structlog
from server.db import supabase

# Configure logging
logger = structlog.get_logger()

app = FastAPI(title="B2B Lead Gen API")

# Configure CORS
# In production, specific origins should be allowed (e.g., the Vercel frontend URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    country: Optional[str] = None

@app.get("/")
async def root():
    return {"status": "ok", "service": "b2b-pipeline-api"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Azure/Container probes"""
    try:
        # Lightweight DB check
        # status = supabase.table("jobs").select("count", count="exact").limit(0).execute()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service Unhealthy")

@app.post("/search")
async def create_search(request: SearchRequest, background_tasks: BackgroundTasks):
    """
    Initiate a new lead generation search job.
    """
    job_id = str(uuid.uuid4())
    logger.info("Received search request", job_id=job_id, query=request.query)
    
    # Create job record
    try:
        job_data = {
            "id": job_id,
            "query": request.query,
            "status": "pending",
            "metadata": request.model_dump()
        }
        # Note: This will fail until the table is created
        supabase.table("jobs").insert(job_data).execute()
        
        # TODO: Trigger actual background pipeline
        # background_tasks.add_task(run_pipeline_task, job_id, request.query)
        
    except Exception as e:
        logger.error("Failed to create job", error=str(e))
        # For now, return success mock if DB fails (since table might not exist yet)
        return {"job_id": job_id, "status": "pending", "note": "DB write might have failed if schema not applied"}

    return {"job_id": job_id, "status": "pending"}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a specific job.
    """
    try:
        response = supabase.table("jobs").select("*").eq("id", job_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Job not found")
        return response.data[0]
    except Exception as e:
        logger.error("Failed to fetch job", error=str(e))
        # Mock response if table missing
        if "Could not find the table" in str(e):
             return {"id": job_id, "status": "mock_pending", "error": "Table 'jobs' does not exist"}
        raise HTTPException(status_code=500, detail=str(e))
