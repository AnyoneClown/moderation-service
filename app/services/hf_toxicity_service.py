"""
app/services/hf_toxicity_service.py — HuggingFace toxicity detection.

Uses the ``martin-ha/toxic-comment-model`` model via the HuggingFace
Inference API to classify text for toxicity (hate speech, threats,
insults, identity attacks, etc.).

This replaces the OpenAI moderation endpoint with a free,
open-source alternative that requires only an HF API token.
"""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# HuggingFace Inference API URL — toxic comment classifier
HF_TOXICITY_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "martin-ha/toxic-comment-model"
)


async def check_hf_toxicity(text: str) -> dict:
    """
    Classify *text* for toxicity via the HuggingFace toxic-comment model.

    The model outputs labels ``toxic`` and ``non-toxic`` with confidence
    scores.  We return the ``toxic`` probability as the risk score.

    Returns
    -------
    dict
        {
            "score": float | None,   # toxicity probability (0–1)
            "details": list | None,  # raw label/score pairs from the API
            "error": str | None
        }
    """
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping toxicity check.")
        return {"score": None, "details": None, "error": "API token not configured"}

    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}
    payload = {"inputs": text}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(HF_TOXICITY_URL, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()

        # Response format: [[{label, score}, ...]]
        labels: list[dict] = data[0] if isinstance(data, list) and data else data

        # Extract the 'toxic' probability
        toxic_score = 0.0
        for item in labels:
            label = item.get("label", "").lower()
            if label in ("toxic", "label_1"):
                toxic_score = item["score"]
                break

        return {
            "score": round(toxic_score, 6),
            "details": labels,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        logger.error("HuggingFace Toxicity API HTTP error: %s", exc.response.text)
        return {"score": None, "details": None, "error": f"HTTP {exc.response.status_code}"}

    except Exception as exc:
        logger.error("HuggingFace Toxicity API call failed: %s", exc)
        return {"score": None, "details": None, "error": str(exc)}
