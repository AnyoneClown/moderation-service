"""
app/services/aggregator.py — Scoring aggregator & decision engine.

Combines results from **five** moderation sources into a single
weighted score and maps it to a human-readable status:
APPROVED, FLAGGED, or REJECTED.

Scoring weights:
    ┌─────────────────────┬────────┐
    │ Source               │ Weight │
    ├─────────────────────┼────────┤
    │ HuggingFace Toxicity │  0.25  │
    │ HuggingFace Spam     │  0.20  │
    │ Profanity Filter     │  0.20  │
    │ Fraud Detector       │  0.25  │
    │ Sentiment (VADER)    │  0.10  │
    └─────────────────────┴────────┘

Decision thresholds:
    score < 0.25  → APPROVED
    score < 0.55  → FLAGGED
    score ≥ 0.55  → REJECTED

If an external API is unavailable the weight is redistributed among
the remaining sources so that the final score is still on a 0–1 scale.
"""

import asyncio
import logging
from app.services.hf_service import check_hf_spam
from app.services.hf_toxicity_service import check_hf_toxicity
from app.services.profanity_service import check_profanity
from app.services.fraud_service import check_fraud
from app.services.sentiment_service import check_sentiment

logger = logging.getLogger(__name__)

# ── Weight configuration ──
WEIGHTS = {
    "toxicity": 0.25,
    "spam": 0.20,
    "profanity": 0.20,
    "fraud": 0.25,
    "sentiment": 0.10,
}

# ── Decision thresholds ──
THRESHOLD_APPROVED = 0.25
THRESHOLD_FLAGGED = 0.55  # scores ≥ this are REJECTED


async def aggregate_moderation(text: str) -> dict:
    """
    Run all five checks **concurrently** via ``asyncio.gather`` and
    produce a combined moderation verdict.

    Returns
    -------
    dict  (ready to be stored in the DB and rendered on the frontend)
    """

    # ── 1. Fire all checks simultaneously ──
    toxicity_result, spam_result, profanity_result, fraud_result, sentiment_result = (
        await asyncio.gather(
            check_hf_toxicity(text),
            check_hf_spam(text),
            check_profanity(text),
            check_fraud(text),
            check_sentiment(text),
        )
    )

    # ── 2. Determine which sources returned valid scores ──
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

    # Local services — should always succeed
    sources["profanity"] = profanity_result["score"]
    sources["fraud"] = fraud_result["score"]
    sources["sentiment"] = sentiment_result["score"]

    # ── 3. Compute weighted score (redistribute missing weights) ──
    active_weight_sum = sum(WEIGHTS[src] for src in sources)
    if active_weight_sum == 0:
        final_score = profanity_result["score"]
    else:
        final_score = sum(
            (WEIGHTS[src] / active_weight_sum) * score
            for src, score in sources.items()
        )
    final_score = round(final_score, 4)

    # ── 4. Map score to decision status ──
    if final_score < THRESHOLD_APPROVED:
        status = "APPROVED"
    elif final_score < THRESHOLD_FLAGGED:
        status = "FLAGGED"
    else:
        status = "REJECTED"

    return {
        "text": text,
        "toxicity": toxicity_result,
        "spam": spam_result,
        "profanity": profanity_result,
        "fraud": fraud_result,
        "sentiment": sentiment_result,
        "final_score": final_score,
        "status": status,
        "is_partial": is_partial,
    }
