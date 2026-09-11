"""Alert banner and notification subscription endpoints."""

import logging

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.schemas.alerts import AlertResponse, SubscriptionRequest
from app.services.database import add_subscription, get_subscriptions
from app.services.ingestion import get_weather_for_location
from app.core.config import settings

router = APIRouter(tags=["alerts"])
logger = logging.getLogger(__name__)


@router.get("/alerts", response_model=AlertResponse)
async def current_alert(location: str = Query(..., min_length=1, max_length=160)):
    """Return the current normalized alert for a location."""
    try:
        weather = await get_weather_for_location(location)
    except Exception as exc:
        logger.exception("Weather source failed for location %s", location)
        raise HTTPException(status_code=502, detail="Weather data is temporarily unavailable.") from exc

    return AlertResponse(
        location=weather.location,
        alert_level=weather.alert_level.value,
        headline=weather.alert_headline or "No significant weather warning",
        updated_at=weather.timestamp.isoformat(),
    )


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(request: SubscriptionRequest):
    """Subscribe a contact to location alert notifications."""
    try:
        return await add_subscription(
            contact=request.contact,
            channel=request.channel,
            location=request.location,
            role=request.role,
        )
    except Exception as exc:
        logger.exception("Could not save subscription")
        raise HTTPException(status_code=500, detail="Could not save the subscription.") from exc

@router.get("/alerts/subscriptions")
async def subscriptions(
    location: str | None = Query(default=None, max_length=160),
    x_admin_key: str | None = Header(default=None),
):
    """List sanitized subscriptions for explicitly authorized local administration."""
    if not settings.admin_api_key:
        raise HTTPException(status_code=404, detail="Not found")
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    records = await get_subscriptions(location)
    sanitized = [
        {
            "id": record["id"],
            "channel": record["channel"],
            "location": record["location"],
            "role": record["role"],
            "created_at": record["created_at"],
        }
        for record in records
    ]
    return {"subscriptions": sanitized}