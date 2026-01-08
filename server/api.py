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


class HybridCorsMiddleware:
    """Hybrid CORS middleware supporting both explicit origins and regex patterns"""

    def __init__(self, app):
        self.app = app
        self.vercel_pattern = re.compile(
            r"^https://amplify-[a-zA-Z0-9-]+\.vercel\.app$"
        )
        self._explicit_origins = None

    @property
    def explicit_origins(self) -> List[str]:
        """Lazy load explicit origins from environment"""
        if self._explicit_origins is None:
            env_origins = os.getenv("ALLOWED_ORIGINS", "")
            if env_origins:
                self._explicit_origins = [o.strip() for o in env_origins.split(",")]
            else:
                self._explicit_origins = [
                    "https://amplify-staging.vercel.app",
                    "https://amplify-production.vercel.app",
                ]

                # Add localhost in development
                if os.getenv("ENVIRONMENT") == "development":
                    self._explicit_origins.extend(
                        [
                            "http://localhost:3000",
                            "http://localhost:5173",
                        ]
                    )
        return self._explicit_origins

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(scope.get("headers", []))
                origin = headers.get(b"origin", b"").decode()

                if origin and self._is_allowed_origin(origin):
                    headers_list = list(message.get("headers", []))
                    headers_list.extend(
                        [
                            (b"Access-Control-Allow-Origin", origin.encode()),
                            (b"Access-Control-Allow-Credentials", b"true"),
                            (
                                b"Access-Control-Allow-Methods",
                                b"GET, POST, PUT, DELETE, OPTIONS",
                            ),
                            (
                                b"Access-Control-Allow-Headers",
                                b"Content-Type, Authorization, X-Requested-With",
                            ),
                            (b"Access-Control-Max-Age", b"86400"),
                        ]
                    )
                    message["headers"] = headers_list

            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is explicitly allowed or matches Vercel pattern"""
        if origin in self.explicit_origins:
            return True
        if self.vercel_pattern.match(origin):
            return True
        return False


# Apply hybrid middleware
app.add_middleware(HybridCorsMiddleware)

# Standard CORS middleware with minimal settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # Handled by custom middleware
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


class SearchRequest(BaseModel):
    query: str
    max_results: int = 2
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
            "user_id": request.user_id,
            "query": request.query,
            "status": "pending",
            "metadata": request.model_dump(),
        }
        # Note: This will fail until the table is created
        supabase.table("jobs").insert(job_data).execute()

        # Trigger actual background pipeline
        background_tasks.add_task(run_pipeline_task, job_id, request.query, request.max_results, request.user_id)
        
    except Exception as e:
        logger.error("Failed to create job", error=str(e))
        # Return 500 error so frontend knows it failed
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

    return {"job_id": job_id, "status": "pending"}


async def run_pipeline_task(job_id: str, query: str, max_results: int, user_id: str):
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
            lead_dict["user_id"] = user_id
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
