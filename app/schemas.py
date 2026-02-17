"""
app/schemas.py — Pydantic schemas for request/response validation.

Keeps the API contract separate from the ORM models.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class ModerationRequest(BaseModel):
    """Incoming moderation request from the frontend form."""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to moderate")


class ModerationResponse(BaseModel):
    """Serialised moderation result returned to the client."""
    id: str
    text: str
    openai_score: Optional[float]
    hf_spam_score: Optional[float]
    profanity_flag: float
    openai_details: Optional[Any]
    hf_details: Optional[Any]
    final_score: float
    status: str
    is_partial: str
    created_at: datetime

    class Config:
        from_attributes = True
