"""Schemas for alert banners and notification subscriptions."""

from typing import Literal

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    location: str
    alert_level: str
    headline: str
    updated_at: str


class SubscriptionRequest(BaseModel):
    contact: str = Field(..., min_length=3, max_length=120)
    channel: Literal["whatsapp", "sms", "web"] = "whatsapp"
    location: str = Field(..., min_length=1, max_length=160)
    role: Literal["farmer", "fisherman", "disaster_team", "citizen"] = "citizen"