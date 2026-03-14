"""
app/services/hf_toxicity_service.py — HuggingFace toxicity detection.

Uses the ``textdetox/xlmr-large-toxicity-classifier`` model via the
HuggingFace Inference API to classify text for toxicity (hate speech,
threats, insults, identity attacks, etc.).

This multilingual model (XLM-RoBERTa) supports 100+ languages including
English and Ukrainian.
"""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# HuggingFace Inference API URL — multilingual toxicity classifier
# XLM-RoBERTa based model that supports 100+ languages incl. Ukrainian
HF_TOXICITY_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "unitary/multilingual-toxic-xlm-roberta"
)


async def check_hf_toxicity(text: str) -> dict:
    """
    Classify *text* for toxicity via the HuggingFace multilingual model.

    The model outputs labels ``toxic`` and ``neutral`` with confidence
    scores.  We return the ``toxic`` probability as the risk score.
    Supports English, Ukrainian and 100+ other languages.

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
        # Different models use different label names
        toxic_score = 0.0
        for item in labels:
            label = item.get("label", "").lower()
            if label in ("toxic", "label_1", "1"):
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
