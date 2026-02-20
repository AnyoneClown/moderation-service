"""
app/services/fraud_service.py — AI-powered fraud & phishing detection.

Uses a multilingual zero-shot classification model (XLM-RoBERTa) via
the HuggingFace Inference API to detect fraud/scam/phishing indicators
in text.

Detection categories (evaluated by the model):
  1. Financial scams   — investment fraud, guaranteed profits, crypto scams
  2. Phishing          — credential harvesting, account verification requests
  3. Urgency/pressure  — "act now", "limited time", deadline pressure
  4. Personal info     — requests for SSN, credit card, bank details
  5. Lottery/prize     — "you have won", "claim your prize"
  6. Advance fee       — processing fees, send money upfront
  7. Impersonation     — fake authority / government officials

The model scores each category independently (multi-label zero-shot
classification).  The final fraud risk score is derived from the
highest fraud-category probability.  Supports 100+ languages including
English and Ukrainian via the XLM-RoBERTa backbone.
"""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Model endpoint ───────────────────────────────────────────
# Multilingual zero-shot classification model (XLM-RoBERTa fine-tuned
# on XNLI).  Supports 100+ languages including English and Ukrainian.
HF_ZERO_SHOT_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "joeddav/xlm-roberta-large-xnli"
)

# ── Candidate labels for zero-shot fraud detection ───────────
# Each label becomes a hypothesis the NLI model evaluates against
# the input text.  Phrased as natural-language descriptions so the
# model can leverage its understanding of entailment.
_FRAUD_LABELS = [
    "financial scam or investment fraud",
    "phishing or credential theft",
    "urgency or pressure tactics",
    "request for personal or financial information",
    "lottery or prize scam",
    "advance fee fraud",
    "impersonation of authority or government",
]

_LEGITIMATE_LABEL = "legitimate ordinary message"

_ALL_LABELS = _FRAUD_LABELS + [_LEGITIMATE_LABEL]

# Short keys used in the details dict and by the aggregator
_LABEL_TO_KEY: dict[str, str] = {
    "financial scam or investment fraud": "financial_scam",
    "phishing or credential theft": "phishing",
    "urgency or pressure tactics": "urgency",
    "request for personal or financial information": "pii_request",
    "lottery or prize scam": "lottery_scam",
    "advance fee fraud": "advance_fee",
    "impersonation of authority or government": "impersonation",
}

# Minimum confidence for a category to be considered "matched"
_CATEGORY_THRESHOLD = 0.30


async def check_fraud(text: str) -> dict:
    """
    Classify *text* for fraud/scam/phishing via HuggingFace zero-shot
    classification.

    Returns
    -------
    dict
        {
            "score": float | None,       # fraud risk score (0.0–1.0)
            "flagged": bool,             # True if any fraud category matched
            "matched_categories": list,  # categories above threshold
            "details": dict | None,      # per-category score breakdown
            "triggered_words": list,     # always [] (AI has no word spans)
            "error": str | None
        }
    """
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping fraud check.")
        return {
            "score": None,
            "flagged": False,
            "matched_categories": [],
            "details": None,
            "triggered_words": [],
            "error": "API token not configured",
        }

    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}
    payload = {
        "inputs": text,
        "parameters": {
            "candidate_labels": _ALL_LABELS,
            "multi_label": True,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                HF_ZERO_SHOT_URL, json=payload, headers=headers,
            )
            response.raise_for_status()

        data = response.json()

        labels: list[str] = data.get("labels", [])
        scores: list[float] = data.get("scores", [])

        # Build per-category score breakdown (using short keys)
        category_scores: dict[str, float] = {}
        matched_categories: list[str] = []
        max_fraud_score = 0.0
        legitimate_score = 0.0

        for label, score in zip(labels, scores):
            if label == _LEGITIMATE_LABEL:
                category_scores["legitimate"] = round(score, 4)
                legitimate_score = score
                continue

            key = _LABEL_TO_KEY.get(label, label)
            category_scores[key] = round(score, 4)

            if score > max_fraud_score:
                max_fraud_score = score

            # A category is only "matched" when it exceeds both the
            # absolute threshold AND the legitimate score — this stops
            # benign messages from accumulating false-positive categories.
            if score >= _CATEGORY_THRESHOLD and score > legitimate_score:
                matched_categories.append(key)

        # Dampen the raw fraud score by how legitimate the model
        # considers the message.  This prevents innocuous text from
        # being flagged just because zero-shot NLI distributes some
        # probability mass across fraud labels.
        fraud_score = min(max_fraud_score * (1.0 - legitimate_score), 1.0)

        return {
            "score": round(fraud_score, 4),
            "flagged": len(matched_categories) > 0,
            "matched_categories": sorted(matched_categories),
            "details": category_scores,
            "triggered_words": [],
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        logger.error("HuggingFace Fraud API HTTP error: %s", exc.response.text)
        return {
            "score": None,
            "flagged": False,
            "matched_categories": [],
            "details": None,
            "triggered_words": [],
            "error": f"HTTP {exc.response.status_code}",
        }

    except Exception as exc:
        logger.error("HuggingFace Fraud API call failed: %s", exc)
        return {
            "score": None,
            "flagged": False,
            "matched_categories": [],
            "details": None,
            "triggered_words": [],
            "error": str(exc),
        }
