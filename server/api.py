import os
import re
import uuid
from typing import Any, Dict, List, Optional

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.db import supabase

# Configure logging
logger = structlog.get_logger()

app = FastAPI(title="B2B Lead Gen API")



def get_cors_regex() -> str:
    """Generate regex for ALLOWED_ORIGINS + Vercel wildcard"""
    # Base pattern for Vercel preview/staging URLs
    patterns = [r"https://amplify-[a-zA-Z0-9-]+\.vercel\.app"]
    
    # Add explicit origins from env
    env_origins = os.getenv("ALLOWED_ORIGINS", "")
    if env_origins:
        for origin in env_origins.split(","):
            if origin.strip():
                patterns.append(re.escape(origin.strip()))
    
    # Add localhost for dev
    if os.getenv("ENVIRONMENT") == "development":
        patterns.extend([
            r"http://localhost:3000",
            r"http://localhost:5173"
        ])
        
    return f"^({'|'.join(patterns)})$"


# Configure CORS with dynamic regex to handle both wildcards and explicit domains
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=get_cors_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    country: Optional[str] = None
    user_id: str


@app.get("/")
async def root():
    return {"status": "ok", "service": "b2b-pipeline-api"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Azure/Container probes"""
    try:
        # Lightweight DB check
        # Lightweight DB check
        status = supabase.table("jobs").select("count", count="exact").limit(0).execute()
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
            "user_id": request.user_id,
            "query": request.query,
            "status": "pending",
            "metadata": request.model_dump(),
        }
        # Note: This will fail until the table is created
        supabase.table("jobs").insert(job_data).execute()

        # Trigger actual background pipeline
        background_tasks.add_task(
            run_pipeline_task, job_id, request.query, request.max_results
        )

    except Exception as e:
        logger.error("Failed to create job", error=str(e))
        # For now, return success mock if DB fails (since table might not exist yet)
        # Return 500 error so frontend knows it failed
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

    return {"job_id": job_id, "status": "pending"}


async def run_pipeline_task(job_id: str, query: str, max_results: int):
    """
    Background task to run the B2B pipeline and persist results.
    """
    import datetime

    from models.lead import LeadProfile
    from pipelines.b2b_lead_pipeline import B2BLeadPipeline, PipelineConfig

    logger.info("Starting background pipeline task", job_id=job_id)

    try:
        # Update job status to running
        supabase.table("jobs").update({"status": "running"}).eq("id", job_id).execute()

        config = PipelineConfig(
            query=query,
            max_results=max_results,
            # Ensure settings path is correct for container environment
            # In container, app is in /app, so settings should be in /app/config/settings.yaml
            settings_path="config/settings.yaml",
        )

        async with B2BLeadPipeline(config) as pipeline:
            result_batch = await pipeline.run_pipeline()

        # Persist leads to Supabase
        leads_data = []
        for lead in result_batch.leads:
            # Convert LeadProfile to dict and add job_id
            lead_dict = lead.model_dump()
            lead_dict["job_id"] = job_id
            # Clean up fields that might not match schema 1:1 if needed,
            # but schema.sql suggests broad compatibility (jsonb metadata)
            leads_data.append(lead_dict)

        if leads_data:
            # Batch insert leads
            supabase.table("leads").insert(leads_data).execute()

        # Update job completion status
        supabase.table("jobs").update(
            {
                "status": "completed",
                "completed_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                "result_count": len(result_batch.leads),
                "metadata": result_batch.metadata,
            }
        ).eq("id", job_id).execute()

        logger.info(
            "Pipeline task completed successfully",
            job_id=job_id,
            count=len(result_batch.leads),
        )

    except Exception as e:
        logger.error("Pipeline task failed", job_id=job_id, error=str(e))
        # Update job error status
        supabase.table("jobs").update(
            {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
        ).eq("id", job_id).execute()


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
            return {
                "id": job_id,
                "status": "mock_pending",
                "error": "Table 'jobs' does not exist",
            }
        raise HTTPException(status_code=500, detail=str(e))
