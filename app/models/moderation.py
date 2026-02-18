"""
app/models/moderation.py — SQLAlchemy ORM model for moderation history.

Every moderation request is persisted here with:
  - original text
  - per-source scores (toxicity, spam, profanity, fraud, sentiment)
  - aggregated final verdict
  - timestamp
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ModerationRecord(Base):
    """Stores one moderation request and its analysis results."""

    __tablename__ = "moderation_records_v2"

    # Primary key — UUID for globally unique, non-sequential IDs
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Input ──
    text = Column(Text, nullable=True, comment="Original text submitted for moderation")
    input_type = Column(String(10), nullable=False, default="text", comment="'text' only")

    # ── Per-source scores (0.0 – 1.0 risk scale) ──
    toxicity_score = Column(Float, nullable=True, comment="Toxicity score from HuggingFace model")
    spam_score = Column(Float, nullable=True, comment="Spam probability from HuggingFace model")
    profanity_score = Column(Float, nullable=True, default=0.0, comment="Profanity severity (0.0–1.0)")
    fraud_score = Column(Float, nullable=True, default=0.0, comment="Fraud/phishing risk score")
    sentiment_score = Column(Float, nullable=True, default=0.0, comment="Negative-sentiment risk score")

    # ── Detailed JSON payloads from each provider ──
    toxicity_details = Column(JSON, nullable=True, comment="Full HuggingFace toxicity response")
    spam_details = Column(JSON, nullable=True, comment="Full HuggingFace spam response")
    profanity_details = Column(JSON, nullable=True, comment="Profanity analysis breakdown")
    fraud_details = Column(JSON, nullable=True, comment="Fraud pattern matches")
    sentiment_details = Column(JSON, nullable=True, comment="VADER sentiment breakdown")

    # ── Aggregated result ──
    final_score = Column(Float, nullable=False, comment="Weighted aggregate score")
    status = Column(String(20), nullable=False, comment="APPROVED | FLAGGED | REJECTED")
    is_partial = Column(String(5), nullable=False, default="false", comment="'true' if any external API failed")

    # ── X-Ray explainability ──
    xray_html = Column(Text, nullable=True, comment="HTML with colour-coded triggered-word highlights")

    # ── Metadata ──
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp of the moderation request",
    )

    def __repr__(self) -> str:
        return f"<ModerationRecord id={self.id} status={self.status}>"
