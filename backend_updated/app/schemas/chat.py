"""
Chat API schemas — request and response models for /api/chat.
"""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request from frontend or WhatsApp."""
    message: str = Field(..., min_length=1, max_length=2000, description="User's natural-language question")
    role: Literal["farmer", "fisherman", "disaster_team", "citizen"] = Field(
        "citizen", description="User's role — affects phrasing and focus"
    )
    location: str = Field(..., min_length=1, max_length=160, description="Location name (e.g. 'Shimla, Himachal Pradesh')")
    language: Literal[
        "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur", "or", "as"
    ] = Field("en", description="Supported ISO 639-1 language code")


class ChatResponse(BaseModel):
    """Chat response returned to the client."""
    reply: str = Field(..., description="Natural-language answer")
    alert_level: str = Field(..., description="Current alert level for the location: Red/Orange/Yellow/None")
    language: str = Field(..., description="Language of the reply")
    sources: List[str] = Field(default_factory=list, description="Source identifiers used")
    data_as_of: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of the weather data used"
    )
