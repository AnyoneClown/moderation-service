"""
app/services/hf_service.py — Hugging Face Inference API: spam detection.

Uses the ``mrm8488/bert-tiny-finetuned-sms-spam-detection`` model to
classify text as **spam** or **ham** (not spam).

The Inference API is free for public models within rate limits.
"""

import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Hugging Face serverless Inference API URL for the spam-detection model
# Updated to the new router URL format
HF_MODEL_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "mrm8488/bert-tiny-finetuned-sms-spam-detection"
)


async def check_hf_spam(text: str) -> dict:
    """
    Classify *text* via the Hugging Face spam-detection model.

    Returns
    -------
    dict
        {
            "score": float,       # probability that the text is spam (0-1)
            "details": [...],     # raw label/score pairs from the API
            "error": str | None
        }
    """
    # Guard: skip if no token is provided
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping spam check.")
        return {"score": None, "details": None, "error": "API token not configured"}

    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}
    payload = {"inputs": text}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(HF_MODEL_URL, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()

        # The API returns [[{label, score}, ...]] — flatten the outer list
        labels: list[dict] = data[0] if isinstance(data, list) and data else data

        # Extract the spam probability
        spam_score = 0.0
        for item in labels:
            label = item.get("label", "").upper()
            if label in ("SPAM", "LABEL_1"):
                spam_score = item["score"]
                break

        return {
            "score": round(spam_score, 6),
            "details": labels,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        logger.error("HuggingFace API HTTP error: %s", exc.response.text)
        return {"score": None, "details": None, "error": f"HTTP {exc.response.status_code}"}

    except Exception as exc:
        logger.error("HuggingFace API call failed: %s", exc)
        return {"score": None, "details": None, "error": str(exc)}
