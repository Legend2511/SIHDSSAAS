"""
Health check endpoint.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Simple health check — confirms the API is running."""
    return {"status": "ok"}
