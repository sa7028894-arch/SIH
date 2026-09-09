from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str

@router.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint to verify backend service status."""
    return HealthResponse(
        status="ok",
        service="FastAPI Backend",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
