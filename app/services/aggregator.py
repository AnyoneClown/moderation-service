"""
app/services/aggregator.py — Scoring aggregator & decision engine.

Combines results from **five text** moderation sources (and optionally
an **image analysis** source) into a single weighted score and maps it
to a human-readable status: APPROVED, FLAGGED, or REJECTED.

Text scoring weights (when no image):
    ┌─────────────────────┬────────┐
    │ Source               │ Weight │
    ├─────────────────────┼────────┤
    │ HuggingFace Toxicity │  0.25  │
    │ HuggingFace Spam     │  0.20  │
    │ Profanity Filter     │  0.20  │
    │ Fraud Detector       │  0.25  │
    │ Sentiment (VADER)    │  0.10  │
    └─────────────────────┴────────┘

When an image is also provided, the final score is:
    final = 0.60 × text_score + 0.40 × image_score

Decision thresholds:
    score < 0.25  → APPROVED
    score < 0.55  → FLAGGED
    score ≥ 0.55  → REJECTED

If an external API is unavailable the weight is redistributed among
the remaining sources so that the final score is still on a 0–1 scale.
"""

import asyncio
import logging
from typing import Optional

from app.services.hf_service import check_hf_spam
from app.services.hf_toxicity_service import check_hf_toxicity
from app.services.profanity_service import check_profanity
from app.services.fraud_service import check_fraud
from app.services.sentiment_service import check_sentiment
from app.services.image_service import analyze_image

logger = logging.getLogger(__name__)

# ── Weight configuration (text sources) ──
WEIGHTS = {
    "toxicity": 0.25,
    "spam": 0.20,
    "profanity": 0.20,
    "fraud": 0.25,
    "sentiment": 0.10,
}

# When both text + image are provided
TEXT_IMAGE_BLEND = 0.60   # text weight
IMAGE_BLEND = 0.40        # image weight

# ── Decision thresholds ──
THRESHOLD_APPROVED = 0.25
THRESHOLD_FLAGGED = 0.55  # scores ≥ this are REJECTED


async def _run_text_checks(text: str) -> tuple[dict, dict, dict, dict, dict, bool, float]:
    """
    Execute the five text moderation checks concurrently and compute
    the weighted text score.

    Returns
    -------
    (toxicity_result, spam_result, profanity_result, fraud_result,
     sentiment_result, is_partial, text_final_score)
    """
    toxicity_result, spam_result, profanity_result, fraud_result, sentiment_result = (
        await asyncio.gather(
            check_hf_toxicity(text),
            check_hf_spam(text),
            check_profanity(text),
            check_fraud(text),
            check_sentiment(text),
        )
    )

    sources: dict[str, float] = {}
    is_partial = False

    if toxicity_result["score"] is not None:
        sources["toxicity"] = toxicity_result["score"]
    else:
        is_partial = True
        logger.warning("Toxicity result unavailable — partial scoring.")

    if spam_result["score"] is not None:
        sources["spam"] = spam_result["score"]
    else:
        is_partial = True
        logger.warning("Spam result unavailable — partial scoring.")

    sources["profanity"] = profanity_result["score"]
    sources["fraud"] = fraud_result["score"]
    sources["sentiment"] = sentiment_result["score"]

    active_weight_sum = sum(WEIGHTS[src] for src in sources)
    if active_weight_sum == 0:
        text_score = profanity_result["score"]
    else:
        text_score = sum(
            (WEIGHTS[src] / active_weight_sum) * score
            for src, score in sources.items()
        )
    text_score = round(text_score, 4)

    return (
        toxicity_result, spam_result, profanity_result,
        fraud_result, sentiment_result, is_partial, text_score,
    )


async def aggregate_moderation(
    text: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
) -> dict:
    """
    Run text and/or image moderation checks **concurrently** and
    produce a combined moderation verdict.

    Parameters
    ----------
    text : str, optional
        Text content to moderate.
    image_bytes : bytes, optional
        Raw image bytes to moderate.

    At least one of ``text`` or ``image_bytes`` must be provided.

    Returns
    -------
    dict  (ready to be stored in the DB and rendered on the frontend)
    """

    has_text = bool(text and text.strip())
    has_image = bool(image_bytes)

    # ── Determine input type ──
    if has_text and has_image:
        input_type = "both"
    elif has_image:
        input_type = "image"
    else:
        input_type = "text"

    # ── Placeholders ──
    _empty = {"score": None, "details": None, "error": "Not applicable"}
    toxicity_result = spam_result = profanity_result = fraud_result = sentiment_result = _empty
    image_result: Optional[dict] = None
    is_partial = False
    text_score = 0.0
    image_score = 0.0

    # ── Run checks ──
    if has_text and has_image:
        (
            toxicity_result, spam_result, profanity_result,
            fraud_result, sentiment_result, text_partial, text_score,
        ), image_result = await asyncio.gather(
            _run_text_checks(text),
            analyze_image(image_bytes),
        )
        is_partial = text_partial or image_result.get("is_partial", False)
        image_score = image_result["combined_score"]
        final_score = round(TEXT_IMAGE_BLEND * text_score + IMAGE_BLEND * image_score, 4)

    elif has_text:
        (
            toxicity_result, spam_result, profanity_result,
            fraud_result, sentiment_result, is_partial, text_score,
        ) = await _run_text_checks(text)
        final_score = text_score

    else:  # image only
        image_result = await analyze_image(image_bytes)
        is_partial = image_result.get("is_partial", False)
        image_score = image_result["combined_score"]
        final_score = image_score

    # ── Map score to decision status ──
    if final_score < THRESHOLD_APPROVED:
        status = "APPROVED"
    elif final_score < THRESHOLD_FLAGGED:
        status = "FLAGGED"
    else:
        status = "REJECTED"

    return {
        "text": text or "",
        "input_type": input_type,
        "toxicity": toxicity_result,
        "spam": spam_result,
        "profanity": profanity_result,
        "fraud": fraud_result,
        "sentiment": sentiment_result,
        "image": image_result,
        "final_score": final_score,
        "status": status,
        "is_partial": is_partial,
    }
