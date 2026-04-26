"""
app/services/hf_xray_service.py — LLM-powered X-Ray word highlighting.

Uses NVIDIA NIM to run an instruction-following LLM that identifies which
specific words and phrases in the input text are problematic (profane,
toxic, fraudulent, or carrying strongly negative sentiment).

Unlike regex-based detection, the LLM understands **context**, sarcasm,
code-switching, and multilingual nuances — producing more accurate and
fewer false-positive highlights.

The service returns character-level spans in the same format consumed
by ``aggregator._build_xray_html``, so the rest of the pipeline is
unchanged.
"""

import json
import re
import logging
from openai import APIError, APIStatusError

from app.services.nvidia_nim_service import is_nim_configured, nim_chat_completion

logger = logging.getLogger(__name__)

# ── Category → visual source (for CSS class mapping) ────────
_CATEGORY_TO_SOURCE: dict[str, str] = {
    "en_profanity":       "profanity",
    "ua_profanity":       "profanity",
    "ua_toxic":           "profanity",
    "financial_scam":     "fraud",
    "crypto_scam":        "fraud",
    "phishing":           "fraud",
    "suspicious_url":     "fraud",
    "urgency":            "fraud",
    "pii_request":        "fraud",
    "lottery_scam":       "fraud",
    "advance_fee":        "fraud",
    "impersonation":      "fraud",
    "negative_sentiment": "sentiment",
}

_VALID_CATEGORIES = set(_CATEGORY_TO_SOURCE.keys())

# ── System prompt ────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are a multilingual content moderation assistant. "
    "Analyse the user's text and identify every specific word or "
    "short phrase that is problematic.\n\n"
    "For each match return a JSON object with two keys:\n"
    '  "text"     — the exact substring as it appears in the input '
    "(preserve spelling and case)\n"
    '  "category" — one of the allowed category codes listed below\n\n'
    "Allowed categories:\n"
    "  en_profanity       — English swear words, vulgar language, obscenities\n"
    "  ua_profanity       — Ukrainian swear words, vulgar language, obscenities\n"
    "  ua_toxic           — Ukrainian insults, dehumanisation, toxic language "
    "(not necessarily vulgar)\n"
    "  financial_scam     — financial scam or investment fraud phrases\n"
    "  crypto_scam        — cryptocurrency / blockchain scam phrases\n"
    "  phishing           — credential harvesting, fake login requests\n"
    "  suspicious_url     — suspicious or deceptive URLs\n"
    "  urgency            — high-pressure / \"act now\" / deadline manipulation\n"
    "  pii_request        — requests for personal or financial information\n"
    "  lottery_scam       — \"you have won\" / prize-claim scam phrases\n"
    "  advance_fee        — advance-fee / processing-fee fraud phrases\n"
    "  impersonation      — impersonation of authority, government, or companies\n"
    "  negative_sentiment — strongly negative emotional words, threats, "
    "wishes of harm, hate\n\n"
    "Rules:\n"
    "1. Return ONLY a JSON array — no markdown fences, no commentary.\n"
    "2. Only flag genuinely harmful content. Do NOT flag neutral or "
    "mildly negative words.\n"
    '3. Keep "text" as short as possible (single word or short phrase).\n'
    "4. If nothing is problematic return [].\n"
    "5. Support English, Ukrainian, and mixed-language input.\n\n"
    "Example input:\n"
    '  "You won a million dollars! Send $50 processing fee now, damn it!"\n'
    "Example output:\n"
    '[{"text":"won a million dollars","category":"lottery_scam"},'
    '{"text":"Send $50 processing fee","category":"advance_fee"},'
    '{"text":"damn","category":"en_profanity"}]'
)


# ── Helpers ──────────────────────────────────────────────────

def _find_all_positions(text: str, substring: str) -> list[tuple[int, int]]:
    """Return (start, end) for every case-insensitive occurrence of *substring* in *text*."""
    positions: list[tuple[int, int]] = []
    lower_text = text.lower()
    lower_sub = substring.lower().strip()
    if not lower_sub:
        return positions
    start = 0
    while True:
        idx = lower_text.find(lower_sub, start)
        if idx == -1:
            break
        positions.append((idx, idx + len(substring.strip())))
        start = idx + 1
    return positions


def _parse_llm_response(raw: str, text: str) -> list[dict]:
    """
    Parse the LLM's JSON output and map each identified word/phrase
    back to character positions in *text*.

    Returns a list of span dicts compatible with ``_build_xray_html``.
    """
    cleaned = raw.strip()

    # Strip markdown code fences the model may wrap around JSON
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Try to extract a JSON array if the model added extra text
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM X-Ray: could not parse JSON: %.200s", raw)
        return []

    if not isinstance(items, list):
        logger.warning("LLM X-Ray: expected JSON array, got %s", type(items).__name__)
        return []

    spans: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        word = str(item.get("text", "")).strip()
        category = str(item.get("category", "")).strip()
        if not word or category not in _VALID_CATEGORIES:
            continue

        source = _CATEGORY_TO_SOURCE[category]
        for start, end in _find_all_positions(text, word):
            spans.append({
                "text": text[start:end],  # preserve original casing
                "start": start,
                "end": end,
                "source": source,
                "category": category,
            })

    return spans


# ── Public API ───────────────────────────────────────────────

async def check_xray(text: str) -> dict:
    """
    Use an instruction-following LLM to identify problematic words
    and phrases in *text*.

    Returns
    -------
    dict
        {
            "triggered_words": list[dict],   # spans with start/end/source/category
            "error": str | None
        }
    """
    if not is_nim_configured():
        logger.warning("NVIDIA API key not configured — skipping LLM X-Ray.")
        return {"triggered_words": [], "error": "API token not configured"}

    try:
        raw_content = await nim_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        spans = _parse_llm_response(raw_content, text)

        logger.info(raw_content)
        logger.info("NVIDIA NIM X-Ray identified %d span(s).", len(spans))
        return {"triggered_words": spans, "error": None}

    except APIStatusError as exc:
        logger.error("NVIDIA NIM X-Ray HTTP error: %s", str(exc)[:300])
        return {
            "triggered_words": [],
            "error": f"HTTP {exc.status_code}",
        }

    except APIError as exc:
        logger.error("NVIDIA NIM X-Ray API error: %s", exc)
        return {"triggered_words": [], "error": str(exc)}

    except Exception as exc:
        logger.error("NVIDIA NIM X-Ray call failed: %s", exc)
        return {"triggered_words": [], "error": str(exc)}
