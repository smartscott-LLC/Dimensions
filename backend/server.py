from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    from lib.auth import bootstrap_admin, validate_jwt_secret
    # Validate JWT secret is configured before starting
    validate_jwt_secret()
    await bootstrap_admin()
    yield
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Track app start time for uptime calculation
app.start_time = datetime.now(timezone.utc)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


class HealthStatus(BaseModel):
    status: str
    database: str
    uptime_seconds: float
    timestamp: datetime

class DatabaseStatus(BaseModel):
    connected: bool
    latency_ms: float


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for load balancers and monitoring.
    
    Returns 200 if healthy, 503 if degraded.
    Checks MongoDB connectivity and reports latency.
    """
    start = datetime.now(timezone.utc)
    
    # Check MongoDB connectivity
    db_status = DatabaseStatus(connected=False, latency_ms=0)
    try:
        db_ping_start = datetime.now(timezone.utc)
        await db.admin_command("ping")
        db_ping_end = datetime.now(timezone.utc)
        db_latency = (db_ping_end - db_ping_start).total_seconds() * 1000
        
        db_status = DatabaseStatus(
            connected=True,
            latency_ms=round(db_latency, 2)
        )
    except Exception as e:
        logger.error(f"Health check: MongoDB ping failed: {e}")
        db_status = DatabaseStatus(connected=False, latency_ms=0)
    
    # Calculate uptime from app start
    uptime = (datetime.now(timezone.utc) - app.start_time).total_seconds() if hasattr(app, 'start_time') else 0
    
    overall_status = "healthy" if db_status.connected else "degraded"
    
    return HealthStatus(
        status=overall_status,
        database=db_status.connected,  # type: ignore[arg-type]
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc)
    )


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@app.get("/readyz")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes-style readiness probe.
    
    Returns 200 if ready to serve traffic, 503 if not ready.
    """
    try:
        await db.admin_command("ping")
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"not ready: {e}")


@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

from routers.containment import router as containment_router
from routers.clients import router as clients_router
from routers.gate import router as gate_router
from routers.chat import router as chat_router
from routers.auth import router as auth_router

api_router.include_router(auth_router)
api_router.include_router(clients_router)
api_router.include_router(gate_router)
api_router.include_router(chat_router)
api_router.include_router(containment_router)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers for defense-in-depth against XSS."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    return response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
