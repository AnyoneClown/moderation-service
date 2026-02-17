"""
app/services/image_service.py — Image content analysis.

Uses HuggingFace Inference API models for:
  1. NSFW / inappropriate content detection  (Falconsai/nsfw_image_detection)
  2. Image captioning for contextual analysis (Salesforce/blip-image-captioning-base)

The two checks run concurrently and produce a combined image-risk score.
"""

import asyncio
import logging

import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── HuggingFace Inference API endpoints ──
HF_NSFW_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "Falconsai/nsfw_image_detection"
)
HF_CAPTION_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "Salesforce/blip-image-captioning-base"
)

# Keywords in image captions that may indicate scam / fraud / dangerous content
_SCAM_CAPTION_KEYWORDS: list[str] = [
    "money", "cash", "dollar", "euro", "bitcoin", "crypto", "lottery",
    "prize", "check", "cheque", "bank", "credit card", "gift card",
    "wire", "passport", "id card", "license", "weapon", "gun", "knife",
    "pill", "drug", "nude", "naked",
]


# ────────────────────────────────────────────────────────────
# Individual checks
# ────────────────────────────────────────────────────────────

async def check_image_nsfw(image_bytes: bytes) -> dict:
    """
    Detect NSFW / inappropriate content using the
    ``Falconsai/nsfw_image_detection`` classifier.

    Returns
    -------
    dict  {"score": float|None, "details": list|None, "error": str|None}
    """
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping NSFW check.")
        return {"score": None, "details": None, "error": "API token not configured"}

    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HF_NSFW_URL, content=image_bytes, headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        # Response: [{"label": "nsfw", "score": 0.99}, {"label": "normal", "score": 0.01}]
        nsfw_score = 0.0
        for item in data:
            if item.get("label", "").lower() == "nsfw":
                nsfw_score = item["score"]
                break

        return {"score": round(nsfw_score, 6), "details": data, "error": None}

    except httpx.HTTPStatusError as exc:
        logger.error("NSFW detection HTTP error: %s", exc.response.text)
        return {"score": None, "details": None, "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        logger.error("NSFW detection failed: %s", exc)
        return {"score": None, "details": None, "error": str(exc)}


async def check_image_caption(image_bytes: bytes) -> dict:
    """
    Generate a caption for the image using BLIP and scan it for
    suspicious keywords that may indicate scam / fraud content.

    Returns
    -------
    dict  {"caption": str|None, "scam_score": float, "matches": list, "error": str|None}
    """
    if not settings.HF_API_TOKEN or settings.HF_API_TOKEN.startswith("hf_REPLACE"):
        logger.warning("HF API token not configured — skipping image caption.")
        return {"caption": None, "scam_score": 0.0, "matches": [], "error": "API token not configured"}

    headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HF_CAPTION_URL, content=image_bytes, headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        caption = data[0].get("generated_text", "") if isinstance(data, list) and data else ""

        # Scan caption for suspicious keywords
        caption_lower = caption.lower()
        matches = [kw for kw in _SCAM_CAPTION_KEYWORDS if kw in caption_lower]
        scam_score = min(len(matches) * 0.20, 1.0)

        return {
            "caption": caption,
            "scam_score": round(scam_score, 4),
            "matches": matches,
            "error": None,
        }

    except httpx.HTTPStatusError as exc:
        logger.error("Image captioning HTTP error: %s", exc.response.text)
        return {"caption": None, "scam_score": 0.0, "matches": [], "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        logger.error("Image captioning failed: %s", exc)
        return {"caption": None, "scam_score": 0.0, "matches": [], "error": str(exc)}


# ────────────────────────────────────────────────────────────
# Combined image analysis
# ────────────────────────────────────────────────────────────

async def analyze_image(image_bytes: bytes) -> dict:
    """
    Run NSFW detection and caption-based scam analysis **concurrently**
    and return a combined image-risk payload.

    Returns
    -------
    dict
        {
            "nsfw": {...},
            "caption": {...},
            "combined_score": float,  # 0–1 risk score
            "is_partial": bool,
        }
    """
    nsfw_result, caption_result = await asyncio.gather(
        check_image_nsfw(image_bytes),
        check_image_caption(image_bytes),
    )

    nsfw_score = nsfw_result["score"] if nsfw_result["score"] is not None else 0.0
    scam_score = caption_result.get("scam_score", 0.0)

    # Weight: 70 % NSFW, 30 % caption-based scam
    combined_score = round(nsfw_score * 0.70 + scam_score * 0.30, 4)

    is_partial = nsfw_result["score"] is None

    return {
        "nsfw": nsfw_result,
        "caption": caption_result,
        "combined_score": combined_score,
        "is_partial": is_partial,
    }
